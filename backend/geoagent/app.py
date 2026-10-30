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
from . import demo, gis

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

class ConnectionRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    base_url: str=Field(max_length=1000)
    model: str=Field(max_length=200)
    api_key: str=Field(default='',repr=False,max_length=1000)

class StyleRequest(BaseModel):
    visible: bool | None=None
    color: str | None=Field(default=None,pattern=r'^#[0-9a-fA-F]{6}$')


def create_app(workspace=None):
    app=FastAPI(title='GeoAgent Local',version='0.1.0')
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
        return {'ok':True,'version':'0.1.0','model_configured':bool(os.environ.get('GIS_LLM_API_KEY')),'tools':list(registry.tools),'limits':{'upload_mb':12,'features':20000}}

    @app.post('/api/model/test')
    def model_test(body: ConnectionRequest):
        config=resolve_config(body.base_url,body.model,body.api_key)
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

    @app.post('/api/layers/upload')
    async def upload(file: UploadFile=File(...),source_crs: str=Form('EPSG:4326')):
        if not (file.filename or '').lower().endswith(('.geojson','.json','.csv')):
            raise ValueError('第一版支持 GeoJSON 和 CSV。')
        content=await file.read(12*1024*1024+1)
        if len(content)>12*1024*1024:
            raise ValueError('文件超过 12 MB。')
        try:
            data=gis.import_bytes(file.filename,content,source_crs)
        except (UnicodeDecodeError,json.JSONDecodeError):
            raise ValueError('无法读取文件，请使用 UTF-8 编码的有效 GeoJSON 或 CSV。') from None
        return store.add_layer(Path(file.filename).stem,data,provenance={'source_crs':source_crs,'import':'normalized_to_WGS84','coordinate_basis':'user_declared'})

    @app.get('/api/layers/{layer_id}/data')
    def data(layer_id: str):
        return store.data(layer_id)

    @app.get('/api/layers/{layer_id}/inspect')
    def inspect(layer_id: str):
        return gis.inspect(store,layer_id)

    @app.patch('/api/layers/{layer_id}/style')
    def style(layer_id: str,body: StyleRequest):
        return store.style_layer(layer_id,**body.model_dump(exclude_none=True))

    @app.get('/api/layers/{layer_id}/export')
    def export(layer_id: str,format: str='geojson'):
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
            config=resolve_config(body.base_url,body.model,body.api_key)
        elif body.mode!='offline':
            raise ValueError('未知运行模式。')
        # One workspace mutation owner. Parallel clients cannot race on the workspace.
        with gate:
            if active:
                raise HTTPException(409,'工作区已有运行中的任务，请等待或停止。')
            run={'id':uuid.uuid4().hex,'status':'queued','mode':body.mode,'session_id':body.session_id,
                 'message_input':body.message,'selected_layers':body.selected_layers,'created_at':now(),'message':'','output_layers':[]}
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
