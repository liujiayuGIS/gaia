const fs=require('node:fs');const fsp=fs.promises;const path=require('node:path');
const crypto=require('node:crypto');const {spawn}=require('node:child_process');const tar=require('tar');
const preparing=new Set();

function executable(prefix,platform=process.platform){return path.join(prefix,platform==='win32'?'python.exe':'bin/python')}
function environment(prefix,extra={},platform=process.platform){
 const lib=platform==='win32'?path.join(prefix,'Library'):prefix;
 const env={...process.env,...extra,PYTHONNOUSERSITE:'1',PYTHONDONTWRITEBYTECODE:'1',PYTHONUTF8:'1',QT_QPA_PLATFORM:'offscreen',
  QGIS_PREFIX_PATH:lib,GDAL_DATA:path.join(lib,'share/gdal'),PROJ_DATA:path.join(lib,'share/proj'),
  PATH:[prefix,path.join(prefix,'Scripts'),path.join(lib,'bin'),process.env.PATH||''].join(path.delimiter)};
 for(const key of ['PYTHONHOME','PYTHONPATH','QT_PLUGIN_PATH','LD_LIBRARY_PATH','DYLD_LIBRARY_PATH'])delete env[key];
 for(const folder of [path.join(lib,'plugins'),path.join(lib,'lib/qt/plugins'),path.join(lib,'lib/qt6/plugins')])
  if(fs.existsSync(folder)){env.QT_PLUGIN_PATH=folder;break}
 return env;
}
function run(command,args,options={}){
 return new Promise((resolve,reject)=>{
  const child=spawn(command,args,{windowsHide:true,...options});preparing.add(child);let error='';
  child.stdout?.on('data',data=>options.log?.(data.toString()));
  child.stderr?.on('data',data=>{error=(error+data).slice(-6000);options.log?.(data.toString())});
  child.on('error',err=>{preparing.delete(child);reject(err)});child.on('exit',code=>{preparing.delete(child);code===0?resolve():reject(new Error('运行环境准备失败（'+code+'）：'+error))});
 });
}
async function digest(file){const hash=crypto.createHash('sha256');for await(const chunk of fs.createReadStream(file))hash.update(chunk);return hash.digest('hex')}
function cancelRuntime(){for(const child of preparing)child.kill()}
function windowsEntrySafe(entry){
 const parts=entry.path.replaceAll('\\','/').split('/');
 return ['File','Directory'].includes(entry.type)&&!path.win32.isAbsolute(entry.path)&&
  !parts.some(p=>p==='..'||p.includes(':')||(p!=='.'&&/[. ]$/.test(p))||/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\.|$)/i.test(p));
}
async function validateWindowsArchive(archive,progress=()=>{}){
 let invalid,count=0;
 const parser=new tar.Parser({strict:true,onReadEntry:entry=>{
  if(!windowsEntrySafe(entry))invalid=new Error('Unsafe Windows archive entry: '+entry.path);
  if(++count%2000===0)progress(count);entry.resume();
 }});
 await new Promise((resolve,reject)=>{
  const input=fs.createReadStream(archive);input.on('error',reject);
  parser.on('error',error=>{input.destroy();reject(error)});parser.on('end',resolve);input.pipe(parser);
 });
 if(invalid)throw invalid;
}
async function extractRuntime(archive,root,progress=()=>{}){
 const links=[];let invalid;let entries=0;
 const inside=value=>value===root||value.startsWith(root+path.sep);
 const unpack=new tar.Unpack({cwd:root,strict:true,preservePaths:false,filter:(entry,header)=>{
  if(++entries%2000===0)progress(entries);
  if(path.isAbsolute(entry)||entry.replaceAll('\\','/').split('/').includes('..')){invalid=new Error('Unsafe archive path: '+entry);return false}
  // Conda contains legitimate chains such as lib/icu/pkgdata.inc -> current/pkgdata.inc.
  // Extract files first so tar never writes through a symlink, then create the links.
  if(header.type==='SymbolicLink'){
   const destination=path.resolve(root,entry),target=path.resolve(path.dirname(destination),header.linkpath);
   if(path.isAbsolute(header.linkpath)||!inside(target)){invalid=new Error('Unsafe archive link: '+entry);return false}
   links.push({destination,target:header.linkpath});return false;
  }
  return true;
 }});
 await new Promise((resolve,reject)=>{
  const input=fs.createReadStream(archive);
  input.on('error',reject);unpack.on('error',error=>{input.destroy();reject(error)});
  unpack.on('close',resolve);input.pipe(unpack);
 });
 if(invalid)throw invalid;
 for(const link of links){
  await fsp.mkdir(path.dirname(link.destination),{recursive:true});
  const parent=await fsp.realpath(path.dirname(link.destination));
  if(!inside(parent))throw new Error('Unsafe archive link parent');
  await fsp.symlink(link.target,link.destination);
 }
 for(const link of links){
  try{if(!inside(await fsp.realpath(link.destination)))throw new Error('Archive link escapes runtime')}
  catch(error){if(error.code!=='ENOENT')throw error}
 }
}
async function installRuntime(resources,userData,status=()=>{},log=()=>{}){
 userData=await fsp.realpath(userData);
 const source=path.join(resources,'runtime'),manifest=JSON.parse(await fsp.readFile(path.join(source,'manifest.json'),'utf8'));
 if(manifest.platform!==process.platform||manifest.arch!==process.arch)throw new Error('安装包与本机架构不符，请下载对应系统和处理器版本。');
 if(!/^[a-f0-9]{64}$/.test(manifest.sha256))throw new Error('运行环境清单无效。');
 const root=path.join(userData,'runtimes',manifest.sha256.slice(0,20)),marker=path.join(root,'.gaia-ready');
 try{if((await fsp.readFile(marker,'utf8'))===manifest.sha256&&fs.existsSync(executable(root)))return root}catch{}
 status('首次启动：校验本地 GIS 运行环境…');
 const archive=path.join(source,'runtime.tar.gz');
 if(await digest(archive)!==manifest.sha256)throw new Error('运行环境校验失败，请重新下载安装包。');
 await fsp.rm(root,{recursive:true,force:true});await fsp.mkdir(root,{recursive:true});
 status('首次启动：正在安装 Python 与 QGIS，可能需要几分钟…');
 // conda-pack environments cannot move after conda-unpack; extract at final path.
 const nativeTar=path.join(process.env.SystemRoot||'C:\\Windows','System32','tar.exe');
 if(process.platform==='win32'&&fs.existsSync(nativeTar)){
  await validateWindowsArchive(archive,count=>status('首次启动：正在检查 GIS 文件目录，已读取 '+count.toLocaleString()+' 项…'));
  status('首次启动：正在展开本机 GIS 环境，请保持应用打开…');
  await run(nativeTar,['-xzf',archive,'-C',root],{log});
 }else await extractRuntime(archive,root,count=>status('首次启动：正在解压 GIS 环境，已读取 '+count.toLocaleString()+' 个文件…'));
 status('首次启动：正在校准 GIS 库路径，请保持应用打开…');
 const unpack=process.platform==='win32'?path.join(root,'Scripts/conda-unpack-script.py'):path.join(root,'bin/conda-unpack');
 await run(executable(root),[unpack],{env:environment(root),log});
 status('首次启动：正在验证本机 GIS 环境…');
 await run(executable(root),['-c','import fastapi,geopandas,rasterio,langgraph; print("GAIA_RUNTIME_READY")'],{env:environment(root),log});
 await fsp.writeFile(marker,manifest.sha256);return root;
}
module.exports={executable,environment,installRuntime,digest,run,extractRuntime,validateWindowsArchive,windowsEntrySafe,cancelRuntime};
