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
  const fixture=path.resolve(__dirname,'../../.desktop-build/qa/import-fixtures');
  const files=fs.readdirSync(fixture).filter(name=>/\.(shp|shx|dbf|prj|cpg)$/i.test(name)).map(name=>({name,bytes:[...fs.readFileSync(path.join(fixture,name))]}));
  const imported=await page.evaluate(async files=>{
   const body=new FormData();for(const file of files)body.append('files',new Blob([new Uint8Array(file.bytes)]),file.name);
   let response=await fetch('/api/imports',{method:'POST',body});if(!response.ok)throw new Error(await response.text());
   const asset=await response.json();response=await fetch('/api/imports/'+asset.id+'/load',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({encoding:'UTF-8'})});
   if(!response.ok)throw new Error(await response.text());
   const layer=await response.json();const data=await(await fetch('/api/layers/'+layer.id+'/data')).json();
   if(data.features[0].properties.f1_1!=='钟楼站'||data.features[0].properties.field_1!==11)throw new Error('Imported attribute values changed');
   return layer;
  },files);
  assert.equal(imported.count,1);assert(imported.fields.includes('f1_1'));assert(imported.import_warnings?.length);
  assert.equal(imported.provenance.field_name_repairs[0].alias,'f1_1');
  console.log('Chinese Shapefile paths, truncated field alias and preserved import warning passed');
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
   return {runId:run.id,count:(await (await fetch('/api/layers')).json()).length,pdf:exported.url,font:styles.default_font,scaleStyles:styles.scale_styles.map(s=>s.id)};
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
  let narrow=await page.locator('.mobile-navigation').isVisible();
  if(narrow)await page.getByRole('button',{name:'数据与工具',exact:true}).click();
  const fixtureRow=page.locator('[data-layer-id="'+imported.id+'"]');
  await fixtureRow.getByRole('button',{name:'删除图层 '+imported.name,exact:true}).click();
  await fixtureRow.waitFor({state:'detached'});
  await page.getByRole('button',{name:'撤销删除',exact:true}).click();await fixtureRow.waitFor();
  // The same removal is executable through the agent, without a model account.
  await page.evaluate(async layer=>{
   const response=await fetch('/api/runs',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({session_id:'desktop-smoke',mode:'offline',message:'删除图层 '+layer.name})});
   if(!response.ok)throw new Error(await response.text());const started=await response.json();
   const deadline=Date.now()+30000;
   while(Date.now()<deadline){const run=await(await fetch('/api/runs/'+started.id)).json();if(!['queued','running'].includes(run.status)){if(run.status!=='completed'||!run.events.some(e=>e.type==='tool_completed'&&e.data.name==='remove_layer'&&e.data.result.success))throw new Error(JSON.stringify(run));return}await new Promise(r=>setTimeout(r,150))}
   throw new Error('Layer removal did not settle');
  },imported);
  result.count-=1;
  await page.reload();await page.locator('.atlas-workbench').waitFor();
  // macOS hosted runners have a 1024px display and clamp native windows.
  // Exercise the deliberately desktop-only separator in an explicit wide
  // renderer viewport, while the earlier delete/undo still covers native size.
  await page.setViewportSize({width:1480,height:960});
  narrow=await page.locator('.mobile-navigation').isVisible();assert.equal(narrow,false);
  const separator=page.getByRole('separator',{name:'调整助手宽度'});
  const b=await separator.boundingBox();assert(b,'Desktop assistant separator must be visible');
  const beforeWidth=(await page.locator('.assistant-dock').boundingBox()).width;
  await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();await page.mouse.move(b.x-76,b.y+b.height/2,{steps:12});await page.mouse.up();
  const assistantWidth=await page.evaluate(()=>Number(localStorage.getItem('gaia-assistant-width-v1')));
  assert(assistantWidth>beforeWidth+60);
  assert.equal(await page.evaluate(async id=>(await(await fetch('/api/layers')).json()).some(x=>x.id===id),imported.id),false);
  console.log('Layer delete, undo, natural-language removal and assistant pointer resize passed');
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
  await page.getByTitle('模型设置',{exact:true}).first().click();
  const settings=page.getByRole('dialog',{name:'模型与运行设置'});
  await settings.getByRole('button',{name:'连接模型',exact:false}).click();
  await settings.getByLabel('每轮输出预算',{exact:true}).selectOption('16384');
  await settings.getByRole('button',{name:'离线指令',exact:false}).click();
  await settings.getByRole('button',{name:'应用设置',exact:true}).click();
  console.log('Model output budget control passed without a model request');
  await page.getByLabel('助手会话',{exact:true}).selectOption('desktop-smoke');
  const originalMessage=page.locator('[data-run-id="'+analysis.runId+'"]');
  const questionActions=originalMessage.getByRole('group',{name:'提问操作',exact:true}),answerActions=originalMessage.getByRole('group',{name:'回答操作',exact:true});
  await questionActions.getByRole('button',{name:'复制提问',exact:true}).click();
  assert.equal(await app.evaluate(async({clipboard})=>await clipboard.readText()),'Desktop buffer verification');
  await answerActions.getByRole('button',{name:'复制回答',exact:true}).click();
  const copiedAnswer=await app.evaluate(async({clipboard})=>await clipboard.readText());assert(copiedAnswer.includes('算法已完成'));
  await answerActions.getByRole('button',{name:'引用回复',exact:true}).click();
  await page.getByText('回复引用 · GAIA 回答',{exact:true}).waitFor();
  await page.getByRole('button',{name:'取消引用或编辑',exact:true}).click();
  await questionActions.getByRole('button',{name:'编辑为新提问',exact:true}).click();
  assert.equal(await page.getByLabel('自然语言任务',{exact:true}).inputValue(),'Desktop buffer verification');
  await page.getByRole('button',{name:'取消引用或编辑',exact:true}).click();
  await answerActions.getByRole('button',{name:'赞同回答',exact:true}).click();
  await page.waitForFunction(id=>document.querySelector('[data-run-id="'+id+'"] [aria-label="赞同回答"]')?.getAttribute('aria-pressed')==='true',analysis.runId);
  const rewrittenRequest=page.waitForResponse(r=>r.url()==='gaia://app/api/runs'&&r.request().method()==='POST');
  await answerActions.getByRole('button',{name:'重新回答',exact:true}).click();const rewrittenId=(await(await rewrittenRequest).json()).id;
  const rewrite=await page.evaluate(async id=>{const deadline=Date.now()+30000;while(Date.now()<deadline){const value=await(await fetch('/api/runs/'+id)).json();if(!['queued','running'].includes(value.status))return value;await new Promise(r=>setTimeout(r,100))}throw new Error('Read-only answer did not settle')},rewrittenId);
  assert.equal(rewrite.status,'completed');assert.equal(rewrite.reanswer_of,analysis.runId);assert.deepEqual(rewrite.steps,[]);
  assert.equal(await page.evaluate(async()=>(await(await fetch('/api/layers')).json()).length),result.count);
  console.log('Question/answer native clipboard, quote, edit, feedback and read-only reanswer passed');
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
  assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('geoagent-preferences-v1')).max_output_tokens),16384);
  assert.equal(await page.evaluate(()=>Number(localStorage.getItem('gaia-assistant-width-v1'))),assistantWidth);
  assert.equal(await page.evaluate(async id=>(await(await fetch('/api/layers')).json()).some(x=>x.id===id),imported.id),false);
  assert.equal(await page.evaluate(async id=>(await(await fetch('/api/runs/'+id)).json()).feedback?.value,analysis.runId),'up');
  const report={desktop:'passed',version:require('../package.json').version,platform:process.platform,arch:process.arch,packaged:!!process.env.GAIA_PACKAGED_EXECUTABLE,layers:count,font:analysis.font,userData,checks:['private-API','QGIS-analysis','Chinese-Shapefile-truncated-field-import','layer-delete-and-undo','natural-language-layer-removal','assistant-pointer-resize','layer-removal-and-assistant-width-persistence','installed-font-catalog','native-style-scene','offline-natural-language-styles','manual-style-and-font-controls','model-output-budget-persistence','PDF-export','native-file-save','interactive-map','question-and-answer-native-clipboard','message-quote-and-edit','message-feedback-persists','read-only-reanswer-no-GIS','restart-preserves-layers-and-style-and-font']};
  fs.writeFileSync(path.resolve(__dirname,'../../.desktop-build/qa/smoke-'+process.platform+'-'+process.arch+(report.packaged?'-packaged':'-development')+'.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
 }catch(error){
  const qa=path.resolve(__dirname,'../../.desktop-build/qa');fs.mkdirSync(qa,{recursive:true});
  for(const kind of ['cache','workspace']){
   const jobs=path.join(userData,kind,'jobs');
   if(fs.existsSync(jobs))for(const job of fs.readdirSync(jobs)){
    const destination=path.join(qa,'desktop-'+kind+'-jobs',job);fs.mkdirSync(destination,{recursive:true});
    for(const file of ['stderr.log','stdout.log','request.json']){const source=path.join(jobs,job,file);if(fs.existsSync(source))fs.copyFileSync(source,path.join(destination,file))}
   }
  }
  for(const file of ['desktop.log','desktop.log.previous']){const source=path.join(userData,'logs',file);if(fs.existsSync(source))fs.copyFileSync(source,path.join(qa,file))}
  const page=app.windows()[0];if(page)await page.screenshot({path:path.join(qa,'failure.png')}).catch(()=>{});
  throw error;
 }finally{clearTimeout(watchdog);await app.close()}
})().catch(error=>{console.error(error);process.exit(1)});
