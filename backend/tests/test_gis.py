import json
import threading
import time
import pytest
from pyproj import Geod, Transformer
from fastapi.testclient import TestClient
from geoagent.store import Store
from geoagent.gis import validate_collection, buffer_points, count_points, import_bytes
from geoagent.harness import Registry, offline_plan, execute_run
from geoagent.app import create_app


def fc(coords):
    return {'type':'FeatureCollection','features':[{'type':'Feature','properties':{'name':str(i)},'geometry':{'type':'Point','coordinates':p}} for i,p in enumerate(coords)]}


def test_buffer_distance_independent_geodesic(tmp_path):
    store=Store(tmp_path)
    source=store.add_layer('station',fc([[116.39,39.91]]))
    result=buffer_points(store,source['id'],800,'r')
    polygon=store.data(result['layer_id'])['features'][0]['geometry']['coordinates'][0]
    geod=Geod(ellps='WGS84')
    assert len(polygon)==257
    assert all(abs(geod.inv(116.39,39.91,x,y)[2]-800)<0.05 for x,y in polygon)
    assert store.data(source['id'])==fc([[116.39,39.91]])


def test_count_inside_outside_boundary_and_overlap(tmp_path):
    store=Store(tmp_path)
    polygon={'type':'Polygon','coordinates':[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}
    regions=store.add_layer('areas',{'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':polygon} for _ in range(2)]})
    points=store.add_layer('poi',fc([[.5,.5],[1,.5],[2,2]]))
    result=count_points(store,regions['id'],points['id'],'r')
    assert [x['poi_count'] for x in result['rows']]==[2,2]
    assert '不是去重' in result['limitations']


def test_projected_import_and_invalid_geometry():
    x,y=Transformer.from_crs(4326,3857,always_xy=True).transform(116,40)
    data=validate_collection(fc([[x,y]]),'EPSG:3857')
    lon,lat=data['features'][0]['geometry']['coordinates']
    assert lon==pytest.approx(116)
    assert lat==pytest.approx(40)
    with pytest.raises(ValueError,match='范围'):
        validate_collection(fc([[x,y]]))
    with pytest.raises(ValueError,match='无效'):
        validate_collection({'type':'FeatureCollection','features':[{'geometry':{'type':'Polygon','coordinates':[[[0,0],[1,1],[1,0],[0,1],[0,0]]]}}]})


def test_typed_tools_refuse_invalid_parameters_and_unknown_tools(tmp_path):
    store=Store(tmp_path)
    r=Registry(store)
    assert not r.execute('r','buffer_points',{'layer_id':'x','distance_m':-1},threading.Event())['success']
    assert not r.execute('r','bash',{'command':'pwd'},threading.Event())['success']
    assert not r.execute('r','list_layers',{'extra':1},threading.Event())['success']


def test_api_full_workflow_persistence_export_and_run_audit(tmp_path):
    client=TestClient(create_app(tmp_path))
    assert client.post('/api/demo').status_code==200
    assert len(client.get('/api/layers').json())==4
    assert len(client.post('/api/demo').json())==4
    request=client.post('/api/runs',json={'message':'统计地铁站 800 米直线范围内的公园数量','session_id':'test','mode':'offline'})
    assert request.status_code==202
    rid=request.json()['id']
    for _ in range(100):
        run=client.get('/api/runs/'+rid).json()
        if run['status'] not in ('queued','running'):
            break
        time.sleep(.02)
    assert run['status']=='completed',run
    assert len(run['output_layers'])==2
    assert [e['seq'] for e in run['events']]==list(range(1,len(run['events'])+1))
    assert any(e['type']=='validation_completed' for e in run['events'])
    output=run['output_layers'][-1]
    assert client.get(f'/api/layers/{output}/export').json()['features'][0]['properties']['poi_count']>=0
    assert 'poi_count' in client.get(f'/api/layers/{output}/export?format=csv').text
    assert 'api_key' not in client.get(f'/api/runs/{rid}/export').text
    assert len(TestClient(create_app(tmp_path)).get('/api/layers').json())==6


