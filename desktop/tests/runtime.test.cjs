const {test}=require('node:test');const assert=require('node:assert/strict');const path=require('node:path');
const {executable,environment}=require('../runtime.cjs');
const fs=require('node:fs/promises');const os=require('node:os');const tar=require('tar');
const {extractRuntime,validateWindowsArchive,windowsEntrySafe}=require('../runtime.cjs');
test('native Windows extraction rejects path escapes, devices, and links',async()=>{
 for(const name of ['../escape','C:/escape','\\\\server\\share','safe/../escape','safe/file:stream','safe/.. /escape','NUL.txt'])
  assert.equal(windowsEntrySafe({path:name,type:'File'}),false,name);
 assert.equal(windowsEntrySafe({path:'Library/bin/python.dll',type:'File'}),true);
 assert.equal(windowsEntrySafe({path:'link',type:'SymbolicLink'}),false);
 assert.equal(windowsEntrySafe({path:'link',type:'Link'}),false);
 const root=await fs.mkdtemp(path.join(os.tmpdir(),'gaia-windows-tar-'));
 try{
  await fs.writeFile(path.join(root,'runtime.txt'),'runtime');
  const file=path.join(root,'env.tar.gz');await tar.c({file,gzip:true,cwd:root},['runtime.txt']);
  await validateWindowsArchive(file);
 }finally{await fs.rm(root,{recursive:true,force:true})}
});
test('Conda symlink chains extract without writing through links',{skip:process.platform==='win32'},async()=>{
 const tmp=await fs.mkdtemp(path.join(os.tmpdir(),'gaia-tar-'));
 try{
  const source=path.join(tmp,'source'),out=path.join(tmp,'out');
  await fs.mkdir(path.join(source,'lib/icu/78'),{recursive:true});await fs.mkdir(out);
  await fs.writeFile(path.join(source,'lib/icu/78/pkgdata.inc'),'ok');
  await fs.symlink('78',path.join(source,'lib/icu/current'));
  await fs.symlink('current/pkgdata.inc',path.join(source,'lib/icu/pkgdata.inc'));
  const archive=path.join(tmp,'env.tgz');await tar.c({file:archive,gzip:true,cwd:source},['lib']);
  await extractRuntime(archive,await fs.realpath(out));
  assert.equal(await fs.readFile(path.join(out,'lib/icu/pkgdata.inc'),'utf8'),'ok');
  await fs.symlink('../../escape',path.join(source,'bad'));await tar.c({file:archive,gzip:true,cwd:source},['bad']);
  await assert.rejects(extractRuntime(archive,await fs.realpath(out)),/Unsafe archive link/);
 }finally{await fs.rm(tmp,{recursive:true,force:true})}
});
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
