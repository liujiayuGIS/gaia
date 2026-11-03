import json
import threading
import httpx
import pytest
from fastapi.testclient import TestClient
from geoagent.provider import completion_payload, error_details, resolve_config, test_connection as check_connection
from geoagent.app import create_app
from geoagent.harness import Registry, execute_run
from geoagent.store import Store


def test_openai_reasoning_payload_and_preserved_model():
    config=resolve_config(' https://api.openai.com/v1/ ','gpt-5.6-sol',' test-key ')
    payload=completion_payload(config,[{'role':'user','content':'Hi'}],[])
    assert payload['model']=='gpt-5.6-sol'
    assert 'max_completion_tokens' in payload
    assert 'max_tokens' not in payload and 'temperature' not in payload
    assert config['api_key']=='test-key'


def test_deepseek_request_keeps_supported_parameters():
    payload=completion_payload({'model':'deepseek-chat','base_url':'https://api.deepseek.com'},[],[])
    assert payload['max_tokens']==8192
    assert payload['temperature']==.1
    assert 'max_completion_tokens' not in payload


def test_error_diagnostics_preserve_cause_and_redact_credentials():
    response=httpx.Response(400,json={'error':{'code':'unsupported_parameter','param':'max_tokens',
        'message':'Unsupported parameter max_tokens. SECRET_EXACT_KEY sk-proj-visible-prefix Bearer other-secret'}})
    details=error_details(response,'SECRET_EXACT_KEY')
    assert details['param']=='max_tokens'
    assert 'unsupported_parameter' in details['message']
    assert 'SECRET_EXACT_KEY' not in details['message']
    assert 'sk-proj-visible-prefix' not in details['message']
    assert 'other-secret' not in details['message']


def test_non_json_error_does_not_echo_html_or_credentials():
    response=httpx.Response(404,text='<html>private content SECRET_KEY</html>')
    details=error_details(response,'SECRET_KEY')
    assert '404' in details['message']
    assert 'private content' not in details['message']


def test_config_rejects_wrong_openai_path_and_missing_key():
    with pytest.raises(ValueError,match='/v1'):
        resolve_config('https://api.openai.com','gpt-5.6-sol','key')
    with pytest.raises(ValueError,match='API 根地址'):
        resolve_config('https://api.openai.com/v1/chat/completions','gpt-5.6-sol','key')
    with pytest.raises(ValueError,match='API Key'):
        resolve_config('https://api.openai.com/v1','gpt-5.6-sol','')


