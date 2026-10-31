import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from geoagent.app import create_app
from geoagent.harness import Registry,execute_run
from geoagent.memory import Memory
from geoagent.store import Store
from geoagent import durable

CONFIG={'base_url':'https://example.test/v1','model':'test','api_key':'SECRET_NEVER_CHECKPOINTED','protocol':'responses','reasoning_effort':'medium'}


def feature(x=0):
    return {'type':'FeatureCollection','features':[{'type':'Feature','geometry':{'type':'Point','coordinates':[x,0]},'properties':{'name':'point'}}]}


def run(id='run',**kw):
    return {'id':id,'mode':'model','session_id':'session','message_input':'进行分析',**kw}


def model_call(name,args):
    return {'id':'response','output':[{'type':'reasoning','id':'reasoning','summary':[],'encrypted_content':'OPAQUE'},
        {'type':'function_call','call_id':'call','name':name,'arguments':json.dumps(args)}]}


def final(text='完成'):
    return {'id':'final','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':text}]}]}


def model(monkeypatch,name,args):
    calls=[]
    def respond(client,config,payload):
        calls.append(payload)
        return final() if any(x.get('type')=='function_call_output' for x in payload['input']) else model_call(name,args)
    monkeypatch.setattr(durable,'request_responses',respond)
    return calls


def fake_code(monkeypatch,counter):
    from geoagent.plugins.python_plugin import PythonPlugin
    def execute(self,store,code,inputs,run_id,cancel,timeout=60):
        counter.append(code)
        layer=store.add_layer('result',feature(),provenance={'run_id':run_id,'input_layers':list(inputs.values())})
        return {'layer_id':layer['id'],'layers':[{'layer_id':layer['id']}],'scalars':{'count':1},'artifacts':[]}
    monkeypatch.setattr(PythonPlugin,'execute_code',execute)


def wait(client,id):
    for _ in range(150):
        value=client.get('/api/runs/'+id).json()
        if value['status'] not in ('queued','running'):return value
        time.sleep(.02)
    raise AssertionError('run did not settle')


def test_same_session_continuity_and_explicit_preferences(tmp_path,monkeypatch):
    store=Store(tmp_path);memory=Memory(store)
    memory.set_preferences({'crs':'EPSG:4547','distance_unit':'km'})
    store.save_run(run('old',status='completed',message_input='使用北京时间和公里',message='已记录本次要求'))
    store.save_run(run('other',session_id='other',status='completed',message_input='PRIVATE_OTHER_SESSION',message='SECRET_CONTEXT'))
    seen=[]
    monkeypatch.setattr(durable,'request_responses',lambda c,k,p:seen.append(p) or final())
    execute_run(store,Registry(store),run('new'),CONFIG,threading.Event())
    text=json.dumps(seen,ensure_ascii=False)
    assert '使用北京时间和公里' in text and 'EPSG:4547' in text
    assert 'PRIVATE_OTHER_SESSION' not in text and 'SECRET_CONTEXT' not in text
    assert memory.preferences()['distance_unit']=='km'
    assert not store.objects('knowledge')
    assert CONFIG['api_key'].encode() not in (tmp_path/'checkpoints.sqlite3').read_bytes()


@pytest.mark.parametrize('approved',[True,False])
def test_approval_survives_restart_and_is_bound_to_exact_call(tmp_path,monkeypatch,approved):
    calls=model(monkeypatch,'execute_code',{'plugin_id':'python','code':'outputs = {}','inputs':{}})
    executed=[];fake_code(monkeypatch,executed)
    store=Store(tmp_path);execute_run(store,Registry(store),run(),CONFIG,threading.Event())
    paused=store.run('run');assert paused['status']=='waiting_approval' and not executed
    assert len(calls)==1
    pending=paused['pending_approval']
    reopened=Store(tmp_path)
    execute_run(reopened,Registry(reopened),reopened.run('run'),CONFIG,threading.Event(),True,
                {'approval_id':pending['id'],'approved':approved})
    result=reopened.run('run')
    assert result['status']==('completed' if approved else 'needs_attention')
    assert len(executed)==int(approved)
    assert reopened.object('approvals',pending['id'])['status']==('approved' if approved else 'denied')
    assert len(calls)==2  # the model request preceding approval is not repeated
    assert any(x.get('encrypted_content')=='OPAQUE' for x in calls[-1]['input'])


