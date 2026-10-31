import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from geoagent.app import create_app
from geoagent.plugins import runtime


def test_workspace_lease_and_pid_probe(tmp_path):
    import subprocess,sys
    from geoagent.process_utils import WorkspaceLease,process_alive
    lease=WorkspaceLease(tmp_path/'execution.lock')
    with pytest.raises(BlockingIOError):WorkspaceLease(tmp_path/'execution.lock')
    lease.close()
    WorkspaceLease(tmp_path/'execution.lock').close()
    child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
    try:
        assert process_alive(child.pid)
        assert child.poll() is None
    finally:child.terminate();child.wait()
    assert not process_alive(child.pid)


def test_desktop_auth_all_routes(tmp_path,monkeypatch):
    monkeypatch.setenv('GAIA_DESKTOP_TOKEN','private-desktop-token-1234567890abcdef')
    client=TestClient(create_app(tmp_path))
    assert client.get('/api/health').status_code==401
    assert client.get('/').status_code==401
    assert client.get('/api/layers',headers={'x-gaia-token':'wrong'}).status_code==401
    headers={'x-gaia-token':os.environ['GAIA_DESKTOP_TOKEN']}
    assert client.get('/api/health',headers=headers).status_code==200
    assert client.post('/demo',headers={**headers,'Origin':'https://other.example'}).status_code==403


def test_desktop_paths_are_external_and_platform_aware(tmp_path,monkeypatch):
    monkeypatch.setenv('GEOAGENT_CACHE_DIR',str(tmp_path/'cache'))
    monkeypatch.setenv('GIS_PYTHON',str(tmp_path/'python.exe'))
    assert runtime.cache_root()==tmp_path/'cache'
    assert runtime.python_executable()==tmp_path/'python.exe'
    assert runtime.runtime_prefix(tmp_path/'python.exe')==tmp_path
    assert runtime.runtime_prefix(tmp_path/'bin/python')==tmp_path


@pytest.mark.skipif(os.environ.get('GAIA_DESKTOP_NATIVE_TESTS')!='1',reason='Real desktop runtime test')
def test_local_code_isolation_and_qgis(tmp_path):
    import threading
    import geopandas as gpd
    from shapely.geometry import Point
    from geoagent.store import Store
    from geoagent import formats,cartography
    from geoagent.plugins import PluginManager
    store=Store(tmp_path/'workspace')
    secret=tmp_path/'private.txt';secret.write_text('private')
    code=f"""from pathlib import Path
import os,socket
metrics['secret_present']='GAIA_DESKTOP_TOKEN' in os.environ
for name,fn in [('read',lambda:Path({str(secret)!r}).read_text()),('write',lambda:Path({str(tmp_path/'escape.txt')!r}).write_text('x')),('network',lambda:socket.create_connection(('1.1.1.1',443),timeout=2))]:
 try:fn();metrics[name]='allowed'
 except PermissionError:metrics[name]='denied'
p=output_dir/'test.txt'
p.write_text('ok')
outputs['test']=str(p)
"""
    answer=PluginManager(store).get('python').execute_code(store,code,{},'desktop',threading.Event())
    assert answer['scalars']=={'secret_present':False,'read':'denied','write':'denied','network':'denied'}
    qgis=PluginManager(store).get('qgis')
    layer=formats.add_frame(store,'Test points',gpd.GeoDataFrame({'name':['A']},geometry=[Point(500000,4400000)],crs=32650),{})
    result=qgis.execute(store,'qgis:native:buffer',{'INPUT':layer['id'],'DISTANCE':100},'desktop',threading.Event())
    assert store.get_layer(result['layer_id'])['count']==1
    cartography.update_layout(store,{'plugin_id':'qgis','focus_layer_id':result['layer_id'],'map_crs':'EPSG:32650','title':'Desktop native map','legend_position':'outside-right'})
    exported=cartography.export_map(store,'pdf',100)
    assert (store.root/exported['path']).read_bytes().startswith(b'%PDF')
    assert exported['quality']['cartography']['passed']
    saved=store.object('settings','last_qgis_project')
    assert (store.root/saved['path']).stat().st_size>0
    reopened=qgis.open_project(store,saved['id'])
    assert len(reopened['layers'])==2