def test_diagnostic_endpoint_sends_no_workspace_data_or_saved_key(tmp_path,monkeypatch):
    seen=[]
    def respond(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200,json={'model':'gpt-5.6-sol','status':'completed','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'OK'}]}]})
    original=httpx.Client
    monkeypatch.setattr('geoagent.provider.httpx.Client',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    client=TestClient(create_app(tmp_path))
    result=client.post('/api/model/test',json={'base_url':'https://api.openai.com/v1','model':'gpt-5.6-sol','api_key':'SECRET_NOT_STORED'})
    assert result.status_code==200 and result.json()['ok']
    assert seen[0]['input']==[{'role':'user','content':'请只回复 OK。'}]
    assert seen[0]['tool_choice']=='none'
    assert seen[0]['reasoning']=={'effort':'medium'}
    assert client.get('/api/runs').json()==[]
    assert b'SECRET_NOT_STORED' not in (tmp_path/'workspace.sqlite3').read_bytes()


def test_model_error_is_logged_with_actionable_safe_details(tmp_path,monkeypatch):
    def respond(request):
        return httpx.Response(404,json={'error':{'code':'model_not_found','message':'The model is not available for SECRET_KEY'}})
    original=httpx.Client
    monkeypatch.setattr('geoagent.provider.httpx.Client',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    store=Store(tmp_path)
    run={'id':'r','mode':'model','session_id':'s','message_input':'Hi'}
    execute_run(store,Registry(store),run,{'base_url':'https://api.openai.com/v1','model':'gpt-5.6-sol','api_key':'SECRET_KEY'},threading.Event())
    result=store.run('r')
    assert result['status']=='failed' and 'model_not_found' in result['message']
    assert any(e['type']=='model_error' for e in store.events('r'))
    assert 'SECRET_KEY' not in json.dumps(store.events('r'))


@pytest.mark.parametrize('model',['gpt-5.6-sol','gpt-5.6','gpt-5.6-sol-2026-07-09'])
def test_sol_chat_function_calls_use_supported_reasoning_mode(model):
    tools=[{'type':'function','function':{'name':'list_layers','parameters':{'type':'object','properties':{}}}}]
    payload=completion_payload({'model':model,'base_url':'https://api.openai.com/v1'},[],tools)
    assert payload['reasoning_effort']=='none'
    assert payload['model']==model
    assert payload['tools']==tools


@pytest.mark.parametrize('model',['gpt-6-astra','gpt-6.1-sol','o3','deepseek-chat'])
def test_sol_compatibility_rule_does_not_disable_other_models_reasoning(model):
    payload=completion_payload({'model':model,'base_url':'https://api.openai.com/v1'},[],[{'type':'function'}])
    assert 'reasoning_effort' not in payload


def test_responses_preserves_reasoning_items_and_tool_call_outputs(tmp_path,monkeypatch):
    calls=[]
    reasoning={'type':'reasoning','id':'rs_1','encrypted_content':'ENCRYPTED_OPAQUE','summary':[]}
    function={'type':'function_call','id':'fc_1','call_id':'call_1','name':'list_layers','arguments':'{}','status':'completed'}
    def respond(request):
        payload=json.loads(request.content);calls.append(payload)
        assert request.url.path=='/v1/responses'
        if len(calls)==1:
            output=[reasoning,function]
        else:
            assert reasoning in payload['input'] and function in payload['input']
            assert any(x.get('type')=='function_call_output' and x['call_id']=='call_1' for x in payload['input'])
            output=[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'已读取工作区。'}]}]
        return httpx.Response(200,json={'id':'resp_'+str(len(calls)),'status':'completed','output':output,'usage':{'input_tokens':10,'output_tokens':5}})
    original=httpx.Client
    monkeypatch.setattr('geoagent.provider.httpx.Client',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    store=Store(tmp_path);run={'id':'responses','mode':'model','session_id':'s','message_input':'读取图层'}
    execute_run(store,Registry(store),run,{'base_url':'https://api.openai.com/v1','model':'gpt-5.6-sol','api_key':'SECRET_KEY','protocol':'responses','reasoning_effort':'medium'},threading.Event())
    assert store.run('responses')['status']=='completed'
    assert calls[0]['reasoning']=={'effort':'medium'} and calls[0]['store'] is False
    assert 'reasoning.encrypted_content' in calls[0]['include']
    assert 'SECRET_KEY' not in json.dumps(store.events('responses'))


def test_output_limit_can_resume_with_larger_budget_without_executing_partial_calls(tmp_path,monkeypatch):
    import time
    payloads=[]
    def respond(request):
        payload=json.loads(request.content);payloads.append(payload)
        if len(payloads)==1:
            message={'role':'assistant','content':None,'tool_calls':[{'id':'safe','type':'function',
                'function':{'name':'list_layers','arguments':'{}'}}]};finish='tool_calls'
        elif len(payloads)==2:
            message={'role':'assistant','content':None,'tool_calls':[{'id':'partial','type':'function',
                'function':{'name':'style_layer','arguments':'{"layer_id":'}}]};finish='length'
        else:
            assert payload['max_completion_tokens']==16384
            assert not any(call['id']=='partial' for item in payload['messages'] for call in item.get('tool_calls',[]))
            message={'role':'assistant','content':'已读取图层。'};finish='stop'
        return httpx.Response(200,json={'id':'response','choices':[{'message':message,'finish_reason':finish}],
                                       'usage':{'completion_tokens':2048}})
    original=httpx.Client
    monkeypatch.setattr('geoagent.provider.httpx.Client',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    store=Store(tmp_path);run={'id':'length','mode':'model','session_id':'s','message_input':'读取图层'}
    config=resolve_config('https://api.openai.com/v1','test-model','SECRET_KEY','chat_completions',max_output_tokens=2048)
    execute_run(store,Registry(store),run,config,threading.Event())
    failed=store.run('length')
    assert failed['status']=='failed' and failed['resumable'] and '2048 tokens' in failed['message']
    assert len(store.steps('length'))==1 and store.steps('length')[0]['name']=='list_layers'
    client=TestClient(create_app(tmp_path))
    assert client.post('/api/runs/length/resume',json={'api_key':'SECRET_KEY','max_output_tokens':16384}).status_code==202
    deadline=time.monotonic()+10
    while time.monotonic()<deadline and store.run('length')['status'] in ('queued','running'):
        time.sleep(.02)
    assert store.run('length')['status']=='completed'
    assert len(store.steps('length'))==1
    assert store.run('length')['model_config']['max_output_tokens']==16384
    assert 'SECRET_KEY' not in json.dumps(store.events('length'))


def test_responses_incomplete_budget_has_actionable_diagnostics():
    from geoagent.provider import request_responses,ProviderError,responses_payload
    config=resolve_config('https://api.openai.com/v1','test-model','SECRET_KEY','responses',max_output_tokens=16384)
    payload=responses_payload(config,[],[],'test')
    assert payload['max_output_tokens']==16384
    with httpx.Client(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={
            'status':'incomplete','output':[],'incomplete_details':{'reason':'max_output_tokens'}}))) as client:
        with pytest.raises(ProviderError) as caught:request_responses(client,config,payload)
    assert caught.value.details['code']=='output_limit'
    assert '16384 tokens' in str(caught.value) and '检查点' in str(caught.value)


@pytest.mark.parametrize('budget',[0,True,32769,None])
def test_invalid_output_budgets_are_rejected_before_request(budget):
    with pytest.raises(ValueError,match='输出预算'):
        resolve_config('https://api.openai.com/v1','test-model','key',max_output_tokens=budget)


def test_deepseek_reasoning_content_is_replayed_with_tool_results(tmp_path,monkeypatch):
    seen=[]
    def respond(request):
        payload=json.loads(request.content);seen.append(payload)
        assert payload['model']=='deepseek-reasoner' and payload['max_tokens']==8192
        assert 'max_completion_tokens' not in payload and 'temperature' not in payload
        assert all('reasoning_content' in message for message in payload['messages'] if message.get('role')=='assistant')
        if len(seen)==1:
            message={'role':'assistant','content':None,'reasoning_content':'TEST_PROVIDER_STATE',
                'tool_calls':[{'id':'call_1','type':'function','function':{'name':'list_layers','arguments':'{}'}}]}
        elif len(seen)==2:
            assert any(x.get('reasoning_content')=='TEST_PROVIDER_STATE' for x in payload['messages'])
            assert any(x.get('role')=='tool' and x.get('tool_call_id')=='call_1' for x in payload['messages'])
            message={'role':'assistant','content':'已读取图层。','reasoning_content':'TEST_FINAL_STATE'}
        else:
            assert any('已读取图层' in (x.get('content') or '') for x in payload['messages'])
            message={'role':'assistant','content':'已结合上次记录回答。','reasoning_content':'TEST_NEXT_RUN_STATE'}
        return httpx.Response(200,json={'choices':[{'message':message,'finish_reason':'tool_calls' if len(seen)==1 else 'stop'}]})
    original=httpx.Client
    monkeypatch.setattr('geoagent.provider.httpx.Client',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    store=Store(tmp_path);run={'id':'deepseek','mode':'model','session_id':'s','message_input':'读取图层'}
    config=resolve_config('https://api.deepseek.com','deepseek-reasoner','TEST_KEY')
    execute_run(store,Registry(store),run,config,threading.Event())
    assert store.run('deepseek')['status']=='completed' and len(seen)==2
    assert 'TEST_PROVIDER_STATE' not in json.dumps(store.events('deepseek'))
    execute_run(store,Registry(store),{'id':'deepseek-next','mode':'model','session_id':'s','message_input':'根据上次记录回答'},config,threading.Event())
    assert store.run('deepseek-next')['status']=='completed' and len(seen)==3