def test_approval_api_rejects_stale_decision_and_keeps_credentials_out_of_storage(tmp_path,monkeypatch):
    model(monkeypatch,'execute_code',{'plugin_id':'python','code':'metrics={"count":1}','inputs':{}})
    executed=[];fake_code(monkeypatch,executed)
    client=TestClient(create_app(tmp_path))
    body={'message':'运行定制分析','session_id':'api-session','mode':'model',**CONFIG}
    response=client.post('/api/runs',json=body);assert response.status_code==202
    id=response.json()['id'];paused=wait(client,id)
    assert paused['status']=='waiting_approval'
    wrong=client.post('/api/runs/'+id+'/resume',json={'approval_id':'wrong','approved':True})
    assert wrong.status_code==400 and not executed
    valid=client.post('/api/runs/'+id+'/resume',json={'approval_id':paused['pending_approval']['id'],'approved':True})
    assert valid.status_code==202
    assert wait(client,id)['status']=='completed'
    assert client.post('/api/runs/'+id+'/resume',json={}).status_code==409
    for filename in ('workspace.sqlite3','checkpoints.sqlite3'):
        assert CONFIG['api_key'].encode() not in (tmp_path/filename).read_bytes()
    assert len(client.get('/api/runs?session_id=api-session').json())==1
    assert client.get('/api/runs?session_id=elsewhere').json()==[]


def test_input_changed_during_approval_is_not_executed(tmp_path,monkeypatch):
    store=Store(tmp_path);layer=store.add_layer('input',feature())
    model(monkeypatch,'execute_code',{'plugin_id':'python','code':'outputs = {}','inputs':{'data':layer['id']}})
    executed=[];fake_code(monkeypatch,executed)
    execute_run(store,Registry(store),run(),CONFIG,threading.Event())
    pending=store.run('run')['pending_approval']
    (tmp_path/'layers'/f"{layer['id']}.geojson").write_text(json.dumps(feature(1)))
    execute_run(store,Registry(store),store.run('run'),CONFIG,threading.Event(),True,{'approval_id':pending['id'],'approved':True})
    assert not executed
    assert store.run('run')['status']=='needs_attention'
    assert any(word in store.run('run')['message'] for word in ('变化','版本'))


def test_hard_process_exit_after_tool_receipt_does_not_duplicate_layer(tmp_path):
    script=tmp_path/'worker.py'
    script.write_text('''import os,sys,threading,json
from pathlib import Path
from geoagent.store import Store
from geoagent.harness import Registry,execute_run
from geoagent import durable
root=Path(sys.argv[1]);store=Store(root)
def respond(c,k,p):
    if any(x.get('type')=='function_call_output' for x in p['input']):
        return {'output':[{'type':'message','content':[{'type':'output_text','text':'done'}]}]}
    return {'output':[{'type':'function_call','call_id':'one','name':'buffer_points','arguments':json.dumps({'layer_id':store.layers()[0]['id'],'distance_m':100})}]}
durable.request_responses=respond
registry=Registry(store);registry.pre_hooks=[]
if sys.argv[2]=='crash':
    layer=store.add_layer('source',{'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':{'type':'Point','coordinates':[116,40]}}]})
    original=registry.execute
    def execute(*a,**kw):
        value=original(*a,**kw)
        if a[1]=='buffer_points':os._exit(23)
        return value
    registry.execute=execute
    run={'id':'crash','mode':'model','session_id':'s','message_input':'buffer'}
else:run=store.run('crash')
execute_run(store,registry,run,{'protocol':'responses','model':'test','base_url':'https://example.test','api_key':'SECRET'},threading.Event(),sys.argv[2]=='resume')
assert store.run('crash')['status']=='completed',store.run('crash')
assert len(store.layers())==2
''')
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]),'GEOAGENT_DISABLE_QGIS':'1'}
    first=subprocess.run([sys.executable,str(script),str(tmp_path/'workspace'),'crash'],env=env,capture_output=True,text=True)
    assert first.returncode==23,first.stderr
    store=Store(tmp_path/'workspace');assert store.run('crash')['status']=='interrupted'
    second=subprocess.run([sys.executable,str(script),str(tmp_path/'workspace'),'resume'],env=env,capture_output=True,text=True)
    assert second.returncode==0,second.stderr
    assert len(store.layers())==2
    assert any(e['type']=='tool_replayed' for e in store.events('crash'))


