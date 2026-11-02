// Inspect the actual packaged bundle, including its OS icon and display name.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process'),crypto=require('node:crypto');
const app=path.resolve(process.argv[2]),arch=process.argv[3]||process.arch;
const root=path.resolve(__dirname,'../..'),resources=path.join(app,'Contents/Resources');
const plist=key=>execFileSync('/usr/bin/plutil',['-extract',key,'raw','-o','-',path.join(app,'Contents/Info.plist')],{encoding:'utf8'}).trim();
const hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
assert.equal(plist('CFBundleDisplayName'),'GAIA');assert.equal(plist('CFBundleName'),'GAIA');
assert.equal(plist('CFBundleIdentifier'),'org.gaia.geospatial');assert.equal(plist('CFBundleShortVersionString'),require('../package.json').version);
const icon=path.join(resources,plist('CFBundleIconFile'));
assert.equal(hash(icon),hash(path.join(root,'.desktop-build/icons/icon.icns')));
assert.equal(hash(path.join(resources,'gaia-icon.png')),hash(path.join(root,'frontend/public/gaia-icon.png')));
const binary=path.join(app,'Contents/MacOS',plist('CFBundleExecutable'));
const binaryArch=execFileSync('/usr/bin/lipo',['-archs',binary],{encoding:'utf8'}).trim();
assert.equal(binaryArch,arch==='x64'?'x86_64':arch);
const report={passed:true,name:'GAIA',version:plist('CFBundleShortVersionString'),identifier:plist('CFBundleIdentifier'),arch,binaryArch,iconSha256:hash(icon),sourceLogoSha256:hash(path.join(resources,'gaia-icon.png'))};
fs.mkdirSync(path.join(root,'.desktop-build/qa'),{recursive:true});
fs.writeFileSync(path.join(root,'.desktop-build/qa','branding-darwin-'+arch+'.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report));
