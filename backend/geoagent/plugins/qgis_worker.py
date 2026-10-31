"""Private JSON worker running in the QGIS interpreter; never import into FastAPI."""
import json
import math
from pathlib import Path
import os
try:import resource
except ImportError:resource=None
import sys
import traceback

PREFIX=Path(os.environ.get('QGIS_PREFIX_PATH',sys.prefix))
if sys.platform=='win32':
    _dll_directory=os.add_dll_directory(str(PREFIX/'bin'))
    sys.path.insert(0,str(PREFIX/'python'))
    sys.path.insert(0,str(PREFIX/'python/plugins'))
sys.path.insert(0,str(PREFIX/'share/qgis/python'))
sys.path.insert(0,str(PREFIX/'share/qgis/python/plugins'))
sys.path.insert(0,str(Path(__file__).parent))
from qgis.core import *
from qgis.PyQt.QtCore import QVariant


def simple(value):
    if value is None or isinstance(value,(str,bool,int)):return value
    if isinstance(value,float):return value if math.isfinite(value) else None
    if isinstance(value,(list,tuple)):return [simple(x) for x in value]
    if isinstance(value,dict):return {str(k):simple(v) for k,v in value.items()}
    if isinstance(value,QgsMapLayer):return value.source()
    return str(value)


def definition(algorithm):
    params={};destinations=[]
    for parameter in algorithm.parameterDefinitions():
        kind=parameter.type().lower()
        if parameter.isDestination():
            ext=parameter.defaultFileExtension() if hasattr(parameter,'defaultFileExtension') else 'dat'
            destinations.append({'name':parameter.name(),'type':kind,'extension':ext or 'dat'})
            continue
        mapped='layer' if kind in ('source','vector','raster','maplayer','feature_source','featuresource') else 'layers' if kind=='multilayer' else 'number' if kind in ('number','distance','scale','band','area','volume') else 'boolean' if kind=='boolean' else 'enum' if kind=='enum' else 'string'
        item={'type':mapped,'native_type':parameter.type(),'label':parameter.description(),
              'required':not bool(parameter.flags()&QgsProcessingParameterDefinition.FlagOptional),
              'default':simple(parameter.defaultValue())}
        if hasattr(parameter,'options'):item['options']=parameter.options()
        if hasattr(parameter,'allowMultiple'):item['multiple']=parameter.allowMultiple()
        if hasattr(parameter,'parentLayerParameterName'):item['parent_layer']=parameter.parentLayerParameterName()
        if hasattr(parameter,'parentParameterName'):item['parent_layer']=parameter.parentParameterName()
        params[parameter.name()]=item
    return {'id':'qgis:'+algorithm.id(),'native_id':algorithm.id(),'plugin_id':'qgis','name':algorithm.displayName(),
            'category':'QGIS · '+algorithm.group(),'provider':algorithm.provider().id(),
            'description':(algorithm.shortHelpString() or '')[:2000],'parameters':params,'destinations':destinations,
            'output':'native_outputs','status':'available'}


def layers_from_paths(paths):
    layers={}
    for name,path in paths.items():
        layer=QgsRasterLayer(path,name) if Path(path).suffix.lower() in ('.tif','.tiff') else QgsVectorLayer(path,name,'ogr')
        if not layer.isValid():raise ValueError('QGIS 无法打开输入：'+name)
        layers[name]=layer
    return layers


def outputs_from_result(result,job,context):
    import shutil
    outputs=[];scalars={}
    for name,value in result.items():
        if isinstance(value,QgsMapLayer):
            if isinstance(value,QgsVectorLayer):
                path=job/'outputs'/(name+'.gpkg')
                options=QgsVectorFileWriter.SaveVectorOptions();options.driverName='GPKG'
                error=QgsVectorFileWriter.writeAsVectorFormatV3(value,str(path),context.transformContext(),options)
                if error[0]!=QgsVectorFileWriter.NoError:raise ValueError(str(error))
                value=str(path)
            else:value=value.source()
        path=Path(value) if isinstance(value,str) and len(value)<4000 and not value.startswith(('http:','https:')) else None
        if path and path.is_file():
            path=path.resolve()
            if not path.is_relative_to(job):raise ValueError('输出路径越过作业目录。')
            outputs.append({'name':name,'path':str(path),'allow_file_only':True})
        else:scalars[name]=simple(value)
    return {'outputs':outputs,'scalars':scalars,'qgis_version':Qgis.QGIS_VERSION}