def test_model_cannot_mark_unmet_output_contract_complete(tmp_path,monkeypatch):
    monkeypatch.setattr(durable,'request_responses',lambda *a:final('已经导出了PDF'))
    store=Store(tmp_path)
    execute_run(store,Registry(store),run(acceptance={'formats':['pdf'],'require_layer':True}),CONFIG,threading.Event())
    result=store.run('run')
    assert result['status']=='needs_attention'
    assert not result['validation']['passed']
    assert 'pdf' in result['message']


def test_catalog_hash_invalidation_and_chinese_knowledge_search(tmp_path):
    store=Store(tmp_path);memory=Memory(store)
    parent=store.add_layer('道路',feature())
    child=store.add_layer('道路缓冲',feature(),provenance={'input_layers':[parent['id']]})
    memory.catalog()
    doc=memory.add_knowledge('道路缓冲规范','采用米制投影计算道路缓冲区，检查拓扑。','团队SOP',[parent['id']],reviewed=True)
    assert memory.search('如何做道路缓冲')[0]['id']==doc['id']
    (tmp_path/'layers'/f"{parent['id']}.geojson").write_text(json.dumps(feature(2)))
    catalog=memory.catalog()
    assert all(x['stale'] for x in catalog)
    assert not memory.search('道路缓冲')
    assert store.object('knowledge',doc['id'])['stale']
    memory.forget_knowledge(doc['id']);assert not store.objects('knowledge')


def test_code_promotion_requires_verification_review_and_unchanged_code(tmp_path,monkeypatch):
    from geoagent.learned_tools import promote
    store=Store(tmp_path);layer=store.add_layer('source',feature())
    recipe={'id':'recipe1','name':'验证算法','code':'outputs = {}','plugin_id':'python','inputs':{'data':layer['id']},'status':'draft','timeout':60}
    store.put_object('recipes',recipe['id'],recipe)
    with pytest.raises(ValueError,match='验证'):promote(store,recipe['id'],True)
    executed=[];fake_code(monkeypatch,executed)
    job=run('verify',mode='code',verify_recipe_id=recipe['id'],inputs=recipe['inputs'],verification_checks={'layer':{'min_count':1,'fields':['name']},'metrics':{'count':{'min':1,'max':1}}})
    execute_run(store,Registry(store),job,None,threading.Event())
    assert store.run('verify')['status']=='completed',store.run('verify')
    with pytest.raises(ValueError,match='检查'):promote(store,recipe['id'],False)
    promoted=promote(store,recipe['id'],True)
    registry=Registry(store);assert promoted['tool_name'] in registry.tools
    assert registry.tools[promoted['tool_name']].schema()['function']['parameters']['required']==['inputs']
    changed=store.object('recipes',recipe['id']);changed['code']='modified';store.put_object('recipes',recipe['id'],changed)
    with pytest.raises(ValueError,match='改变'):promote(store,recipe['id'],True)


def test_workflow_resumes_failed_node_without_repeating_success(tmp_path,monkeypatch):
    from geoagent.workflows import save
    from geoagent import algorithms
    store=Store(tmp_path);layer=store.add_layer('source',feature())
    workflow=save(store,'buffer then centroid',[
        {'id':'first','algorithm_id':'buffer','arguments':{'layer_id':layer['id'],'distance_m':100}},
        {'id':'second','algorithm_id':'centroid','arguments':{'layer_id':'$first.layer_id'}}])
    real=algorithms.run_algorithm;calls=[];fail=[True]
    def execute(store,id,args,run_id):
        calls.append(id)
        if id=='centroid' and fail[0]:raise ValueError('temporary worker unavailable')
        return real(store,id,args,run_id)
    monkeypatch.setattr(algorithms,'run_algorithm',execute)
    job=run('workflow',mode='workflow',workflow_id=workflow['id'])
    execute_run(store,Registry(store),job,None,threading.Event())
    assert store.run('workflow')['status']=='failed'
    assert calls==['buffer','centroid'] and len(store.layers())==2
    fail[0]=False;reopened=Store(tmp_path)
    execute_run(reopened,Registry(reopened),reopened.run('workflow'),None,threading.Event(),True)
    assert reopened.run('workflow')['status']=='completed',reopened.run('workflow')
    assert calls==['buffer','centroid','centroid'] and len(reopened.layers())==3
    assert len(reopened.objects('workflow_runs'))==1
    assert all(x['status']=='completed' for x in reopened.setting('plan:workflow')['steps'])


