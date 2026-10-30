from __future__ import annotations
import csv
import io
import json
import os
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict, Field
from .store import Store, now
from .harness import Registry, execute_run
from .provider import ProviderError, resolve_config, test_connection
from . import demo, gis, formats, algorithms, cartography

ROOT=Path(__file__).resolve().parents[2]

class ChatRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    message: str=Field(min_length=1,max_length=4000)
    session_id: str=Field(max_length=100)
    selected_layers: list[str]=Field(default_factory=list,max_length=20)
    mode: str='offline'
    base_url: str='https://api.deepseek.com'
    model: str='deepseek-chat'
    api_key: str=''
    protocol: str='auto'
    reasoning_effort: str='medium'
    algorithm_id: str | None=None
    code: str | None=Field(default=None,max_length=30000)
    plugin_id: str='python'
    inputs: dict[str,str]=Field(default_factory=dict)
    save_as: str | None=None
    recipe_id: str | None=None
    output_name: str | None=Field(default=None,max_length=100)
    workflow_id: str | None=None
    arguments: dict=Field(default_factory=dict)

class ConnectionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    base_url: str=Field(max_length=1000)
    model: str=Field(max_length=200)
    api_key: str=Field(default='',repr=False,max_length=1000)
    protocol: str='auto'
    reasoning_effort: str='medium'

class StyleRequest(BaseModel):
    visible: bool | None=None
    opacity: float | None=Field(default=None,ge=0,le=1)
    labels: bool | None=None
    field: str | None=None
    color: str | None=Field(default=None,pattern=r'^#[0-9a-fA-F]{6}$')


