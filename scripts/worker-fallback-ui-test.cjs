// Reproduce an asynchronous worker failure at a small Windows-like viewport.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
const base=process.env.BASE_URL||'http://127.0.0.1:8767';
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});try{
 const context=await browser.newContext({viewport:{width:1008,height:650}});let blocked=0;
 await context.route('**/maplibre-gl-worker-*.mjs',route=>{blocked++;return route.abort()});
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.locator('.atlas-workbench').waitFor();
 await page.waitForSelector('.map-canvas[data-renderer="leaflet"][data-ready="true"]',{timeout:60000});
 assert(blocked>0,'A real worker request must fail');
 await page.getByRole('button',{name:'布局',exact:true}).click();
 await page.waitForSelector('.layout-page .layout-item',{timeout:90000});
 await page.getByRole('button',{name:'数据与工具',exact:true}).click();
 await page.locator('.contents-tree').getByRole('button',{name:'指北针',exact:true}).click();
 await page.getByRole('button',{name:'指北针 极简线形',exact:true}).click();
 await page.evaluate(async()=>{for(let i=0;i<100;i++){const l=await (await fetch('/api/layout')).json();if(l.items.north_arrow?.north_style==='minimal')return;await new Promise(r=>setTimeout(r,150))}throw Error('Style not persisted')});
 await page.getByRole('button',{name:'数据面板',exact:true}).click();
 await page.locator('.contents-tree').getByRole('button',{name:'标题',exact:true}).click();
 await page.getByLabel('元素字体',{exact:true}).selectOption('Noto Sans CJK SC');
 const fonts=await page.evaluate(async()=>{const faces=await document.fonts.load('20px "Noto Sans CJK SC"','盖亚地理空间');return faces.map(f=>({family:f.family,status:f.status}))});
 assert(fonts.some(f=>f.status==='loaded'),'Bundled browser font must actually load');
 fs.mkdirSync('outputs/worker-fallback',{recursive:true});await page.screenshot({path:'outputs/worker-fallback/compact-controls.png'});
 assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)));
 assert.deepEqual(errors,[]);
 const result={passed:true,blockedWorkerRequests:blocked,fonts,checks:['async-worker-failure','usable-Leaflet-raster-and-vector-map','1008px-responsive-navigation','layout-style-save','bundled-font-load'],errors};
 fs.writeFileSync('outputs/worker-fallback/result.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exit(1)});
