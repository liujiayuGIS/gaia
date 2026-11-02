// Isolate Conda relocation from Electron/Chromium before the full Windows smoke.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const runtime=require('../runtime.cjs');
(async()=>{
 const root=path.resolve(__dirname,'../..'),qa=path.join(root,'.desktop-build/qa');fs.mkdirSync(qa,{recursive:true});
 const userData=fs.mkdtempSync(path.join(os.tmpdir(),'gaia-desktop-probe-'));
 fs.writeFileSync(path.join(qa,'smoke-user-data.txt'),userData);
 try{
  const prefix=await runtime.installRuntime(path.join(root,'.desktop-build'),userData,console.log,console.log);
  console.log('Relocated runtime: '+prefix);
  const env=runtime.environment(prefix,{GEOAGENT_WORKSPACE:path.join(userData,'workspace'),GEOAGENT_CACHE_DIR:path.join(userData,'cache'),GIS_QGIS_PYTHON:runtime.executable(prefix),GIS_PYTHON:runtime.executable(prefix)});
  env.PYTHONPATH=path.join(root,'backend');
  const code="import json\nfrom geoagent.plugins.qgis_plugin import QGISPlugin\nr=QGISPlugin().status()\nprint('RELOCATED_QGIS:'+json.dumps(r),flush=True)\nassert r['available'],r\n";
  await runtime.run(runtime.executable(prefix),['-c',code],{env,cwd:root,log:console.log});
  console.log('Relocated QGIS registry ready without Electron');
  fs.rmSync(path.join(userData,'cache/qgis-catalog.json'),{force:true});
  console.log('Cleared probe catalog so Electron verifies a fresh GIS startup');
 }catch(error){
  const jobs=path.join(userData,'cache/jobs');
  if(fs.existsSync(jobs))for(const job of fs.readdirSync(jobs)){
   const dest=path.join(qa,'relocation-jobs',job);fs.mkdirSync(dest,{recursive:true});
   for(const file of ['stderr.log','stdout.log','request.json']){const src=path.join(jobs,job,file);if(fs.existsSync(src))fs.copyFileSync(src,path.join(dest,file))}
  }
  throw error;
 }
})().catch(error=>{console.error(error);process.exit(1)});
