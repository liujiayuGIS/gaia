// Start scripts/qa_layer_order_server.py first. Never run against a user's workspace.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const fs=require('fs');const assert=require('node:assert/strict');
const base=process.env.BASE_URL||'http://127.0.0.1:8767';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:960}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const getLayers=async()=>(await page.request.get(base+'/api/layers')).json();
  const layers=await getLayers();assert.equal(layers.length,3);
  const blue=layers.find(l=>l.name==='地块 · 蓝色').id,red=layers.find(l=>l.name==='地块 · 红色').id,raster=layers.find(l=>l.kind==='raster').id;
  const initial=[blue,red,raster];await page.request.patch(base+'/api/layers/order',{data:{layer_ids:initial}});
  await page.goto(base);await page.waitForSelector('.map-canvas[data-ready="true"]');
  const row=id=>page.locator(`[data-layer-id="${id}"]`),handle=id=>row(id).locator('.layer-drag-handle');
  async function checkOrder(ids){
   await page.waitForFunction(expected=>JSON.stringify([...document.querySelectorAll('[data-layer-id]')].map(el=>el.dataset.layerId))===JSON.stringify(expected),ids);
   await page.waitForSelector('.layer-list[aria-busy="false"]');
   assert.deepEqual((await getLayers()).map(l=>l.id),ids);
  }
  async function dragAfter(id,target){const a=await handle(id).boundingBox(),b=await row(target).boundingBox();await page.mouse.move(a.x+a.width/2,a.y+a.height/2);await page.mouse.down();await page.mouse.move(b.x+30,b.y+b.height-3,{steps:12});await page.mouse.up()}
  fs.mkdirSync('outputs/layer-order',{recursive:true});
  await page.waitForTimeout(1000);await page.locator('.map-canvas').screenshot({path:'outputs/layer-order/blue-top.png'});
  await dragAfter(blue,raster);await checkOrder([red,raster,blue]);await page.waitForTimeout(400);await page.locator('.map-canvas').screenshot({path:'outputs/layer-order/red-top.png'});
  await page.reload();await page.waitForSelector('.map-canvas[data-ready="true"]');await checkOrder([red,raster,blue]);
  await handle(blue).focus();await page.keyboard.press('Home');await checkOrder(initial);
  await row(blue).locator('.tree-name').click();await page.getByRole('button',{name:'下移图层',exact:true}).click();await checkOrder([red,blue,raster]);
  await page.getByRole('button',{name:'上移图层',exact:true}).click();await checkOrder(initial);
  // Pointer cancellation must discard the pending drop, and allow the next drag.
  const a=await handle(blue).boundingBox(),b=await row(raster).boundingBox();await page.mouse.move(a.x+10,a.y+10);await page.mouse.down();await page.mouse.move(b.x+25,b.y+b.height-3,{steps:8});
  await handle(blue).evaluate(el=>el.dispatchEvent(new PointerEvent('pointercancel',{pointerId:1,bubbles:true})));await page.mouse.up();await checkOrder(initial);
  await dragAfter(blue,raster);await checkOrder([red,raster,blue]);
  // Saving errors restore the authoritative order rather than leaving a false UI state.
  await page.route('**/api/layers/order',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'测试保存失败'})}));
  await handle(blue).focus();await page.keyboard.press('Home');await page.getByText('顺序未保存：',{exact:false}).waitFor();await checkOrder([red,raster,blue]);await page.unroute('**/api/layers/order');
  await handle(raster).focus();await page.keyboard.press('Home');await checkOrder([raster,red,blue]);await page.waitForTimeout(700);await page.locator('.map-canvas').screenshot({path:'outputs/layer-order/raster-top.png'});
  await page.getByRole('button',{name:'关闭提示',exact:true}).click();await page.screenshot({path:'outputs/layer-order/desktop.png'});
  await page.getByRole('button',{name:'外观设置',exact:true}).click();await page.getByRole('button',{name:'深色',exact:true}).click();await page.getByRole('button',{name:'数据面板',exact:true}).click();await page.screenshot({path:'outputs/layer-order/dark.png'});
  await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'数据与工具',exact:true}).click();await page.screenshot({path:'outputs/layer-order/mobile.png'});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2),false);assert.deepEqual(errors,[]);
  // Chromium touch events: the handle supports touch without taking over list scrolling.
  const touch=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});const tp=await touch.newPage();await tp.goto(base);await tp.getByRole('button',{name:'数据与工具',exact:true}).click();await tp.waitForSelector('[data-layer-id]');
  const th=await tp.locator(`[data-layer-id="${raster}"] .layer-drag-handle`).boundingBox(),tr=await tp.locator(`[data-layer-id="${blue}"]`).boundingBox();
  const cdp=await touch.newCDPSession(tp),x=th.x+th.width/2,y=th.y+th.height/2,end=tr.y+tr.height-3;
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x,y}]});for(let i=1;i<=10;i++)await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x,y:y+(end-y)*i/10}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
  await tp.waitForSelector('.layer-list[aria-busy="false"]');assert.deepEqual((await getLayers()).map(l=>l.id),[red,blue,raster]);await touch.close();
  require('node:child_process').execFileSync('.venv/bin/python',['-c',`from PIL import Image
for name,expected in [('blue-top',(36,99,219)),('red-top',(230,54,54)),('raster-top',None)]:
 image=Image.open('outputs/layer-order/'+name+'.png').convert('RGB')
 pixel=image.getpixel((image.width//2,image.height//2))
 assert pixel==expected if expected else pixel not in [(36,99,219),(230,54,54)],(name,pixel)
`]);
  console.log('Layer order UI passed: mouse drag, keyboard, buttons, refresh, cancellation, save rollback, themes, narrow viewport and Chromium touch.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
