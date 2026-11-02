// Exercises the real Electron window, local API, persistence, and native export.
const {_electron:electron}=require('playwright');const path=require('node:path');const fs=require('node:fs');const os=require('node:os');const assert=require('node:assert/strict');
(async()=>{
 const userData=process.env.GAIA_SMOKE_DATA_DIR||fs.mkdtempSync(path.join(os.tmpdir(),'gaia-desktop-test-'));
 const graphics=process.env.GAIA_SMOKE_NO_GPU==='1'?['--use-gl=angle','--use-angle=swiftshader-webgl','--enable-unsafe-swiftshader']:[];
 const launch=()=>electron.launch({...(process.env.GAIA_PACKAGED_EXECUTABLE?{executablePath:process.env.GAIA_PACKAGED_EXECUTABLE,args:graphics}:{args:[path.resolve(__dirname,'..'),...graphics]}),
  env:{...process.env,GAIA_DESKTOP_DATA_DIR:userData},timeout:600000});
 const ready=page=>Promise.race([page.waitForURL('gaia://app/',{timeout:600000}),page.locator('#retry').waitFor({state:'visible',timeout:600000}).then(async()=>{throw new Error('Desktop startup: '+await page.locator('#status').innerText())})]);
 console.log('Desktop test data: '+userData);
 let app=await launch();
 const watchdog=setTimeout(()=>{console.error('Desktop smoke exceeded 15 minutes');app.process().kill('SIGKILL')},900000);
 watchdog.unref();
 try{
  let page=await app.firstWindow();page.setDefaultTimeout(60000);
  const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error(e.message)});
  page.on('console',e=>{if(e.type()==='error')console.error('Renderer: '+e.text())});
  await ready(page);await page.locator('.atlas-workbench').waitFor();
  console.log('Desktop workbench ready');
  assert.equal(await page.evaluate(()=>typeof require),'undefined');
  const result=await page.evaluate(async()=>{
   const get=async p=>(await fetch('/api'+p)).json();
   const health=await get('/health');const demo=await fetch('/api/demo',{method:'POST'});
   const layers=await get('/layers');const caps=await get('/capabilities');
   localStorage.setItem('desktop-persistence-test','retained');
   return {health,demo:demo.status,count:layers.length,qgis:caps.plugins?.find(x=>x.id==='qgis')};
  });
  assert(await page.locator('.atlas-workbench').count(),'Latest Atlas/Folio UI must be bundled');
  assert.equal(await app.evaluate(({app})=>app.getVersion()),require('../package.json').version);
  assert.equal(await app.evaluate(({app})=>app.getName()),'GAIA');
  assert(result.qgis?.available,JSON.stringify(result.qgis));
  assert(result.health.ok);assert.equal(result.demo,200);assert(result.count>0);
  console.log('Local API and QGIS ready');
  const analysis=await page.evaluate(async()=>{
   const json=async(url,body,method='POST')=>{const r=await fetch('/api'+url,{method,headers:{'content-type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json()};
   const layers=await (await fetch('/api/layers')).json();
   const source=layers.find(l=>l.source==='demo'&&l.geometry_types?.includes('Point'));
   const started=await json('/runs',{session_id:'desktop-smoke',message:'Desktop buffer verification',mode:'algorithm',algorithm_id:'buffer',arguments:{layer_id:source.id,distance_m:100}});
   let run;const deadline=Date.now()+240000;
   do{run=await (await fetch('/api/runs/'+started.id)).json();if(!['queued','running'].includes(run.status))break;await new Promise(r=>setTimeout(r,500))}while(Date.now()<deadline);
   if(run.status!=='completed')throw new Error(JSON.stringify(run));
   await json('/layout',{plugin_id:'qgis',title:'GAIA 桌面出图验证',focus_layer_id:run.output_layers[0],map_crs:'EPSG:32650',legend_position:'outside-right'},'PATCH');
   const styles=await (await fetch('/api/layout/styles')).json();
   if(!styles.default_cjk||!styles.fonts?.some(f=>f.bundled&&f.family==='Noto Sans CJK SC')||styles.north_styles?.length!==4||styles.terrain_palettes?.length!==5||!styles.fonts?.some(f=>f.family===styles.default_font))throw new Error('Latest style/font catalog missing');
   await json('/layout/items/title',{font_family:styles.default_font,font_weight:600,font_size:22},'PATCH');
   const styled=await json('/runs',{session_id:'desktop-smoke',mode:'offline',message:'指北针改成罗盘玫瑰，比例尺用双线框，单位米，分4段'});
   let styleRun;
   do{styleRun=await (await fetch('/api/runs/'+styled.id)).json();if(!['queued','running'].includes(styleRun.status))break;await new Promise(r=>setTimeout(r,500))}while(Date.now()<deadline);
   if(styleRun.status!=='completed')throw new Error(JSON.stringify(styleRun));
   const scene=await (await fetch('/api/layout/scene')).json(),byId=Object.fromEntries(scene.elements.map(e=>[e.id,e]));
   if(byId.north_arrow.north_style!=='rose'||byId.scale_bar.scale_style!=='Double Box'||byId.scale_bar.scale_units!=='m'||byId.title.font_family!==styles.default_font||byId.title.font_size!==22)throw new Error('Native style scene did not match request');
   const exported=await json('/layout/export',{format:'pdf',dpi:100});
   const pdf=await (await fetch(exported.url)).arrayBuffer();
   if(new TextDecoder().decode(pdf.slice(0,5))!=='%PDF-')throw new Error('Invalid exported PDF');
   return {count:(await (await fetch('/api/layers')).json()).length,pdf:exported.url,font:styles.default_font,scaleStyles:styles.scale_styles.map(s=>s.id)};
  });
  result.count=analysis.count;
  console.log('Analysis, natural-language styles and native PDF export passed: '+JSON.stringify({font:analysis.font,scaleStyles:analysis.scaleStyles}));
  const saved=path.resolve(__dirname,'../../.desktop-build/qa/desktop-export-'+process.platform+'.pdf');
  fs.mkdirSync(path.dirname(saved),{recursive:true});
  // Acknowledge registration before clicking: main/renderer IPC can otherwise
  // race and leave a native save dialog waiting for a person on slower hosts.
  await app.evaluate(({session},file)=>{
   globalThis.__gaiaTestDownload=new Promise(resolve=>{
    const timer=setTimeout(()=>resolve('timed-out'),120000);
    session.defaultSession.once('will-download',(_,item)=>{item.setSavePath(file);item.once('done',(_,state)=>{clearTimeout(timer);resolve(state)})});
   });
  },saved);
  await page.evaluate(url=>{const a=document.createElement('a');a.href=url;a.download='GAIA-map.pdf';document.body.appendChild(a);a.click();a.remove()},analysis.pdf);
  assert.equal(await app.evaluate(()=>globalThis.__gaiaTestDownload),'completed');assert.equal(fs.readFileSync(saved).subarray(0,5).toString(),'%PDF-');
  console.log('Native file save passed');

  // Requests outside the private bridge cannot read the user's workspace.
  const readyDir=path.join(userData,'sessions');
  const address=JSON.parse(fs.readFileSync(path.join(readyDir,fs.readdirSync(readyDir).filter(x=>x.endsWith('.json')).sort((a,b)=>fs.statSync(path.join(readyDir,b)).mtimeMs-fs.statSync(path.join(readyDir,a)).mtimeMs)[0]),'utf8'));
  assert.equal((await fetch('http://127.0.0.1:'+address.port+'/api/layers')).status,401);
  await page.reload();await page.waitForSelector('.map-canvas[data-ready="true"]',{timeout:120000});
  const renderer=await page.locator('.map-canvas').getAttribute('data-renderer');
  if(process.env.GAIA_SMOKE_NO_GPU==='1')assert.equal(renderer,'leaflet');
  console.log('Interactive map ready: '+renderer);
  const narrow=await page.locator('.mobile-navigation').isVisible();
  await page.getByRole('button',{name:narrow?'布局':'出图布局',exact:true}).click();
  await page.waitForSelector('.layout-page .layout-item',{timeout:120000});
  if(narrow)await page.getByRole('button',{name:'数据与工具',exact:true}).click();
  await page.locator('.contents-tree').getByRole('button',{name:'指北针',exact:true}).click();
  await page.getByRole('button',{name:'指北针 极简线形',exact:true}).click();
  await page.evaluate(async()=>{const deadline=Date.now()+30000;while(Date.now()<deadline){const r=await fetch('/api/layout');if(!r.ok)throw new Error(await r.text());const c=await r.json();if(c.items.north_arrow?.north_style==='minimal')return;await new Promise(resolve=>setTimeout(resolve,150))}throw new Error('Manual north style was not persisted')});
  const manual=await page.evaluate(async()=>{const r=await fetch('/api/layout/scene');const scene=await r.json();return scene.elements.find(e=>e.id==='north_arrow').north_style});
  assert.equal(manual,'minimal');
  await page.getByRole('button',{name:'外观设置',exact:true}).click();
  await page.getByLabel('界面字体',{exact:true}).selectOption('sans');
  await page.waitForFunction(()=>JSON.parse(localStorage.getItem('geoagent-appearance-v3')).font==='sans');
  console.log('Desktop manual style and font controls passed');
  fs.mkdirSync(path.resolve(__dirname,'../../.desktop-build/qa'),{recursive:true});
  await page.screenshot({path:path.resolve(__dirname,'../../.desktop-build/qa/desktop-'+process.platform+'-'+process.arch+'.png')});
  fs.writeFileSync(path.resolve(__dirname,'../../.desktop-build/qa/smoke-user-data.txt'),userData);
  assert.deepEqual(errors,[]);
  await app.close();app=await launch();page=await app.firstWindow();await ready(page);
  assert.equal(await page.evaluate(()=>localStorage.getItem('desktop-persistence-test')),'retained');
  const count=await page.evaluate(async()=>(await (await fetch('/api/layers')).json()).length);
  assert.equal(count,result.count);
  const persisted=await page.evaluate(async()=>({layout:await (await fetch('/api/layout')).json(),font:JSON.parse(localStorage.getItem('geoagent-appearance-v3')).font}));
  assert.equal(persisted.layout.items.north_arrow.north_style,'minimal');assert.equal(persisted.layout.items.scale_bar.scale_style,'Double Box');assert.equal(persisted.font,'sans');
  const report={desktop:'passed',version:require('../package.json').version,platform:process.platform,arch:process.arch,packaged:!!process.env.GAIA_PACKAGED_EXECUTABLE,layers:count,font:analysis.font,userData,checks:['private-API','QGIS-analysis','installed-font-catalog','native-style-scene','offline-natural-language-styles','manual-style-and-font-controls','PDF-export','native-file-save','interactive-map','restart-preserves-layers-and-style-and-font']};
  fs.writeFileSync(path.resolve(__dirname,'../../.desktop-build/qa/smoke-'+process.platform+'-'+process.arch+(report.packaged?'-packaged':'-development')+'.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
 }catch(error){
  const qa=path.resolve(__dirname,'../../.desktop-build/qa');fs.mkdirSync(qa,{recursive:true});
  for(const file of ['desktop.log','desktop.log.previous']){const source=path.join(userData,'logs',file);if(fs.existsSync(source))fs.copyFileSync(source,path.join(qa,file))}
  const page=app.windows()[0];if(page)await page.screenshot({path:path.join(qa,'failure.png')}).catch(()=>{});
  throw error;
 }finally{clearTimeout(watchdog);await app.close()}
})().catch(error=>{console.error(error);process.exit(1)});
