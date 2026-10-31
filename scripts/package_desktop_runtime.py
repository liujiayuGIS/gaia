"""Build a relocatable offline runtime on the SAME OS/CPU as the installer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--prefix',type=Path,default=ROOT/'.runtime/desktop-env')
    parser.add_argument('--mamba',default='micromamba')
    parser.add_argument('--skip-create',action='store_true')
    args=parser.parse_args();prefix=args.prefix.resolve()
    target=ROOT/'.desktop-build/runtime';target.mkdir(parents=True,exist_ok=True)
    if not args.skip_create:
        subprocess.run([args.mamba,'create','--no-rc','-y','-p',str(prefix),'-f',str(ROOT/'desktop/environment.yml'),'--strict-channel-priority'],check=True)
    python=prefix/('python.exe' if sys.platform=='win32' else 'bin/python')
    subprocess.run([str(python),'-m','pip','install','-r',str(ROOT/'desktop/requirements-app.txt')],check=True)
    licenses=target/'licenses';licenses.mkdir(exist_ok=True)
    packages=[]
    for metadata in sorted((prefix/'conda-meta').glob('*.json')):
        item=json.loads(metadata.read_text())
        packages.append({k:item.get(k) for k in ('name','version','build','channel','url','sha256','license')})
        source=Path(item.get('link',{}).get('source',''))/'info'
        if source.is_dir():
            dest=licenses/(item['name']+'-'+item['version'])
            for name in ('licenses','recipe','about.json','index.json'):
                src=source/name
                if src.is_dir():shutil.copytree(src,dest/name,dirs_exist_ok=True)
                elif src.is_file():dest.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest/name)
    (licenses/'conda-packages.json').write_text(json.dumps(packages,indent=2))
    freeze=subprocess.check_output([str(python),'-m','pip','freeze'],text=True)
    (licenses/'python-packages.txt').write_text(freeze)
    # Include package license texts without shipping caches or application secrets.
    site=prefix/('Lib/site-packages' if sys.platform=='win32' else 'lib/python3.12/site-packages')
    for folder in site.glob('*.dist-info'):
        for pattern in ('LICENSE*','COPYING*','licenses'):
            for src in folder.glob(pattern):
                dest=licenses/'python'/folder.name/src.name;dest.parent.mkdir(parents=True,exist_ok=True)
                if src.is_dir():shutil.copytree(src,dest,dirs_exist_ok=True)
                else:shutil.copy2(src,dest)
    archive=target/'runtime.tar.gz'
    subprocess.run([str(python),'-c','from conda_pack.cli import main; main()','-p',str(prefix),'-o',str(archive),'--force','--n-threads','4'],check=True)
    with archive.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    manifest={'schema':1,'platform':sys.platform,'arch':'arm64' if platform.machine().lower() in ('arm64','aarch64') else 'x64',
              'python':'3.12','qgis':'3.44.14','sha256':sha,'bytes':archive.stat().st_size}
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2))
    from PIL import Image
    icons=ROOT/'.desktop-build/icons';icons.mkdir(exist_ok=True)
    image=Image.open(ROOT/'frontend/public/gaia-icon.png').convert('RGBA').resize((1024,1024),Image.Resampling.LANCZOS)
    image.save(icons/'icon.png');image.save(icons/'icon.icns');image.save(icons/'icon.ico',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
    print(json.dumps(manifest))


if __name__=='__main__':main()
