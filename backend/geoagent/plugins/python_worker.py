"""Generic scientific Python worker; launched inside an OS sandbox."""
import contextlib
import io
import json
from pathlib import Path
try:import resource
except ImportError:resource=None
import sys
import traceback


def run(request):
    import geopandas as gpd
    import rasterio
    inputs={}
    for name,path in request.get('inputs',{}).items():
        inputs[name]=rasterio.open(path) if Path(path).suffix.lower() in ('.tif','.tiff') else gpd.read_file(path)
    scope={'__name__':'__geoagent_analysis__','inputs':inputs,'input_paths':request.get('inputs',{}),
           'output_dir':Path(request['job'])/'outputs','outputs':{},'metrics':{}}
    if resource:
        resource.setrlimit(resource.RLIMIT_CPU,(request['timeout'],request['timeout']+2))
        resource.setrlimit(resource.RLIMIT_FSIZE,(100*1024*1024,100*1024*1024))
    exec(compile(request['code'],'<workspace-analysis>','exec'),scope)
    outputs=[]
    for name,path in scope.get('outputs',{}).items():
        path=Path(path).resolve()
        if not path.is_relative_to(scope['output_dir'].resolve()) or not path.is_file():
            raise ValueError('代码输出必须是 output_dir 内实际存在的文件。')
        outputs.append({'name':str(name),'path':str(path),'allow_file_only':True})
    return {'outputs':outputs,'scalars':scope.get('metrics',{})}


if __name__=='__main__':
    request=json.loads(Path(sys.argv[1]).read_text())
    try:result={'ok':True,'data':run(request)}
    except Exception as exc:result={'ok':False,'error':str(exc),'traceback':traceback.format_exc(limit=5)}
    print('GEOAGENT_RESULT:'+json.dumps(result,ensure_ascii=False,default=str),flush=True)
