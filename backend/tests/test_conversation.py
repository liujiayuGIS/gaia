import threading

import pytest
from fastapi.testclient import TestClient

from geoagent.app import create_app
from geoagent import durable
from geoagent.harness import Registry,execute_run
from geoagent.store import Store
from geoagent.conversation import evidence,answer_validation
from test_durable import CONFIG,final,feature,model_call,wait


def original(store,id='original',session='chat',**changes):
    value={'id':id,'mode':'offline','session_id':session,'status':'completed','message_input':'删除测试图层',
           'message':'已删除，源文件保留。','output_layers':[],**changes};store.save_run(value);return value


def test_message_reference_is_session_bound_validated_and_persisted(tmp_path):
    app=create_app(tmp_path);s=app.state.store;original(s)
    with TestClient(app) as client:
        reference={'run_id':'original','role':'assistant','excerpt':'源文件保留'}
        response=client.post('/api/runs',json={'message':'列出图层','session_id':'chat','reply_to':reference})
        assert response.status_code==202
        run=wait(client,response.json()['id']);assert run['reply_to']['excerpt']==reference['excerpt']
        assert len(run['reply_to']['source_sha256'])==64
        for ref in ({**reference,'run_id':'missing'},{**reference,'excerpt':'伪造引用'}):
            assert client.post('/api/runs',json={'message':'继续','session_id':'chat','reply_to':ref}).status_code==400
        assert client.post('/api/runs',json={'message':'继续','session_id':'other','reply_to':reference}).status_code==400
        assert client.post('/api/runs',json={'message':'继续','session_id':'other','edit_of':'original'}).status_code==400
    assert Store(tmp_path).run(run['id'])['reply_to']==run['reply_to']


def test_feedback_roundtrip_does_not_change_execution_record(tmp_path):
    app=create_app(tmp_path);s=app.state.store;before=original(s)
    with TestClient(app) as client:
        for value in ('up','down'):
            assert client.patch('/api/runs/original/feedback',json={'value':value}).status_code==200
            assert client.get('/api/runs/original').json()['feedback']['value']==value
        assert s.run('original')==before
        assert client.patch('/api/runs/original/feedback',json={'value':'approve'}).status_code==422
        assert client.patch('/api/runs/missing/feedback',json={'value':'up'}).status_code==404
        assert client.patch('/api/runs/original/feedback',json={'value':None}).json() is None
        assert client.get('/api/runs/original').json()['feedback'] is None


def test_offline_reanswer_preserves_layers_and_old_run(tmp_path):
    app=create_app(tmp_path);s=app.state.store;a=s.add_layer('测试图层',feature());before=original(s)
    with TestClient(app) as client:
        started=client.post('/api/runs',json={'session_id':'chat','message':'重新回答','reanswer_of':'original','selected_layers':[a['id']]})
        assert started.status_code==202
        run=wait(client,started.json()['id'])
        assert run['status']=='completed' and not s.steps(run['id'])
        assert run['validation']['checks']==['answer_only','no_GIS_tool_execution']
        assert run['selected_layers']==[] and s.layers()==[a] and s.run('original')==before
        assert '离线模式仅重述原记录' in run['message']
        invalid=[{'session_id':'other'},{'algorithm_id':'buffer','arguments':{'layer_id':a['id'],'distance_m':10}},{'mode':'code','code':'outputs={}'}]
        for extra in invalid:
            assert client.post('/api/runs',json={'session_id':'chat','message':'重新回答','reanswer_of':'original',**extra}).status_code==400


@pytest.mark.parametrize('protocol',['responses','chat_completions'])
@pytest.mark.parametrize('malicious',[False,True])
def test_reanswer_never_exposes_or_executes_tools(tmp_path,monkeypatch,protocol,malicious):
    s=Store(tmp_path);a=s.add_layer('保护图层',feature());source=original(s,status='failed',message='处理失败，尚未核验。')
    called=[]
    def response(client,config,payload):
        called.append(payload);assert not payload.get('tools')
        if protocol=='responses':return model_call('remove_layer',{'layer_id':a['id']}) if malicious else final('原任务失败，尚不能给出新结果。')
        msg={'role':'assistant','content':'原任务失败，尚不能给出新结果。'}
        if malicious:msg['tool_calls']=[{'id':'delete','type':'function','function':{'name':'remove_layer','arguments':'{"layer_id":"'+a['id']+'"}'}}]
        return {'choices':[{'finish_reason':'stop','message':msg}]}
    monkeypatch.setattr(durable,'request_responses' if protocol=='responses' else 'request_completion',response)
    run={'id':'rewrite','session_id':'chat','mode':'model','message_input':'重新回答','reanswer_of':source['id'],'answer_source':evidence(s,source)}
    execute_run(s,Registry(s),run,{**CONFIG,'protocol':protocol},threading.Event())
    result=s.run('rewrite');assert result['status']==('failed' if malicious else 'completed'),result['message']
    assert not s.steps('rewrite') and s.layers()==[a]
    assert '处理失败' in str(called) and '只读' in str(called)
    assert s.run('original')==source


def test_repeated_reanswer_keeps_original_failure_evidence(tmp_path):
    s=Store(tmp_path);source=original(s,status='failed',message='原始核验失败')
    rewritten=original(s,'variant',reanswer_of='original',answer_source=evidence(s,source),message='改写的说明')
    result=evidence(s,rewritten)
    assert result['run_id']=='original' and result['status']=='failed' and result['answer']=='原始核验失败'
    assert result['previous_answer']=='改写的说明'
    assert answer_validation(rewritten)['unverified']
