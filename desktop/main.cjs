const {app,BrowserWindow,Menu,protocol,net,session,shell,dialog,ipcMain}=require('electron');
const fs=require('node:fs');const fsp=fs.promises;const path=require('node:path');const crypto=require('node:crypto');
const {spawn}=require('node:child_process');const runtime=require('./runtime.cjs');
app.setName('GAIA');
if(process.env.GAIA_DESKTOP_DATA_DIR)app.setPath('userData',path.resolve(process.env.GAIA_DESKTOP_DATA_DIR));
protocol.registerSchemesAsPrivileged([{scheme:'gaia',privileges:{standard:true,secure:true,supportFetchAPI:true,corsEnabled:true,stream:true}}]);
let window,child,base,stopping=false,booting=false,currentStatus='正在启动 GAIA…',failure=false,logs,workspace;
const token=crypto.randomBytes(32).toString('hex');
const resources=app.isPackaged?process.resourcesPath:path.resolve(__dirname,'../.desktop-build');
const serverRoot=app.isPackaged?path.join(resources,'server'):path.resolve(__dirname,'..');
const bootURL='gaia://app/_desktop/boot';
function status(text,error=false){currentStatus=text;failure=error;window?.webContents.send('boot-status',{text,error})}
function log(message){if(logs)fs.appendFileSync(path.join(logs,'desktop.log'),new Date().toISOString()+' '+message+'\n')}
function prefs(){return {contextIsolation:true,nodeIntegration:false,sandbox:true,preload:path.join(__dirname,'preload.cjs')}}
function trusted(url){return url.startsWith('gaia://app/')}
function attachNavigation(win){
 win.webContents.on('will-navigate',(event,url)=>{if(!trusted(url))event.preventDefault()});
 win.webContents.setWindowOpenHandler(({url})=>{
  if(trusted(url))return {action:'allow',overrideBrowserWindowOptions:{webPreferences:prefs(),width:1100,height:800}};
  if(/^https?:\/\//.test(url))dialog.showMessageBox(window,{type:'question',message:'在浏览器中打开此链接？',detail:url,buttons:['取消','打开'],defaultId:0}).then(({response})=>{if(response===1)shell.openExternal(url)});
  return {action:'deny'};
 });
 win.webContents.on('did-create-window',attachNavigation);
}
function createWindow(){
 window=new BrowserWindow({title:'GAIA',width:1480,height:960,minWidth:860,minHeight:620,
  backgroundColor:'#eef3f1',show:false,webPreferences:prefs(),icon:app.isPackaged?path.join(resources,'gaia-icon.png'):path.join(serverRoot,'frontend/public/gaia-icon.png')});
 attachNavigation(window);window.once('ready-to-show',()=>window.show());window.on('closed',()=>{window=null});
 window.loadURL(base?'gaia://app/':bootURL);
}
async function stopBackend(){
 runtime.cancelRuntime();
 const process=child;child=null;base=null;if(!process)return;
 process.stdin?.end();
 await Promise.race([new Promise(resolve=>process.once('exit',resolve)),new Promise(resolve=>setTimeout(resolve,5000))]);
 if(process.exitCode===null)process.kill();
}
async function boot(){
 if(booting)return;booting=true;failure=false;
 try{
  await stopBackend();
  const prefix=(!app.isPackaged&&process.env.GAIA_DEV_RUNTIME)||await runtime.installRuntime(resources,app.getPath('userData'),status,log);
  status('正在启动本地分析服务…');
  const ready=path.join(app.getPath('userData'),'sessions',crypto.randomUUID()+'.json');
  const env=runtime.environment(prefix,{GEOAGENT_WORKSPACE:workspace,GEOAGENT_CACHE_DIR:path.join(app.getPath('userData'),'cache'),
   GAIA_DESKTOP_TOKEN:token,GAIA_DESKTOP_READY:ready,GIS_QGIS_PYTHON:runtime.executable(prefix),GIS_PYTHON:runtime.executable(prefix)});
  env.PYTHONPATH=path.join(serverRoot,'backend');
  child=spawn(runtime.executable(prefix),['-m','geoagent.desktop'],{cwd:serverRoot,env,windowsHide:true,stdio:['pipe','pipe','pipe']});
  child.stdout.on('data',data=>log(data.toString()));child.stderr.on('data',data=>log(data.toString()));
  let exited=false;child.on('error',error=>{exited=true;log(error.message)});
  child.on('exit',code=>{exited=true;log('Backend exited: '+code);if(!stopping&&!booting){base=null;status('本地服务已停止。请重试启动；已有数据和检查点保留。',true);window?.loadURL(bootURL)}});
  const deadline=Date.now()+120000;let address;
  while(Date.now()<deadline&&!exited){
   try{const value=JSON.parse(await fsp.readFile(ready,'utf8'));address='http://127.0.0.1:'+value.port;
    const result=await net.fetch(address+'/api/health',{headers:{'x-gaia-token':token},signal:AbortSignal.timeout(1500)});
    if(result.ok){base=address;break}
   }catch{}
   await new Promise(resolve=>setTimeout(resolve,250));
  }
  if(!base)throw new Error('本地服务未能启动。可从“帮助 → 打开日志目录”查看原因。');
  await window.loadURL('gaia://app/');log('Workbench ready.');
 }catch(error){log(error.stack||error.message);status(error.message,true)}
 finally{booting=false}
}
if(!app.requestSingleInstanceLock())app.quit();
else{
 app.on('second-instance',()=>{if(window){if(window.isMinimized())window.restore();window.focus()}});
 app.whenReady().then(async()=>{
  workspace=path.join(app.getPath('userData'),'workspace');logs=path.join(app.getPath('userData'),'logs');
  await fsp.mkdir(logs,{recursive:true});await fsp.mkdir(workspace,{recursive:true});
  const logfile=path.join(logs,'desktop.log');
  if(fs.existsSync(logfile)&&(await fsp.stat(logfile)).size>5*1024*1024)await fsp.rename(logfile,logfile+'.previous').catch(()=>{});
  protocol.handle('gaia',async request=>{
   const url=new URL(request.url);
   if(url.host!=='app'||(request.initiatorOrigin&&!['gaia://app','null'].includes(request.initiatorOrigin)))return new Response('Forbidden',{status:403});
   const assets={'/_desktop/boot':['boot.html','text/html'],'/_desktop/boot.css':['boot.css','text/css'],'/_desktop/boot.js':['boot.js','text/javascript']};
   if(assets[url.pathname]){
    const [file,type]=assets[url.pathname];return new Response(await fsp.readFile(path.join(__dirname,file)),{headers:{'content-type':type,'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:"}});
   }
   if(!base)return new Response('Local service is starting',{status:503});
   const headers=new Headers(request.headers);headers.delete('origin');headers.delete('host');headers.set('x-gaia-token',token);
   const response=await net.fetch(base+url.pathname+url.search,{method:request.method,headers,body:['GET','HEAD'].includes(request.method)?undefined:request.body,duplex:'half',redirect:'error'});
   const out=new Headers(response.headers);out.set('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self' https:; worker-src 'self' blob:; font-src 'self' data:; object-src 'none'; frame-src 'self' blob:");
   return new Response(response.body,{status:response.status,headers:out});
  });
  session.defaultSession.setPermissionRequestHandler((wc,permission,callback)=>callback(false));
  session.defaultSession.setPermissionCheckHandler(()=>false);
  session.defaultSession.on('will-download',(event,item)=>{
   item.setSaveDialogOptions({defaultPath:path.join(app.getPath('downloads'),path.basename(item.getFilename())),title:'保存 GAIA 成果'});
  });
  ipcMain.handle('boot-state',event=>event.senderFrame.url===bootURL?{text:currentStatus,error:failure}:null);
  ipcMain.handle('boot-retry',event=>{if(event.senderFrame.url===bootURL&&failure)void boot()});
  const menu=[
   ...(process.platform==='darwin'?[{label:'GAIA',submenu:[{role:'about'},{type:'separator'},{role:'quit'}]}]:[]),
   {label:'文件',submenu:[{label:'打开工作区目录',click:()=>shell.openPath(workspace)},{type:'separator'},{role:'quit',label:'退出 GAIA'}]},
   {label:'编辑',submenu:[{role:'undo'},{role:'redo'},{type:'separator'},{role:'cut'},{role:'copy'},{role:'paste'},{role:'selectAll'}]},
   {label:'视图',submenu:[{role:'reload',label:'重新加载界面'},{role:'resetZoom'},{role:'zoomIn'},{role:'zoomOut'},{role:'togglefullscreen'}]},
   {label:'帮助',submenu:[{label:'打开日志目录',click:()=>shell.openPath(logs)},{label:'下载与更新',click:()=>shell.openExternal('https://github.com/liujiayuGIS/geoagent-studio/releases')},{label:'关于 GAIA',click:()=>dialog.showMessageBox(window,{message:'GAIA '+app.getVersion(),detail:'地理空间人工智能助手盖亚\n数据与分析在本机运行；模型调用需要配置 API。'})}]}
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(menu));createWindow();void boot();
 });
 app.on('window-all-closed',()=>app.quit());
 app.on('before-quit',event=>{if(!stopping){event.preventDefault();stopping=true;stopBackend().finally(()=>app.quit())}});
}