def test_uncertain_side_effect_requires_review_before_retry(tmp_path,monkeypatch):
    model(monkeypatch,'buffer_points',{'layer_id':'placeholder','distance_m':100})
    store=Store(tmp_path);layer=store.add_layer('source',feature())
    model(monkeypatch,'buffer_points',{'layer_id':layer['id'],'distance_m':100})
    registry=Registry(store);registry.pre_hooks=[]
    real=registry.tools['buffer_points'].handler
    def crash(args,r):
        real(args,r)
        raise KeyboardInterrupt('crash after output, before receipt')
    registry.tools['buffer_points'].handler=crash
    with pytest.raises(KeyboardInterrupt):execute_run(store,registry,run(),CONFIG,threading.Event())
    assert len(store.layers())==2
    reopened=Store(tmp_path);registry=Registry(reopened);registry.pre_hooks=[]
    execute_run(reopened,registry,reopened.run('run'),CONFIG,threading.Event(),True)
    paused=reopened.run('run')
    assert paused['status']=='waiting_approval' and '可能已有输出' in paused['pending_approval']['reason']
    assert len(reopened.layers())==2
    execute_run(reopened,registry,paused,CONFIG,threading.Event(),True,{'approval_id':paused['pending_approval']['id'],'approved':False})
    assert len(reopened.layers())==2
    assert reopened.run('run')['status']=='needs_attention'


def test_missing_export_blocks_acceptance(tmp_path,monkeypatch):
    store=Store(tmp_path)
    store.put_object('exports','missing',{'id':'missing','run_id':'run','format':'pdf','name':'missing.pdf','path':'exports/missing.pdf'})
    monkeypatch.setattr(durable,'request_responses',lambda *a:final())
    execute_run(store,Registry(store),run(),CONFIG,threading.Event())
    assert store.run('run')['status']=='needs_attention'
    assert '丢失' in store.run('run')['message']


def test_offline_layer_list_does_not_match_map_export(tmp_path):
    store=Store(tmp_path);store.add_layer('source',feature())
    execute_run(store,Registry(store),run(mode='offline',message_input='列出图层'),None,threading.Event())
    assert store.run('run')['status']=='completed'
    assert not store.objects('exports')
    assert not any(s['name']=='export_map' for s in store.steps('run'))


def test_empty_layer_is_valid_but_reported_as_empty(tmp_path,monkeypatch):
    store=Store(tmp_path);layer=store.add_layer('empty',{'type':'FeatureCollection','features':[]})
    model(monkeypatch,'inspect_layer',{'layer_id':layer['id']})
    execute_run(store,Registry(store),run(),CONFIG,threading.Event())
    result=store.run('run')
    assert result['status']=='completed',result
    assert any('为空' in x for x in result['validation']['warnings'])


@pytest.mark.skipif(os.environ.get('GEOAGENT_NATIVE_TESTS')!='1',reason='Native QGIS / Seatbelt integration is opt-in')
def test_native_qgis_through_durable_harness_and_acceptance(tmp_path,monkeypatch):
    import geopandas as gpd
    from shapely.geometry import Point
    from geoagent import formats
    monkeypatch.delenv('GEOAGENT_DISABLE_QGIS',raising=False)
    store=Store(tmp_path)
    layer=formats.add_frame(store,'stations',gpd.GeoDataFrame({'name':['A']},geometry=[Point(550000,5180000)],crs=32610),{})
    job=run('native',mode='algorithm',algorithm_id='qgis:native:buffer',arguments={
        'INPUT':layer['id'],'DISTANCE':100,'SEGMENTS':32,'END_CAP_STYLE':0,'JOIN_STYLE':0,'MITER_LIMIT':2,'DISSOLVE':False},
        acceptance={'require_layer':True,'layer':{'crs':'EPSG:32610','min_count':1,'max_count':1,'fields':['name']}})
    execute_run(store,Registry(store),job,None,threading.Event())
    done=store.run('native');assert done['status']=='completed',done
    assert done['validation']['passed'] and len(done['output_layers'])==1
    output=formats.frame(store,done['output_layers'][0]).to_crs(32610)
    assert output.area.iloc[0]==pytest.approx(31415.9265,rel=.001)