def run(request,app):
    import processing
    job=Path(request['job'])
    if request['operation']=='catalog':
        return {'version':Qgis.QGIS_VERSION,'providers':[{'id':p.id(),'name':p.name()} for p in app.processingRegistry().providers()],
                'algorithms':[definition(a) for a in app.processingRegistry().algorithms()]}
    if request['operation'] in ('render','project','open_project','template'):
        from qgis_cartography import execute
        return execute(request)
    context=QgsProcessingContext();context.setProject(QgsProject.instance());context.setTemporaryFolder(str(job/'tmp'))
    feedback=QgsProcessingFeedback()
    if request['operation']=='algorithm':
        algorithm=app.processingRegistry().algorithmById(request['algorithm_id'])
        if not algorithm:raise ValueError('QGIS 算法不存在。')
        spec=definition(algorithm);arguments=request.get('arguments',{}).copy()
        for key,value in request.get('inputs',{}).items():arguments[key]=value
        for dest in spec['destinations']:
            arguments[dest['name']]=str(job/'outputs'/(dest['name']+'.'+dest['extension']))
        ok,message=algorithm.checkParameterValues(arguments,context)
        if not ok:raise ValueError(message)
        result=processing.run(algorithm.id(),arguments,context=context,feedback=feedback)
    elif request['operation']=='code':
        if resource:
            resource.setrlimit(resource.RLIMIT_CPU,(request['timeout'],request['timeout']+2))
            resource.setrlimit(resource.RLIMIT_FSIZE,(100*1024*1024,100*1024*1024))
        scope={'__name__':'__geoagent_analysis__','inputs':layers_from_paths(request.get('inputs',{})),
               'input_paths':request.get('inputs',{}),'output_dir':job/'outputs','outputs':{},'metrics':{},
               'processing':processing,'context':context,'feedback':feedback}
        exec(compile(request['code'],'<pyqgis-analysis>','exec'),scope)
        result=scope.get('outputs',{})
        answer=outputs_from_result(result,job,context);answer['scalars'].update(simple(scope.get('metrics',{})))
        return answer
    else:raise ValueError('Unknown QGIS operation.')
    return outputs_from_result(result,job,context)


if __name__=='__main__':
    request=json.loads(Path(sys.argv[1]).read_text())
    config=str(Path(request['job'])/'config')
    if sys.platform=='win32':
        from qgis.PyQt.QtCore import QSettings
        # Headless jobs must not depend on the interactive user's registry profile.
        QSettings.setDefaultFormat(QSettings.IniFormat)
        QSettings.setPath(QSettings.IniFormat,QSettings.UserScope,config)
        os.environ['QGIS_AUTH_DB_DIR_PATH']=config
    QgsApplication.setPrefixPath(str(PREFIX),True)
    app=QgsApplication([],False,config)
    try:
        if sys.platform=='win32':
            for name,initialize in [('providers',lambda:QgsProviderRegistry.instance()),
                                    ('data items',lambda:QgsApplication.dataItemProviderRegistry()),
                                    ('project',lambda:QgsProject.instance())]:
                print('QGIS initializing '+name,file=sys.stderr,flush=True)
                initialize()
        app.initQgis()
        from processing.core.Processing import Processing
        Processing.initialize()
        result={'ok':True,'data':run(request,app)}
    except Exception as exc:result={'ok':False,'error':str(exc),'traceback':traceback.format_exc(limit=8)}
    print('GEOAGENT_RESULT:'+json.dumps(result,ensure_ascii=False,default=str),flush=True)
    QgsProject.instance().clear()
    app.exitQgis()
