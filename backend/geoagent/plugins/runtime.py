"""Separate processes with workspace-only data access, no inherited API secrets."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
CODE = Path(__file__).resolve().parent


def cache_root():
    return Path(os.environ.get('GEOAGENT_CACHE_DIR',ROOT/'.runtime'))


def python_executable():
    return Path(os.environ.get('GIS_PYTHON',sys.executable))


def runtime_prefix(python):
    return python.parent if python.name.lower().endswith('.exe') else python.parent.parent


def qgis_python():
    configured = os.environ.get('GIS_QGIS_PYTHON')
    candidates = [Path(configured)] if configured else [ROOT/'.runtime/qgis/bin/python',ROOT/'.runtime/qgis/python.exe',
        Path('/Applications/QGIS.app/Contents/MacOS/bin/python3')]
    return next((x for x in candidates if x.is_file()), None)


def job_folder(store):
    path=store.root/'jobs'/uuid.uuid4().hex
    for name in ('inputs','outputs','tmp','cache','config'):(path/name).mkdir(parents=True,exist_ok=True)
    return path.resolve()


def copy_inputs(store, bindings, job):
    from ..formats import raster_path
    paths={};metadata={}
    for alias, layer_id in bindings.items():
        layer=store.get_layer(layer_id)
        if layer.get('kind')=='raster':source=raster_path(store,layer_id)
        else:
            native=store.root/'layers'/f'{layer_id}.gpkg'
            source=native if native.exists() else store.root/'layers'/f'{layer_id}.geojson'
        target=job/'inputs'/(layer_id+source.suffix)
        shutil.copy2(source,target)
        paths[alias]=str(target);metadata[alias]=layer
    return paths,metadata


def execute(python, worker, request, job, cancel=None, timeout=120, restricted=True):
    python=Path(python).absolute();prefix=runtime_prefix(python)
    qgis_prefix=prefix/'Library' if sys.platform=='win32' else prefix
    paths=[prefix,prefix/'Library/bin',prefix/'Scripts',prefix/'bin']
    paths+=([Path(os.environ.get('SystemRoot','C:/Windows'))/'System32'] if sys.platform=='win32' else [Path('/usr/bin'),Path('/bin')])
    env={'PATH':os.pathsep.join(map(str,paths)),'LANG':'en_US.UTF-8',
        'TMPDIR':str(job/'tmp'),'XDG_CACHE_HOME':str(job/'cache'),'XDG_CONFIG_HOME':str(job/'config'),
        'MPLCONFIGDIR':str(job/'cache/matplotlib'),'QT_QPA_PLATFORM':'offscreen',
        'QGIS_PREFIX_PATH':str(qgis_prefix),'QGIS_CUSTOM_CONFIG_PATH':str(job/'config'),
        'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','PYTHONUTF8':'1'}
    if sys.platform=='win32':
        env.update(SystemRoot=os.environ.get('SystemRoot','C:/Windows'),TEMP=str(job/'tmp'),TMP=str(job/'tmp'),
                   USERPROFILE=str(job/'config'),APPDATA=str(job/'config'),LOCALAPPDATA=str(job/'cache'))
    for folder in (qgis_prefix/'plugins',qgis_prefix/'lib/qt6/plugins',qgis_prefix/'lib/qt/plugins'):
        if folder.exists():env['QT_PLUGIN_PATH']=str(folder);break
    for key,folder in [('GDAL_DATA',qgis_prefix/'share/gdal'),('PROJ_DATA',qgis_prefix/'share/proj')]:
        if folder.exists():env[key]=str(folder)
    request={**request,'job':str(job),'timeout':timeout}
    request_path=job/'request.json';request_path.write_text(json.dumps(request,ensure_ascii=False))
    command=[str(python),'-I','-B','-X','utf8',str(CODE/worker),str(request_path)]
    sandbox='none'
    windows_sandbox=restricted and sys.platform=='win32'
    if restricted and not windows_sandbox:
        if sys.platform!='darwin' or not shutil.which('sandbox-exec'):
            raise ValueError('此主机缺少操作系统代码沙箱；请配置受限运行器后再执行自定义代码。')
        readable=[str(prefix),str(Path(python).resolve().parent.parent),str(CODE),str(job),sys.base_prefix,'/System/Library','/System/Cryptexes','/System/Volumes/Preboot/Cryptexes','/usr','/Library/Fonts',
                  '/Library/Frameworks','/private/var/db/timezone','/private/etc','/dev']
        rules='\n'.join('(subpath '+json.dumps(str(Path(x).resolve()))+')' for x in readable)
        profile='(version 1)\n(deny default)\n(allow process*)\n(allow sysctl-read)\n(allow mach-lookup)\n(allow signal (target self))\n(allow file-read-metadata)\n(allow file-map-executable)\n(allow file-read* (literal "/") '+rules+')\n(allow file-write* (subpath '+json.dumps(str(job))+') (literal "/dev/null"))\n(allow ipc-posix-shm ipc-posix-sem)\n'
        profile_path=job/'sandbox.sb';profile_path.write_text(profile)
        command=['/usr/bin/sandbox-exec','-f',str(profile_path),*command]
        sandbox='macOS Seatbelt: job-only writes, explicit runtime reads, network denied'
    stdout_path=job/'stdout.log';stderr_path=job/'stderr.log'
    with stdout_path.open('wb') as stdout,stderr_path.open('wb') as stderr:
        if windows_sandbox:
            from .windows_sandbox import launch
            process=launch(command,job,env,stdout,stderr,[prefix,CODE],timeout)
            sandbox='Windows AppContainer: no network, job and private container writes only'
        else:process=subprocess.Popen(command,cwd=job,env=env,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,
                                      start_new_session=sys.platform!='win32',
                                      creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
        start=time.monotonic()
        try:
            while process.poll() is None:
                if cancel and cancel.is_set():raise InterruptedError('任务已停止。')
                if time.monotonic()-start>timeout:
                    stages=[line for line in stderr_path.read_text(errors='replace').splitlines() if line.startswith('QGIS initializing ')]
                    raise TimeoutError(f'执行超过 {timeout} 秒，已停止。'+(' 最后阶段：'+stages[-1] if stages else ''))
                if stdout_path.stat().st_size+stderr_path.stat().st_size>2*1024*1024:
                    raise ValueError('执行日志超过2MB，已停止。')
                time.sleep(.1)
        except BaseException:
            try:
                if sys.platform=='win32':process.kill()
                else:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait();raise
        finally:
            if windows_sandbox:process.close()
    if stdout_path.stat().st_size+stderr_path.stat().st_size>2*1024*1024:raise ValueError('执行日志超过2MB。')
    lines=stdout_path.read_text(errors='replace').splitlines()
    result=next((json.loads(x[len('GEOAGENT_RESULT:'):]) for x in reversed(lines) if x.startswith('GEOAGENT_RESULT:')),None)
    if not result:
        detail=stderr_path.read_text(errors='replace')[-2500:]
        raise ValueError(f'插件进程失败（退出码 {process.returncode}）：{detail}')
    if process.returncode!=0:raise ValueError(f'插件进程异常退出：{process.returncode}')
    if not result.get('ok'):raise ValueError(result.get('error','插件执行失败。'))
    return {**result['data'],'sandbox':sandbox,'duration_ms':round((time.monotonic()-start)*1000),'job_id':job.name}


def publish(store, payload, run_id, plugin_id, inputs, extra=None):
    from .. import formats
    from ..store import now
    layers=[];artifacts=[]
    provenance={'run_id':run_id,'plugin':plugin_id,'input_layers':list(inputs.values()),
        'input_sha256':[store.get_layer(x)['sha256'] for x in inputs.values()],**(extra or {})}
    for output in payload.get('outputs',[]):
        path=Path(output['path']).resolve()
        if not path.is_file() or path.is_symlink():raise ValueError('插件返回了不存在的输出或符号链接。')
        jobs=(store.root/'jobs').resolve()
        if not path.is_relative_to(jobs):raise ValueError('插件输出必须位于本次作业目录。')
        if path.stat().st_size>250*1024*1024:raise ValueError('插件输出超出250MB限制。')
        if path.suffix.lower() in {'.gpkg','.geojson','.json','.shp','.fgb','.parquet','.kml','.gml','.tif','.tiff'}:
            asset=formats.stage_files(store,[(path.name,path.read_bytes())])
            try:
                layer=formats.import_asset(store,asset['id'],run_id=run_id)
                layer=store.patch_layer(layer['id'],{'source':'analysis','name':output.get('name',path.stem),
                    'provenance':{**layer.get('provenance',{}),**provenance}})
                layers.append(layer)
            except ValueError:
                # A file remains downloadable if the 2D preview cannot represent its native data.
                if not output.get('allow_file_only'):raise
        export_id=uuid.uuid4().hex
        item={'id':export_id,'name':output.get('name',path.stem)+path.suffix,'path':str(path.relative_to(store.root.resolve())),
              'created_at':now(),'run_id':run_id,'format':path.suffix[1:],'plugin':plugin_id,'url':f'/api/exports/{export_id}/download'}
        store.put_object('exports',export_id,item);artifacts.append(item)
    answer={'layers':[{'layer_id':x['id'],'name':x['name'],'count':x['count']} for x in layers],
        'artifacts':artifacts,'scalars':payload.get('scalars',{}),'plugin':plugin_id,
        'validation':{'outputs_exist':True,'input_hashes_recorded':True},
        'sandbox':payload.get('sandbox'),'job_id':payload.get('job_id')}
    if layers:answer.update(layer_id=layers[0]['id'],name=layers[0]['name'],count=layers[0]['count'])
    return answer
