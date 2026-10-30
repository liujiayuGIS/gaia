"""QGIS provider implementation of the shared plugin SDK."""
import hashlib
import json
from pathlib import Path
import shutil
import threading
import uuid
from .base import AnalysisPlugin
from . import runtime

_LOCK=threading.Lock()
_CATALOG=None


class QGISPlugin(AnalysisPlugin):
    id='qgis';name='QGIS / PyQGIS'

    def catalog(self):
        global _CATALOG
        if _CATALOG is not None:return _CATALOG
        with _LOCK:
            if _CATALOG is not None:return _CATALOG
            python=runtime.qgis_python()
            if not python:raise ValueError('QGIS 插件尚未配置运行环境。')
            cache=runtime.ROOT/'.runtime/qgis-catalog.json'
            if cache.exists():
                _CATALOG=json.loads(cache.read_text());return _CATALOG
            from types import SimpleNamespace
            root=runtime.ROOT/'.runtime';root.mkdir(exist_ok=True)
            job=runtime.job_folder(SimpleNamespace(root=root))
            _CATALOG=runtime.execute(python,'qgis_worker.py',{'operation':'catalog'},job,timeout=90,restricted=False)
            cache.write_text(json.dumps(_CATALOG,ensure_ascii=False));return _CATALOG

    def status(self):
        if not runtime.qgis_python():return {'available':False,'error':'请安装 QGIS 运行时，或配置 GIS_QGIS_PYTHON。','operations':[]}
        if __import__('os').environ.get('GEOAGENT_DISABLE_QGIS')=='1':return {'available':False,'error':'此进程停用了 QGIS。','operations':[]}
        try:
            data=self.catalog()
            return {'available':True,'version':data['version'],'algorithm_count':len(data['algorithms']),
                'providers':data['providers'],'operations':['analysis','cartography','projects','templates','execute_code'],
                'description':'真实 QGIS Processing、打印布局、工程与样式保存、独立 PyQGIS 代码作业。'}
        except Exception as exc:return {'available':False,'error':str(exc),'operations':[]}

    def algorithms(self):return self.catalog()['algorithms']

    def execute(self,store,algorithm_id,arguments,run_id,cancel):
        spec=next((x for x in self.algorithms() if x['id']==algorithm_id),None)
        if not spec:raise ValueError('原生 QGIS 算法不存在。')
        unknown=set(arguments)-set(spec['parameters'])
        if unknown:raise ValueError('未知 QGIS 参数：'+', '.join(unknown))
        job=runtime.job_folder(store);bindings={};params={};multi={}
        for key,value in arguments.items():
            parameter=spec['parameters'][key]
            if parameter['type']=='layer':
                if value:bindings[key]=value
            elif parameter['type']=='layers':
                if not isinstance(value,list):raise ValueError(key+' 需要图层ID列表。')
                multi[key]=[]
                for i,layer_id in enumerate(value):
                    alias=f'{key}__{i}';bindings[alias]=layer_id;multi[key].append(alias)
            elif value is not None and not (value=='' and parameter.get('default') is None):params[key]=value
        paths,_=runtime.copy_inputs(store,bindings,job)
        for key,aliases in multi.items():
            paths[key]=[paths.pop(alias) for alias in aliases]
        response=runtime.execute(runtime.qgis_python(),'qgis_worker.py',{'operation':'algorithm',
            'algorithm_id':spec['native_id'],'arguments':params,'inputs':paths},job,cancel,300)
        return runtime.publish(store,response,run_id,self.id,bindings,{'algorithm':spec['native_id'],'parameters':params,'qgis_version':response.get('qgis_version')})

    def execute_code(self,store,code,inputs,run_id,cancel,timeout=60):
        job=runtime.job_folder(store);paths,_=runtime.copy_inputs(store,inputs,job)
        (job/'analysis.py').write_text(code)
        response=runtime.execute(runtime.qgis_python(),'qgis_worker.py',{'operation':'code','code':code,'inputs':paths},job,cancel,timeout)
        result=runtime.publish(store,response,run_id,self.id,inputs,{'code_sha256':hashlib.sha256(code.encode()).hexdigest(),'qgis_version':response.get('qgis_version')})
        result['code']=code;return result

    def prepare(self,store,layout,layers,operation,fmt='pdf',dpi=150):
        layout=json.loads(json.dumps(layout))
        job=runtime.job_folder(store)
        for item in layout.get('items',{}).values():
            if item.get('asset_id'):
                asset=store.object('assets',item['asset_id'])
                candidates=[x for x in asset['resources'] if x['path'].lower().endswith(('.png','.jpg','.jpeg','.svg'))]
                if len(candidates)!=1:raise ValueError('布局图片需选择唯一图片资源。')
                source=store.root/'inbox'/asset['id']/candidates[0]['path'];target=job/'inputs'/source.name
                shutil.copy2(source,target);item['picture_path']=str(target)
        selected={x['id']:x for x in layers}
        # Preserve the entire workspace in a project snapshot; map frames use explicit bindings.
        all_layers=store.layers()
        paths,metadata=runtime.copy_inputs(store,{x['id']:x['id'] for x in all_layers},job)
        scene=[]
        for layer in all_layers:
            item={**layer,'path':paths[layer['id']]}
            if layer.get('qgis_style_path'):
                source=store.root/layer['qgis_style_path'];target=job/'inputs'/(layer['id']+'.qml')
                if source.exists():shutil.copy2(source,target);item['qml']=str(target)
            scene.append(item)
        template=None
        if layout.get('template_id'):
            saved=store.object('templates',layout['template_id'])
            folder=store.root/Path(saved['path']).parent
            shutil.copytree(folder,job/'inputs/template')
            template={'path':str(job/'inputs/template'/Path(saved['path']).name),'bindings':{layout.get('template_bindings',{}).get(k,k):v for k,v in saved.get('bindings',{}).items()}}
        return job,{'operation':operation,'layout':layout,'layers':scene,'map_layers':list(selected),
                    'format':fmt,'dpi':dpi,'template':template}

    def render(self,store,layout,fmt,dpi,layers,preview=False):
        config=layout.model_dump() if hasattr(layout,'model_dump') else layout
        job,request=self.prepare(store,config,layers,'render',fmt,dpi)
        response=runtime.execute(runtime.qgis_python(),'qgis_worker.py',request,job,timeout=180)
        content=Path(response['rendered_path']).read_bytes()
        if not preview:self.record_project(store,response,config.get('title','地图工程'),config)
        return content

    def record_project(self,store,response,name,layout):
        from ..store import now
        id=uuid.uuid4().hex
        project=Path(response['project']);template=Path(response['template'])
        record={'id':id,'name':name[:100],'plugin_id':self.id,'created_at':now(),
                'path':str(project.relative_to(store.root.resolve())),'bundle':str(Path(response['bundle']).relative_to(store.root.resolve())),
                'template_path':str(template.relative_to(store.root.resolve())),'bindings':response.get('bindings',{}),
                'layout':layout,'qgis_version':response.get('qgis_version')}
        for key in ('path','bundle','template_path'):
            export_id=uuid.uuid4().hex;path=store.root/record[key]
            store.put_object('exports',export_id,{'id':export_id,'name':name+path.suffix,'path':record[key],
                'created_at':record['created_at'],'format':path.suffix[1:],'plugin':'qgis','url':f'/api/exports/{export_id}/download'})
            record[key+'_url']=f'/api/exports/{export_id}/download'
        store.put_object('projects',id,record)
        store.put_object('settings','last_qgis_project',record)
        return record

    def save_project(self,store,name,layout=None):
        from ..cartography import get_layout
        config=layout or get_layout(store)
        job,request=self.prepare(store,config,store.layers(),'project')
        response=runtime.execute(runtime.qgis_python(),'qgis_worker.py',request,job,timeout=180)
        return self.record_project(store,response,name,config)

    def save_template(self,store,name):
        project=self.save_project(store,name)
        id=uuid.uuid4().hex
        record={'id':id,'name':name[:100],'plugin_id':'qgis','path':project['template_path'],
            'bindings':project['bindings'],'layout':project['layout'],'created_at':project['created_at'],
            'url':project['template_path_url']}
        return store.put_object('templates',id,record)

    def open_project(self,store,project_id,run_id=None):
        from ..cartography import update_layout
        record=store.object('projects',project_id);source=store.root/record['path']
        job=runtime.job_folder(store)
        shutil.copytree(source.parent,job/'inputs/project')
        response=runtime.execute(runtime.qgis_python(),'qgis_worker.py',{'operation':'open_project',
            'path':str(job/'inputs/project'/source.name)},job,timeout=180)
        answer=runtime.publish(store,response,run_id,'qgis',{}, {'project_id':project_id,'operation':'open_project'})
        remap={}
        for old,new in zip(response.get('layer_metadata',[]),answer['layers']):
            remap[old['backend_id']]=new['layer_id']
            if old.get('style_path'):
                target=store.root/'styles'/(new['layer_id']+'.qml');target.parent.mkdir(exist_ok=True)
                shutil.copy2(old['style_path'],target)
                store.patch_layer(new['layer_id'],{'qgis_style_path':str(target.relative_to(store.root))})
        layout=record['layout'].copy();layout.pop('template_id',None)
        for key in ('focus_layer_id','context_layer_id'):
            if layout.get(key):layout[key]=remap.get(layout[key])
        layout['plugin_id']='qgis';update_layout(store,layout)
        return {**answer,'project_id':project_id,'restored_layers':len(answer['layers'])}

    def scene(self,store,layout,layers):
        config=layout.model_dump() if hasattr(layout,'model_dump') else layout
        key=hashlib.sha256(json.dumps({'layout':config,'layers':store.layers(),'scene_version':2},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        try:return store.object('layout_scenes',key)['scene']
        except ValueError:pass
        job,request=self.prepare(store,config,layers,'project')
        response=runtime.execute(runtime.qgis_python(),'qgis_worker.py',request,job,timeout=180)
        scene=response['scene'];files={}
        for element in scene['elements']:
            path=Path(element.pop('image_path'));files[element['id']]=str(path.relative_to(store.root.resolve()))
            element['image_url']=f'/api/layout-scenes/{key}/{element["id"]}.png'
        scene.update(id=key,plugin_id='qgis')
        store.put_object('layout_scenes',key,{'scene':scene,'files':files})
        return scene
