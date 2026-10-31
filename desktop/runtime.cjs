const fs=require('node:fs');const fsp=fs.promises;const path=require('node:path');
const crypto=require('node:crypto');const {spawn}=require('node:child_process');const tar=require('tar');

function executable(prefix,platform=process.platform){return path.join(prefix,platform==='win32'?'python.exe':'bin/python')}
function environment(prefix,extra={},platform=process.platform){
 const lib=platform==='win32'?path.join(prefix,'Library'):prefix;
 const env={...process.env,...extra,PYTHONNOUSERSITE:'1',PYTHONUTF8:'1',QT_QPA_PLATFORM:'offscreen',
  QGIS_PREFIX_PATH:lib,GDAL_DATA:path.join(lib,'share/gdal'),PROJ_DATA:path.join(lib,'share/proj'),
  PATH:[prefix,path.join(prefix,'Scripts'),path.join(lib,'bin'),process.env.PATH||''].join(path.delimiter)};
 for(const key of ['PYTHONHOME','PYTHONPATH','QT_PLUGIN_PATH','LD_LIBRARY_PATH','DYLD_LIBRARY_PATH'])delete env[key];
 for(const folder of [path.join(lib,'plugins'),path.join(lib,'lib/qt/plugins'),path.join(lib,'lib/qt6/plugins')])
  if(fs.existsSync(folder)){env.QT_PLUGIN_PATH=folder;break}
 return env;
}
function run(command,args,options={}){
 return new Promise((resolve,reject)=>{
  const child=spawn(command,args,{windowsHide:true,...options});let error='';
  child.stdout?.on('data',data=>options.log?.(data.toString()));
  child.stderr?.on('data',data=>{error=(error+data).slice(-6000);options.log?.(data.toString())});
  child.on('error',reject);child.on('exit',code=>code===0?resolve():reject(new Error('运行环境准备失败（'+code+'）：'+error)));
 });
}
async function digest(file){const hash=crypto.createHash('sha256');for await(const chunk of fs.createReadStream(file))hash.update(chunk);return hash.digest('hex')}
async function installRuntime(resources,userData,status=()=>{},log=()=>{}){
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
 await tar.x({file:archive,cwd:root,strict:true,preservePaths:false,
  filter:(entry)=>!path.isAbsolute(entry)&&!entry.replaceAll('\\','/').split('/').includes('..')});
 const unpack=process.platform==='win32'?path.join(root,'Scripts/conda-unpack-script.py'):path.join(root,'bin/conda-unpack');
 await run(executable(root),[unpack],{env:environment(root),log});
 await run(executable(root),['-c','import fastapi,geopandas,rasterio,langgraph; print("GAIA_RUNTIME_READY")'],{env:environment(root),log});
 await fsp.writeFile(marker,manifest.sha256);return root;
}
module.exports={executable,environment,installRuntime,digest,run};
