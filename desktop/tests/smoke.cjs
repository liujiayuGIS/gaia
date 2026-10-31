// Exercises the real Electron window, local API, persistence, and native export.
const {_electron:electron}=require('playwright');const path=require('node:path');const fs=require('node:fs');const os=require('node:os');const assert=require('node:assert/strict');
(async()=>{
 const userData=process.env.GAIA_SMOKE_DATA_DIR||fs.mkdtempSync(path.join(os.tmpdir(),'gaia-desktop-test-'));
 const launch=()=>electron.launch({...(process.env.GAIA_PACKAGED_EXECUTABLE?{executablePath:process.env.GAIA_PACKAGED_EXECUTABLE,args:[]}:{args:[path.resolve(__dirname,'..')]}),
  env:{...process.env,GAIA_DESKTOP_DATA_DIR:userData},timeout:180000});
 let app=await launch();
 try{
  let page=await app.firstWindow();page.setDefaultTimeout(180000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.waitForURL('gaia://app/');await page.getByRole('button',{name:'数据面板',exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>typeof require),'undefined');
  const result=await page.evaluate(async()=>{
   const get=async p=>(await fetch('/api'+p)).json();
   const health=await get('/health');const demo=await fetch('/api/demo',{method:'POST'});
   const layers=await get('/layers');const caps=await get('/capabilities');
   localStorage.setItem('desktop-persistence-test','retained');
   return {health,demo:demo.status,count:layers.length,qgis:caps.plugins?.find(x=>x.id==='qgis')};
  });
  assert(result.health.ok);assert.equal(result.demo,200);assert(result.count>0);
  // Requests outside the private bridge cannot read the user's workspace.
  const readyDir=path.join(userData,'sessions');
  const ready=JSON.parse(fs.readFileSync(path.join(readyDir,fs.readdirSync(readyDir).find(x=>x.endsWith('.json'))),'utf8'));
  assert.equal((await fetch('http://127.0.0.1:'+ready.port+'/api/layers')).status,401);
  await page.reload();await page.waitForSelector('.map-canvas[data-ready="true"]',{timeout:180000});
  fs.mkdirSync(path.resolve(__dirname,'../../.desktop-build/qa'),{recursive:true});
  await page.screenshot({path:path.resolve(__dirname,'../../.desktop-build/qa/desktop-'+process.platform+'-'+process.arch+'.png')});
  assert.deepEqual(errors,[]);
  await app.close();app=await launch();page=await app.firstWindow();await page.waitForURL('gaia://app/',{timeout:180000});
  assert.equal(await page.evaluate(()=>localStorage.getItem('desktop-persistence-test')),'retained');
  const count=await page.evaluate(async()=>(await (await fetch('/api/layers')).json()).length);
  assert.equal(count,result.count);
  console.log(JSON.stringify({desktop:'passed',platform:process.platform,arch:process.arch,layers:count,userData}));
 }finally{await app.close()}
})().catch(error=>{console.error(error);process.exit(1)});
