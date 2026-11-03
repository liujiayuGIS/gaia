import hashlib
import threading

import pytest
from fastapi.testclient import TestClient

from geoagent.app import create_app
from geoagent.execution import scope
from geoagent.harness import Registry, execute_run
from geoagent.memory import Memory
from geoagent.store import Store
from test_layer_order import polygon, raster


def hashes(store):
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (store.root/'layers').iterdir() if p.is_file()}


def test_remove_restore_vector_and_raster_persistence_and_layout(tmp_path):
    app=create_app(tmp_path/'workspace');s=app.state.store
    a=polygon(s,'甲','#e63636');b=polygon(s,'乙','#2463db');c=raster(s,tmp_path)
    ids=[a['id'],c['id'],b['id']];s.reorder_layers(ids)
    s.put_object('settings','layout',{'focus_layer_id':a['id'],'context_layer_id':a['id'],'template_bindings':{'main':a['id'],'other':c['id']}})
    before=hashes(s)
    with TestClient(app) as client:
        for id in (a['id'],c['id']):
            result=client.delete('/api/layers/'+id)
            assert result.status_code==200 and result.json()['removed_id']==id
            assert client.get('/api/layers/'+id+'/data').status_code==400
            assert client.delete('/api/layers/'+id).status_code==200
        assert [x['id'] for x in client.get('/api/layers').json()]==[b['id']]
        assert client.delete('/api/layers/unknown').status_code==400
        assert client.post('/api/layers/unknown/restore').status_code==400
    assert hashes(s)==before
    layout=s.setting('layout');assert layout['focus_layer_id'] is None and layout['context_layer_id'] is None
    assert not layout['template_bindings']  # both referenced layers were removed
    reopened=Store(s.root)
    for id in (c['id'],a['id']):reopened.restore_layer(id)
    assert [x['id'] for x in reopened.ordered_layers()]==ids
    assert reopened.restore_layer(a['id'])==a
    assert hashes(reopened)==before
    assert reopened.get_layer(c['id'])['kind']=='raster'
    for id in ids:reopened.remove_layer(id)
    assert Store(s.root).ordered_layers()==[]
    assert hashes(reopened)==before


def test_history_catalog_and_api_export_survive_removal(tmp_path):
    app=create_app(tmp_path);s=app.state.store
    a=polygon(s,'历史成果','#e63636')
    s.save_run({'id':'history','mode':'offline','status':'completed','message_input':'测试','message':'完成','output_layers':[a['id']]})
    before=Memory(s).catalog()[0]['content_hash'];s.remove_layer(a['id'])
    assert Memory(s).catalog()==[]
    assert Memory(s).fingerprint(a['id'],include_removed=True)[0]==before
    from geoagent.spatial_contracts import semantic_metadata
    assert semantic_metadata(s,a['id'],include_removed=True)=={}
    with pytest.raises(ValueError):Memory(s).fingerprint(a['id'])
    with TestClient(app) as client:
        result=client.get('/api/runs/history/export')
        assert result.status_code==200
        assert result.json()['artifacts'][0]['workspace_removed'] is True


def test_agent_receipt_replay_does_not_remove_a_restored_layer(tmp_path):
    s=Store(tmp_path);a=polygon(s,'数据','#e63636');registry=Registry(s);cancel=threading.Event()
    s.save_run({'id':'test','mode':'model','status':'running'})
    with scope(registry,'turn'):
        assert registry.execute('test','inspect_layer',{'layer_id':a['id']},cancel)['success']
        result=registry.execute('test','remove_layer',{'layer_id':a['id']},cancel)
        assert result['success'] and result['validation']['checks'][0]=='absent_from_workspace'
    # Reading then removing is replayable without re-executing the deletion.
    with scope(registry,'turn'):
        assert registry.execute('test','inspect_layer',{'layer_id':a['id']},cancel)['success']
        assert registry.execute('test','remove_layer',{'layer_id':a['id']},cancel)['success']
    assert len(s.events('test'))>0 and not s.layers()
    s.restore_layer(a['id'])
    with scope(registry,'turn'):
        registry.execute('test','inspect_layer',{'layer_id':a['id']},cancel)
        with pytest.raises(ValueError,match='删除或恢复状态'):registry.execute('test','remove_layer',{'layer_id':a['id']},cancel)
    assert s.get_layer(a['id'])==a


def test_offline_natural_language_remove_restore_and_ambiguity(tmp_path):
    s=Store(tmp_path);a=polygon(s,'西安市_地铁站点','#e63636');b=polygon(s,'其他图层','#2463db')
    def task(id,message):
        execute_run(s,Registry(s),{'id':id,'mode':'offline','session_id':'test','message_input':message},None,threading.Event())
        value=s.run(id);assert value['status']=='completed',value['message'];return value['message']
    assert '已删除' in task('delete','删除有1个要素的这个西安市_地铁站点图层')
    assert [x['id'] for x in s.layers()]==[b['id']]
    assert '已恢复' in task('undo','恢复图层 西安市_地铁站点')
    task('ambiguous','删除有1个要素的这个图层')
    assert len(s.layers())==2
    task('wrong-count','删除有582个要素的西安市_地铁站点图层')
    assert len(s.layers())==2


def test_model_loop_can_invoke_registered_removal(tmp_path,monkeypatch):
    from geoagent import durable
    import json
    s=Store(tmp_path);a=polygon(s,'地铁站','#e63636');requests=[]
    def respond(client,config,payload):
        requests.append(payload)
        if any(x.get('type')=='function_call_output' for x in payload['input']):
            return {'id':'done','output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'图层已删除，源数据保留。'}]}]}
        assert any(x['name']=='remove_layer' for x in payload['tools'])
        return {'id':'remove','output':[{'type':'function_call','call_id':'delete','name':'remove_layer','arguments':json.dumps({'layer_id':a['id']})}]}
    monkeypatch.setattr(durable,'request_responses',respond)
    execute_run(s,Registry(s),{'id':'model-delete','mode':'model','session_id':'test','message_input':'删除地铁站图层'},
                {'base_url':'https://example.test/v1','model':'test','api_key':'fake','protocol':'responses','reasoning_effort':'medium'},threading.Event())
    result=s.run('model-delete')
    assert result['status']=='completed',result['message']
    assert not s.layers() and len(requests)==2 and result['validation']['passed']