def test_csv_upload_errors_and_cross_origin(tmp_path):
    client=TestClient(create_app(tmp_path))
    assert client.post('/api/layers/upload',files={'file':('points.csv',b'name,lon,lat\na,116,40')}).status_code==200
    assert client.post('/api/layers/upload',files={'file':('bad.geojson',b'not json')}).status_code==400
    assert client.post('/api/layers/upload',files={'file':('bad.csv',b'name\na')}).status_code==400
    assert client.post('/api/demo',headers={'Origin':'https://example.com'}).status_code==403


def test_offline_no_network_substitute_or_silent_distance(tmp_path):
    store=Store(tmp_path)
    from geoagent.demo import seed
    seed(store)
    registry=Registry(store)
    def run(text):
        return offline_plan(registry,store,{'id':'r','message_input':text},threading.Event())
    assert '尚未实现' in run('计算地铁站 800 米步行范围')
    assert '明确' in run('统计地铁站周边公园')
    assert len(store.layers())==4


def test_restart_marks_incomplete_run(tmp_path):
    store=Store(tmp_path)
    store.save_run({'id':'r','status':'running'})
    assert Store(tmp_path).run('r')['status']=='interrupted'


def test_cancellation_before_execution(tmp_path):
    store=Store(tmp_path)
    cancel=threading.Event();cancel.set()
    run={'id':'r','mode':'offline','message_input':'列出图层','status':'queued'}
    execute_run(store,Registry(store),run,None,cancel)
    assert store.run('r')['status']=='cancelled'


def test_model_loop_uses_real_tools_and_hides_secret(tmp_path, monkeypatch):
    from geoagent import harness
    from geoagent.demo import seed
    store=Store(tmp_path);seed(store)
    seen=[]
    class FakeClient:
        def __init__(self,*a,**kw): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,url,headers,json):
            seen.append(json)
            msg={'role':'assistant','content':None,'tool_calls':[{'id':'t1','type':'function','function':{'name':'list_layers','arguments':'{}'}}]} if len(seen)==1 else {'role':'assistant','content':'已读取四个图层。'}
            return httpx.Response(200,json={'choices':[{'message':msg}]},request=httpx.Request('POST',url))
    import httpx
    monkeypatch.setattr(harness.httpx,'Client',FakeClient)
    run={'id':'r','mode':'model','session_id':'s','message_input':'列出图层','selected_layers':[]}
    execute_run(store,Registry(store),run,{'base_url':'https://example.com','model':'test','api_key':'SECRET_TEST_KEY'},threading.Event())
    assert store.run('r')['status']=='completed'
    assert any(x['role']=='tool' for x in seen[-1]['messages'])
    assert 'SECRET_TEST_KEY' not in json.dumps(store.events('r'))


def test_inspection_guard_is_enforced_before_analysis(tmp_path):
    store=Store(tmp_path)
    layer=store.add_layer('station',fc([[116.39,39.91]]))
    registry=Registry(store);cancel=threading.Event()
    args={'layer_id':layer['id'],'distance_m':800}
    denied=registry.execute('r','buffer_points',args,cancel)
    assert not denied['success'] and 'inspect_layer' in denied['error']
    assert registry.execute('r','inspect_layer',{'layer_id':layer['id']},cancel)['success']
    assert registry.execute('r','buffer_points',args,cancel)['success']
    assert not registry.execute('other','buffer_points',args,cancel)['success']


def test_negative_distance_is_not_reinterpreted_as_positive(tmp_path):
    from geoagent.demo import seed
    store=Store(tmp_path);seed(store)
    run={'id':'r','mode':'offline','message_input':'为地铁站生成 -100 米缓冲区'}
    execute_run(store,Registry(store),run,None,threading.Event())
    assert store.run('r')['status']=='failed'
    assert len(store.layers())==4


def test_dateline_buffer_is_rejected(tmp_path):
    store=Store(tmp_path)
    layer=store.add_layer('station',fc([[179.99,0]]))
    with pytest.raises(ValueError,match='日期变更线'):
        buffer_points(store,layer['id'],2000,'r')
    assert len(store.layers())==1
