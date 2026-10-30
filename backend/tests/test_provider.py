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
    assert payload['max_tokens']==2000
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
        return httpx.Response(200,json={'model':'gpt-5.6-sol','choices':[{'message':{'role':'assistant','content':'OK'}}]})
    original=httpx.Client
    monkeypatch.setattr('geoagent.provider.httpx.Client',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    client=TestClient(create_app(tmp_path))
    result=client.post('/api/model/test',json={'base_url':'https://api.openai.com/v1','model':'gpt-5.6-sol','api_key':'SECRET_NOT_STORED'})
    assert result.status_code==200 and result.json()['ok']
    assert seen[0]['messages']==[{'role':'user','content':'请只回复 OK。'}]
    assert seen[0]['tool_choice']=='none'
    assert seen[0]['reasoning_effort']=='none'
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
