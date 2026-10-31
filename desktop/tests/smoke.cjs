// Exercises the real Electron window, local API, persistence, and native export.
const {_electron:electron}=require('playwright');const path=require('node:path');const fs=require('node:fs');const os=require('node:os');const assert=require('node:assert/strict');
(async()=>{
 const userData=process.env.GAIA_SMOKE_DATA_DIR||fs.mkdtempSync(path.join(os.tmpdir(),'gaia-desktop-test-'));
 const launch=()=>electron.launch({...(process.env.GAIA_PACKAGED_EXECUTABLE?{executablePath:process.env.GAIA_PACKAGED_EXECUTABLE,args:[]}:{args:[path.resolve(__dirname,'..')]}),
  env:{...process.env,GAIA_DESKTOP_DATA_DIR:userData},timeout:600000});
 const ready=page=>Promise.race([page.waitForURL('gaia://app/',{timeout:600000}),page.locator('#retry').waitFor({state:'visible',timeout:600000}).then(async()=>{throw new Error('Desktop startup: '+await page.locator('#status').innerText())})]);
 console.log('Desktop test data: '+userData);
 let app=await launch();
 try{
  let page=await app.firstWindow();page.setDefaultTimeout(600000);
  const errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error(e.message)});
  page.on('console',e=>{if(e.type()==='error')console.error('Renderer: '+e.text())});
  await ready(page);await page.getByRole('button',{name:'数据面板',exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>typeof require),'undefined');
  const result=await page.evaluate(async()=>{
   const get=async p=>(await fetch('/api'+p)).json();
   const health=await get('/health');const demo=await fetch('/api/demo',{method:'POST'});
   const layers=await get('/layers');const caps=await get('/capabilities');
   localStorage.setItem('desktop-persistence-test','retained');
   return {health,demo:demo.status,count:layers.length,qgis:caps.plugins?.find(x=>x.id==='qgis')};
  });
  assert(result.qgis?.available,JSON.stringify(result.qgis));
  assert(result.health.ok);assert.equal(result.demo,200);assert(result.count>0);
  const analysis=await page.evaluate(async()=>{
   const json=async(url,body,method='POST')=>{const r=await fetch('/api'+url,{method,headers:{'content-type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw new Error(await r.text());return r.json()};
   const layers=await (await fetch('/api/layers')).json();
   const source=layers.find(l=>l.source==='demo'&&l.geometry_types?.includes('Point'));
   const started=await json('/runs',{session_id:'desktop-smoke',message:'Desktop buffer verification',mode:'algorithm',algorithm_id:'buffer',arguments:{layer_id:source.id,distance_m:100}});
   let run;const deadline=Date.now()+240000;
   do{run=await (await fetch('/api/runs/'+started.id)).json();if(!['queued','running'].includes(run.status))break;await new Promise(r=>setTimeout(r,500))}while(Date.now()<deadline);
   if(run.status!=='completed')throw new Error(JSON.stringify(run));
   await json('/layout',{plugin_id:'qgis',title:'GAIA 桌面出图验证',focus_layer_id:run.output_layers[0],map_crs:'EPSG:32650',legend_position:'outside-right'},'PATCH');
   const exported=await json('/layout/export',{format:'pdf',dpi:100});
   const pdf=await (await fetch(exported.url)).arrayBuffer();
   if(new TextDecoder().decode(pdf.slice(0,5))!=='%PDF-')throw new Error('Invalid exported PDF');
   return {count:(await (await fetch('/api/layers')).json()).length,pdf:exported.url};
  });
  result.count=analysis.count;
  const saved=path.resolve(__dirname,'../../.desktop-build/qa/desktop-export-'+process.platform+'.pdf');
  fs.mkdirSync(path.dirname(saved),{recursive:true});
  const downloaded=app.evaluate(({session},file)=>new Promise(resolve=>{
   session.defaultSession.once('will-download',(_,item)=>{item.setSavePath(file);item.once('done',(_,state)=>resolve(state))});
  }),saved);
  await page.evaluate(url=>{const a=document.createElement('a');a.href=url;a.download='GAIA-map.pdf';document.body.appendChild(a);a.click();a.remove()},analysis.pdf);
  assert.equal(await downloaded,'completed');assert.equal(fs.readFileSync(saved).subarray(0,5).toString(),'%PDF-');

  // Requests outside the private bridge cannot read the user's workspace.
  const readyDir=path.join(userData,'sessions');
  const address=JSON.parse(fs.readFileSync(path.join(readyDir,fs.readdirSync(readyDir).filter(x=>x.endsWith('.json')).sort((a,b)=>fs.statSync(path.join(readyDir,b)).mtimeMs-fs.statSync(path.join(readyDir,a)).mtimeMs)[0]),'utf8'));
  assert.equal((await fetch('http://127.0.0.1:'+address.port+'/api/layers')).status,401);
  await page.reload();await page.waitForSelector('.map-canvas[data-ready="true"]',{timeout:600000});
  fs.mkdirSync(path.resolve(__dirname,'../../.desktop-build/qa'),{recursive:true});
  await page.screenshot({path:path.resolve(__dirname,'../../.desktop-build/qa/desktop-'+process.platform+'-'+process.arch+'.png')});
  fs.writeFileSync(path.resolve(__dirname,'../../.desktop-build/qa/smoke-user-data.txt'),userData);
  assert.deepEqual(errors,[]);
  await app.close();app=await launch();page=await app.firstWindow();await ready(page);
  assert.equal(await page.evaluate(()=>localStorage.getItem('desktop-persistence-test')),'retained');
  const count=await page.evaluate(async()=>(await (await fetch('/api/layers')).json()).length);
  assert.equal(count,result.count);
  console.log(JSON.stringify({desktop:'passed',platform:process.platform,arch:process.arch,layers:count,userData}));
 }catch(error){
  const qa=path.resolve(__dirname,'../../.desktop-build/qa');fs.mkdirSync(qa,{recursive:true});
  for(const file of ['desktop.log','desktop.log.previous']){const source=path.join(userData,'logs',file);if(fs.existsSync(source))fs.copyFileSync(source,path.join(qa,file))}
  const page=app.windows()[0];if(page)await page.screenshot({path:path.join(qa,'failure.png')}).catch(()=>{});
  throw error;
 }finally{await app.close()}
})().catch(error=>{console.error(error);process.exit(1)});