def create_app(workspace=None):
    app=FastAPI(title='GeoAgent Local',version='0.3.0')
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver','[::1]'])
    store=Store(workspace or os.environ.get('GEOAGENT_WORKSPACE',ROOT/'.geoagent'))
    registry=Registry(store)
    app.state.store=store
    active={}
    gate=threading.Lock()

    @app.middleware('http')
    async def local_origin(request: Request,call_next):
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('origin')
            if origin and urlparse(origin).netloc!=request.headers.get('host'):
                return JSONResponse({'detail':'跨站写入请求被拒绝。'},status_code=403)
        return await call_next(request)

    @app.exception_handler(ValueError)
    async def bad_input(request,exc):
        return JSONResponse({'detail':str(exc)},status_code=400)

    @app.get('/api/health')
    def health():
        return {'ok':True,'version':'0.3.0','model_configured':bool(os.environ.get('GIS_LLM_API_KEY')),'tools':list(registry.tools),'limits':{'upload_mb':250,'features':100000,'raster_analysis_pixels':16000000}}

    @app.post('/api/model/test')
    def model_test(body: ConnectionRequest):
        config=resolve_config(body.base_url,body.model,body.api_key,body.protocol,body.reasoning_effort)
        try:
            return test_connection(config,[t.schema() for t in registry.tools.values()])
        except ProviderError as exc:
            return JSONResponse({'detail':exc.details['message'],'diagnostic':exc.details},status_code=400)

    @app.get('/api/layers')
    def layers():
        return store.layers()

    @app.post('/api/demo')
    def load_demo():
        return demo.seed(store)

    @app.get('/api/capabilities')
    def capabilities():
        from .plugins import PluginManager
        plugins=PluginManager(store)
        return {'algorithms':plugins.algorithms(),'plugins':plugins.manifests(),'formats':formats.format_catalog(),'protocols':['responses','chat_completions'],
                'map_exports':['png','jpeg','tiff','svg','pdf'],'cartographic_templates':['standard','choropleth','terrain'],'qgis_engine':next((p.get('version','not available') for p in plugins.manifests() if p['id']=='qgis' and p.get('available')),'not available')}

    @app.get('/api/plugins')
    def list_plugins():
        from .plugins import PluginManager
        return PluginManager(store).manifests()

    @app.patch('/api/plugins/{plugin_id}')
    def configure_plugin(plugin_id: str,body: dict):
        from .plugins import PluginManager
        return PluginManager(store).toggle(plugin_id,body.get('enabled',True))

    @app.get('/api/skills')
    def skills(query: str=''):
        from .skills import SkillManager
        return SkillManager(store).list(query)

    @app.get('/api/skills/{skill_id}')
    def skill_detail(skill_id: str):
        from .skills import SkillManager
        return SkillManager(store).read(skill_id)

    @app.post('/api/skills')
    async def install_skill(file: UploadFile=File(...)):
        from .skills import SkillManager
        return SkillManager(store).install(file.filename or 'SKILL.md',await file.read(5*1024*1024+1))

    @app.get('/api/recipes')
    def recipes():return [{k:v for k,v in x.items() if k!='code'} for x in store.objects('recipes')]

    @app.get('/api/recipes/{recipe_id}')
    def recipe(recipe_id: str):return store.object('recipes',recipe_id)

    @app.get('/api/projects')
    def projects():return store.objects('projects')

    @app.post('/api/projects')
    def save_project(body: dict):
        from .plugins import PluginManager
        return PluginManager(store).choose('projects',body.get('plugin_id','auto')).save_project(store,str(body.get('name','GIS 工程')))

    @app.post('/api/projects/{project_id}/open')
    def open_project(project_id: str):
        from .plugins import PluginManager
        if active:raise HTTPException(409,'请等待当前任务结束后再打开工程。')
        project=store.object('projects',project_id)
        return PluginManager(store).get(project['plugin_id']).open_project(store,project_id)

    @app.get('/api/layout-templates')
    def templates():return store.objects('templates')

    @app.post('/api/layout-templates')
    def save_template(body: dict):
        from .plugins import PluginManager
        return PluginManager(store).choose('templates',body.get('plugin_id','auto')).save_template(store,str(body.get('name','地图布局')))

    @app.post('/api/layout-templates/{template_id}/apply')
    def apply_template(template_id: str,body: dict):
        item=store.object('templates',template_id);layout=item['layout'].copy();bindings=body.get('bindings',{})
        for key in ('focus_layer_id','context_layer_id'):
            if layout.get(key):layout[key]=bindings.get(layout[key],layout[key])
        layout.update(plugin_id=item['plugin_id'],template_id=template_id,template_bindings=bindings)
        return cartography.update_layout(store,layout)

    @app.get('/api/layout/scene')
    def layout_scene():
        from .plugins import PluginManager
        layout=cartography.Layout.model_validate(cartography.get_layout(store))
        plugin=PluginManager(store).choose('cartography',layout.plugin_id)
        if not hasattr(plugin,'scene'):raise ValueError('当前插件未提供可编辑布局场景。请选择支持该能力的插件。')
        return plugin.scene(store,layout,[x for x in store.layers() if x['style'].get('visible',True)])

    @app.get('/api/layout-scenes/{scene_id}/{element_id}.png')
    def layout_element(scene_id: str,element_id: str):
        item=store.object('layout_scenes',scene_id)
        if element_id not in item['files']:raise HTTPException(404,'布局元素不存在。')
        return FileResponse(store.root/item['files'][element_id],media_type='image/png',headers={'Cache-Control':'private, max-age=31536000, immutable'})

    @app.get('/api/imports')
    def imports():
        return store.objects('assets')

    @app.post('/api/imports')
    async def stage(files: list[UploadFile]=File(...)):
        content=[];size=0
        for file in files:
            data=await file.read(formats.MAX_UPLOAD+1);size+=len(data)
            if size>formats.MAX_UPLOAD:raise ValueError('本次文件超过250 MB。')
            content.append((file.filename or 'data',data))
        return formats.stage_files(store,content)

    @app.post('/api/imports/{asset_id}/load')
    def load_asset(asset_id: str,body: dict):
        return formats.import_asset(store,asset_id,body.get('resource'),body.get('source_crs'),body.get('sublayer'))

    @app.post('/api/layers/upload')
    async def upload(file: UploadFile=File(...),source_crs: str=Form('')):
        content=await file.read(formats.MAX_UPLOAD+1)
        if len(content)>formats.MAX_UPLOAD:raise ValueError('文件超过250 MB。')
        asset=formats.stage_files(store,[(file.filename or 'data',content)])
        return formats.import_asset(store,asset['id'],source_crs=source_crs or None)

    @app.get('/api/workflows')
    def workflows():return store.objects('workflows')

    @app.get('/api/workflows/{workflow_id}')
    def workflow_file(workflow_id: str):return store.object('workflows',workflow_id)

    @app.get('/api/layout')
    def layout():return cartography.get_layout(store)

    @app.patch('/api/layout')
    def update_layout(body: dict):return cartography.update_layout(store,body)

    @app.get('/api/layout/preview')
    def preview():return Response(cartography.render_map(store,'svg',100,preview=True),media_type='image/svg+xml')

    @app.post('/api/layout/export')
    def export_map(body: dict):return cartography.export_map(store,body.get('format','pdf'),int(body.get('dpi',150)),body.get('layer_ids'))

    @app.get('/api/exports')
    def exports():return store.objects('exports')

    @app.get('/api/exports/{export_id}/download')
    def download(export_id: str):
        item=store.object('exports',export_id);path=store.root/item['path']
        return FileResponse(path,filename=item['name'])

    @app.post('/api/view')
    def save_map_state(body: dict):
        return store.put_object('settings','map_state',{k:body[k] for k in ('bounds','zoom','center') if k in body})

    @app.get('/api/view')
    def view():return store.setting('map_command',{})

    @app.get('/api/layers/{layer_id}/preview')
    def raster_preview(layer_id: str):return Response(formats.raster_preview(store,layer_id),media_type='image/png')

    @app.patch('/api/layers/{layer_id}/name')
    def rename(layer_id: str,body: dict):
        name=str(body.get('name','')).strip()
        if not name:raise ValueError('图层名称不能为空。')
        return store.patch_layer(layer_id,{'name':name[:100]})

    @app.get('/api/layers/{layer_id}/data')
    def data(layer_id: str):
        if store.get_layer(layer_id).get('kind')=='raster':return {'type':'FeatureCollection','features':[]}
        data=store.data(layer_id)
        return {**data,'features':data['features'][:10000],'preview_truncated':len(data['features'])>10000,'total':len(data['features'])}

    @app.get('/api/layers/{layer_id}/inspect')
    def inspect(layer_id: str):
        return gis.inspect(store,layer_id)

    @app.patch('/api/layers/{layer_id}/style')
    def style(layer_id: str,body: StyleRequest):
        return store.style_layer(layer_id,**body.model_dump(exclude_unset=True))

    @app.get('/api/layers/{layer_id}/export')
    def export(layer_id: str,format: str='geojson',target_crs: str | None=None):
        meta=store.get_layer(layer_id)
        if meta.get('kind')=='raster':
            if format not in ('tif','tiff','geotiff'):raise ValueError('栅格原始数据导出请选择 tif。')
            return FileResponse(formats.raster_path(store,layer_id),filename=layer_id+'.tif')
        if format not in ('geojson','csv'):
            path=formats.export_vector(store,layer_id,format,target_crs)
            return FileResponse(path,filename=path.name)
        data=store.data(layer_id)
        if format=='csv':
            fields=sorted({k for f in data['features'] for k in f['properties']})
            buf=io.StringIO()
            writer=csv.DictWriter(buf,fieldnames=fields)
            writer.writeheader()
            writer.writerows(f['properties'] for f in data['features'])
            return Response('\ufeff'+buf.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{layer_id}.csv"'})
        if format!='geojson':
            raise ValueError('支持 geojson 或 csv 导出。')
        return Response(json.dumps(data,ensure_ascii=False),media_type='application/geo+json',headers={'Content-Disposition':f'attachment; filename="{layer_id}.geojson"'})

    @app.get('/api/runs')
    def runs():
        return store.runs()

    @app.post('/api/runs',status_code=202)
    def chat(body: ChatRequest):
        config=None
        if body.mode=='model':
            config=resolve_config(body.base_url,body.model,body.api_key,body.protocol,body.reasoning_effort)
        elif body.mode not in ('offline','algorithm','workflow','code'):
            raise ValueError('未知运行模式。')
        # One workspace mutation owner. Parallel clients cannot race on the workspace.
        with gate:
            if active:
                raise HTTPException(409,'工作区已有运行中的任务，请等待或停止。')
            run={'id':uuid.uuid4().hex,'status':'queued','mode':body.mode,'session_id':body.session_id,
                 'message_input':body.message,'selected_layers':body.selected_layers,'algorithm_id':body.algorithm_id,'workflow_id':body.workflow_id,'arguments':body.arguments,'code':body.code,'plugin_id':body.plugin_id,'inputs':body.inputs,'save_as':body.save_as,'recipe_id':body.recipe_id,'output_name':body.output_name,'created_at':now(),'message':'','output_layers':[]}
            store.save_run(run)
            cancel=threading.Event()
            active[run['id']]=cancel
        def work():
            try:
                execute_run(store,registry,run,config,cancel)
            finally:
                with gate:
                    active.pop(run['id'],None)
        threading.Thread(target=work,daemon=True).start()
        return {'id':run['id']}

    @app.get('/api/runs/{run_id}')
    def get_run(run_id: str):
        try:
            return {**store.run(run_id),'events':store.events(run_id)}
        except KeyError:
            raise HTTPException(404,'运行不存在。')

    @app.post('/api/runs/{run_id}/cancel')
    def cancel_run(run_id: str):
        with gate:
            cancel=active.get(run_id)
            if cancel:
                cancel.set()
        return {'requested':bool(cancel),'note':'在工具或模型调用结束后停止；不会回滚已完成的图层。'}

    @app.get('/api/runs/{run_id}/export')
    def export_run(run_id: str):
        result=get_run(run_id)
        import importlib.metadata
        result['environment']={x:importlib.metadata.version(x) for x in ('shapely','pyproj','fastapi')}
        result['artifacts']=[store.get_layer(x) for x in result.get('output_layers',[])]
        return Response(json.dumps(result,ensure_ascii=False,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="run-{run_id}.json"'})

    dist=ROOT/'frontend/dist'
    if dist.exists():
        app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
    return app

app=create_app()
