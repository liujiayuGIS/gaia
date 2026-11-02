// Run against scripts/qa_quality_server.py in an isolated workspace.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');const fs=require('node:fs');
const base=process.env.BASE_URL||'http://127.0.0.1:8767';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  fs.mkdirSync('outputs/atlas-ui',{recursive:true});
  const screenshot=async name=>{const close=page.getByRole('button',{name:'关闭提示',exact:true});if(await close.isVisible())await close.click();await page.waitForTimeout(250);return page.screenshot({path:'outputs/atlas-ui/'+name+'.png',animations:'disabled'})};
  const layers=await (await page.request.get(base+'/api/layers')).json();
  assert(layers.some(l=>l.kind==='raster'),'Use the real public-data QA fixture');
  await page.goto(base);await page.waitForSelector('.map-canvas[data-ready="true"]',{timeout:90000});
  await page.getByRole('heading',{name:'GAIA 助手',exact:true}).waitFor();
  await page.getByRole('button',{name:'收起数据面板',exact:true}).click();
  assert(await page.locator('.layer-palette').isHidden());
  await page.getByRole('button',{name:'展开数据面板',exact:true}).click();
  assert(await page.locator('.layer-palette').isVisible());
  await page.keyboard.press('Control+k');await page.getByRole('dialog',{name:'搜索图层与工具'}).waitFor();
  await page.getByLabel('全局搜索').fill('native:centroids');
  await page.locator('.command-results>button').first().click();
  await page.getByLabel('输出数据名称').fill('Atlas 验收 · 质心');
  await page.getByRole('button',{name:'运行',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.statusbar').textContent.includes('正在处理'));
  await page.waitForFunction(()=>document.querySelector('.statusbar').textContent.includes('就绪'),{timeout:90000});
  const runs=await (await page.request.get(base+'/api/runs')).json(),run=await (await page.request.get(base+'/api/runs/'+runs[0].id)).json();
  assert.equal(run.status,'completed',run.message);
  await page.getByRole('button',{name:'展开分析流程',exact:true}).click();
  await page.locator('.process-track button').first().waitFor();
  const actual=run.events.filter(e=>e.type==='tool_started');
  assert.equal(await page.locator('.process-track button').count(),actual.length);
  await page.locator('.process-track button').last().click();
  await page.locator('.process-detail summary').click();
  assert((await page.locator('.process-detail pre').innerText()).includes('arguments'));
  await page.waitForFunction(()=>{
   const p=document.querySelector('.layer-palette').getBoundingClientRect(),d=document.querySelector('.process-drawer').getBoundingClientRect();
   return p.bottom<d.top;
  },null,{timeout:5000});
  const drawer=await page.locator('.process-drawer').boundingBox(),palette=await page.locator('.layer-palette').boundingBox();
  assert(palette.y+palette.height<drawer.y,'Expanded drawer must not hide the input panel');
  await page.getByRole('button',{name:'查看输出图层',exact:true}).click();
  const outputId=run.output_layers.at(-1);
  const outputLayers=await (await page.request.get(base+'/api/layers')).json();
  await page.locator('.composer-context').filter({hasText:outputLayers.find(l=>l.id===outputId).name}).waitFor();
  await screenshot('process');
  await page.getByRole('button',{name:'收起分析流程',exact:true}).click();
  await page.getByRole('button',{name:'数据面板',exact:true}).click();
  const dem=layers.find(l=>l.kind==='raster');
  await page.locator('[data-layer-id="'+dem.id+'"] .tree-name').dblclick();
  await page.waitForTimeout(900);await screenshot('map');

  await page.getByRole('button',{name:'出图布局',exact:true}).click();
  await page.waitForSelector('.layout-page .layout-item',{timeout:90000});
  await page.getByRole('img',{name:'当前地图版式预览'}).waitFor();
  assert(await page.locator('.layout-page-thumb svg image').count()>0);
  await screenshot('folio');
  await page.getByRole('button',{name:'导出布局',exact:true}).click();
  await page.getByRole('dialog',{name:'导出地图成果'}).getByRole('combobox').last().selectOption('100');
  const [download]=await Promise.all([page.waitForEvent('download',{timeout:90000}),page.getByRole('button',{name:'导出并下载',exact:true}).click()]);
  await download.saveAs('outputs/atlas-ui/verified-map.pdf');
  assert.equal(fs.readFileSync('outputs/atlas-ui/verified-map.pdf').subarray(0,5).toString(),'%PDF-');

  await page.getByRole('button',{name:'地图',exact:true}).click();
  await page.getByRole('button',{name:'外观设置',exact:true}).click();
  await page.getByRole('button',{name:'深色',exact:true}).click();
  await page.getByLabel('工作区强调色').fill('#d97757');
  await page.getByRole('button',{name:'数据面板',exact:true}).click();
  await page.waitForTimeout(900);
  const contrast=await page.evaluate(()=>{
   const rgb=s=>s.match(/[\d.]+/g).slice(0,3).map(Number);
   const lum=s=>{const a=rgb(s).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});return a[0]*.2126+a[1]*.7152+a[2]*.0722};
   const c=getComputedStyle(document.querySelector('.assistant-composer .primary'));
   const a=lum(c.color),b=lum(c.backgroundColor);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
  });assert(contrast>=4.5,'Custom accent primary label contrast: '+contrast);
  await screenshot('dark');
  await page.reload();await page.waitForFunction(()=>document.querySelector('.workbench')?.dataset.theme==='dark');
  await page.getByRole('button',{name:'外观设置',exact:true}).click();
  await page.getByRole('button',{name:'恢复默认',exact:true}).click();
  await page.getByRole('button',{name:'数据面板',exact:true}).click();
  await page.setViewportSize({width:1100,height:820});await page.waitForTimeout(1000);await screenshot('compact');
  assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)));
  assert(await page.locator('.assistant-dock').isVisible());

  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button',{name:'地图 / 布局',exact:true}).click();
  await page.getByRole('button',{name:'布局',exact:true}).click();
  await page.waitForSelector('.layout-page .layout-item',{timeout:90000});
  const exp=await page.getByRole('button',{name:'导出布局',exact:true}).boundingBox();
  await screenshot('mobile-folio');
  assert(exp.x>=0&&exp.x+exp.width<=390,'Mobile export remains immediately reachable');
  await page.getByRole('button',{name:'GAIA 助手',exact:true}).click();await screenshot('mobile-assistant');
  await page.getByRole('button',{name:'数据与工具',exact:true}).click();await screenshot('mobile-data');
  assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)));
  assert.deepEqual(errors,[]);
  const result={passed:true,toolSteps:actual.length,accentContrast:contrast,checks:['floating-palette','command-search-to-native-parameters','real-QGIS-output','actual-event-drawer','drawer-panel-clearance','native-scene-thumbnail','PDF-download','custom-accent-contrast','theme-persistence','compact-desktop','mobile-export-and-panes'],errors};
  fs.writeFileSync('outputs/atlas-ui/result.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
