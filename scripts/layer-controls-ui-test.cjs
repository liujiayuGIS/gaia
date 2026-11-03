// Only run against an isolated qa_layer_order_server.py workspace.
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const {chromium}=require(path.resolve(__dirname,'../desktop/node_modules/playwright'));
const base=process.env.BASE_URL||'http://127.0.0.1:8773',output=path.resolve(__dirname,'../outputs/layer-controls');
(async()=>{
 fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1480,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const layers=await(await page.request.get(base+'/api/layers')).json();assert.equal(layers.length,3);
  await page.goto(base);await page.locator('[data-layer-id]').first().waitFor();
  const separator=page.getByRole('separator',{name:'调整助手宽度'}),dock=page.locator('.assistant-dock');
  const width=async()=>Math.round((await dock.boundingBox()).width);
  async function drag(delta,commit=true){const b=await separator.boundingBox();await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();await page.mouse.move(b.x+delta,b.y+b.height/2,{steps:12});if(!commit)await page.keyboard.press('Escape');await page.mouse.up()}
  const initial=await width();await drag(-195);const wide=await width();assert(wide>initial+180,{initial,wide});
  await page.reload();await separator.waitFor();assert(Math.abs(await width()-wide)<2);
  await drag(110,false);assert(Math.abs(await width()-wide)<2,'Escape restores previous width');
  await separator.focus();await page.keyboard.press('ArrowRight');assert.equal(await width(),wide-24);
  await page.keyboard.press('Home');assert.equal(await width(),320);
  await page.keyboard.press('End');assert.equal(await width(),760);
  await separator.dblclick();assert(Math.abs(await width()-initial)<2);
  await drag(-195);await page.screenshot({path:path.join(output,'wide-assistant.png')});
  await page.getByRole('button',{name:'出图布局',exact:true}).click();
  await page.setViewportSize({width:1120,height:900});await page.waitForTimeout(250);
  assert((await page.locator('.document-area').boundingBox()).width>=439);
  assert((await width())<=453,'Print sidebar and map retain space');
  await page.getByRole('button',{name:'地图',exact:true}).click();await page.setViewportSize({width:1480,height:1000});
  // Delete selected vector, remove its attribute table, and undo by actual API.
  const red=layers.find(x=>x.name==='地块 · 红色'),raster=layers.find(x=>x.kind==='raster');
  const row=id=>page.locator('[data-layer-id="'+id+'"]');
  await row(red.id).locator('.tree-name').click();
  await row(red.id).getByRole('button',{name:'删除图层 '+red.name,exact:true}).click();
  await row(red.id).waitFor({state:'detached'});
  assert(!(await(await page.request.get(base+'/api/layers')).json()).some(x=>x.id===red.id));
  await page.getByRole('button',{name:'撤销删除',exact:true}).click();await row(red.id).waitFor();
  // A failed delete must leave the real layer and the UI intact.
  await page.route('**/api/layers/'+red.id,route=>route.request().method()==='DELETE'?route.fulfill({status:503,contentType:'application/json',body:'{"detail":"测试删除失败"}'}):route.continue());
  await row(red.id).getByRole('button',{name:'删除图层 '+red.name,exact:true}).click();
  await page.getByText('测试删除失败',{exact:true}).waitFor();assert(await row(red.id).isVisible());await page.unroute('**/api/layers/'+red.id);
  // Native-language requests share the registered remove/restore tools.
  async function say(message,name){
   await page.getByLabel('自然语言任务').fill(message);await page.getByRole('button',{name:'发送任务',exact:true}).click();
   await page.waitForFunction(()=>document.querySelector('.statusbar')?.textContent.includes('就绪'));
   await page.waitForFunction(async name=>{const runs=await(await fetch('/api/runs')).json();if(!runs.length)return false;const run=await(await fetch('/api/runs/'+runs[0].id)).json();return run.status==='completed'&&run.events.some(e=>e.type==='tool_completed'&&e.data.name===name&&e.data.result.success)},name);
  }
  await say('删除图层 '+red.name,'remove_layer');await row(red.id).waitFor({state:'detached'});
  await say('恢复图层 '+red.name,'restore_layer');await row(red.id).waitFor();
  await row(raster.id).getByRole('button',{name:'删除图层 '+raster.name,exact:true}).click();await row(raster.id).waitFor({state:'detached'});
  await page.reload();await row(red.id).waitFor();assert.equal(await row(raster.id).count(),0);
  await page.getByRole('button',{name:'外观设置',exact:true}).click();await page.getByRole('button',{name:'深色',exact:true}).click();await page.getByRole('button',{name:'数据面板',exact:true}).click();
  await page.screenshot({path:path.join(output,'dark.png')});
  await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'数据与工具',exact:true}).click();
  assert(await separator.isHidden());assert(await row(red.id).getByRole('button',{name:'删除图层 '+red.name,exact:true}).isVisible());
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
  await page.screenshot({path:path.join(output,'mobile.png')});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({passed:true,checks:['pointer-resize','persistent-width','escape-cancel','keyboard-and-reset','print-map-clearance','delete-and-undo','failed-delete-preserves-layer','natural-language-remove-restore','raster-removal-persists','dark-and-narrow-ui'],initialWidth:initial,wideWidth:wide},null,2));
  console.log(fs.readFileSync(path.join(output,'result.json'),'utf8'));
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
