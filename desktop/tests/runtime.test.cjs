const {test}=require('node:test');const assert=require('node:assert/strict');const path=require('node:path');
const {executable,environment}=require('../runtime.cjs');
test('runtime paths work for Windows and macOS',()=>{
 assert.equal(executable('/runtime','win32'),path.join('/runtime','python.exe'));
 assert.equal(executable('/runtime','darwin'),path.join('/runtime','bin/python'));
 const env=environment('/runtime',{},'win32');
 assert.equal(env.QGIS_PREFIX_PATH,path.join('/runtime','Library'));assert.equal(env.PYTHONUTF8,'1');
});
test('host Python overrides are not inherited',()=>{
 process.env.PYTHONHOME='/wrong';process.env.PYTHONPATH='/wrong';
 const env=environment('/runtime');
 assert.equal(env.PYTHONHOME,undefined);assert.equal(env.PYTHONPATH,undefined);
 delete process.env.PYTHONHOME;delete process.env.PYTHONPATH;
});
