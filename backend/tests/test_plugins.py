import io
import os
import json
import threading
import zipfile
from pathlib import Path
import geopandas as gpd
import pytest
from shapely.geometry import Point
from geoagent.store import Store
from geoagent import formats,cartography
from geoagent.skills import SkillManager
from geoagent.plugins import PluginManager
from geoagent.plugins.manager import register,_FACTORIES
from geoagent.plugins.base import AnalysisPlugin


def test_plugin_contract_selection_toggle_and_inputs(tmp_path):
    class Example(AnalysisPlugin):
        id='example';name='Example'
        def status(self):return {'available':True,'operations':['analysis']}
        def algorithms(self):return [{'id':'example:merge','name':'Merge','category':'vector','parameters':{'INPUT':{'type':'layers'}}}]
        def execute(self,*args):return {'ok':True}
    register('example',Example)
    try:
        manager=PluginManager(Store(tmp_path));assert manager.input_ids('example:merge',{'INPUT':['a','b']})==['a','b']
        assert manager.choose('analysis','example').id=='example'
        manager.toggle('example',False)
        with pytest.raises(ValueError,match='停用'):manager.get('example')
    finally:_FACTORIES.pop('example')


def test_skill_package_roundtrip_and_traversal(tmp_path):
    manager=SkillManager(Store(tmp_path));content=b'---\nname: sample\ndescription: Spatial recipe\nversion: 2\n---\nInspect CRS before analysis.'
    z=io.BytesIO()
    with zipfile.ZipFile(z,'w') as f:
        f.writestr('package/SKILL.md',content);f.writestr('package/references/note.txt','units are metres')
    s=manager.install('sample.zip',z.getvalue());assert s['name']=='sample'
    assert manager.read(s['id'])['body']=='Inspect CRS before analysis.'
    assert manager.resource(s['id'],'references/note.txt')['text']=='units are metres'
    with pytest.raises(ValueError):manager.resource(s['id'],'../../outside')
    with pytest.raises(ValueError):manager.install('broken.md',b'not a skill')
    assert any(x['id']==s['id'] for x in manager.list())
    with pytest.raises(ValueError,match='ZIP'):manager.install('broken.zip',b'not a zip')
    bad=io.BytesIO()
    with zipfile.ZipFile(bad,'w') as f:f.writestr('../escape',content)
    with pytest.raises(ValueError,match='不安全'):manager.install('bad.zip',bad.getvalue())


@pytest.mark.parametrize('items',[{'../x':{}},{'title':{'width':0}},{'title':{'x':float('inf')}},{'title':{'picture_path':'/private/x'}},{'map':{'map_extent':[1,2,0,0]}}])
def test_layout_geometry_rejects_invalid_paths_and_dimensions(tmp_path,items):
    with pytest.raises(ValueError):cartography.update_layout(Store(tmp_path),{'items':items})


@pytest.mark.skipif(os.environ.get('GEOAGENT_NATIVE_TESTS')!='1',reason='Native QGIS / Seatbelt integration is opt-in')
def test_native_geometry_code_sandbox_and_project_roundtrip(tmp_path,monkeypatch):
    monkeypatch.delenv('GEOAGENT_DISABLE_QGIS',raising=False)
    store=Store(tmp_path/'workspace');frame=gpd.GeoDataFrame({'name':['A','B']},geometry=[Point(550000,5180000),Point(552000,5181000)],crs=32610)
    layer=formats.add_frame(store,'stations',frame,{})
    qgis=PluginManager(store).get('qgis')
    result=qgis.execute(store,'qgis:native:buffer',{'INPUT':layer['id'],'DISTANCE':100,'SEGMENTS':20,'END_CAP_STYLE':0,'JOIN_STYLE':0,'MITER_LIMIT':2,'DISSOLVE':False},None,threading.Event())
    output=formats.frame(store,result['layer_id']).to_crs(32610)
    assert len(output)==2 and output.area.iloc[0]==pytest.approx(3.14159265*10000,rel=.002)
    assert store.get_layer(result['layer_id'])['provenance']['plugin']=='qgis'
    secret=tmp_path/'canary.txt';secret.write_text('private-canary')
    monkeypatch.setenv('OPENAI_API_KEY','dummy-not-a-real-key')
    code=f"from pathlib import Path\nimport socket,os\nfor key,fn in [('read',lambda:Path({str(secret)!r}).read_text()),('write',lambda:Path({str(tmp_path/'escape.txt')!r}).write_text('x')),('network',lambda:socket.socket().connect(('127.0.0.1',8766)))]:\n try:fn();metrics[key]='allowed'\n except PermissionError:metrics[key]='denied'\nmetrics['secret_present']='OPENAI_API_KEY' in os.environ"
    report=PluginManager(store).get('python').execute_code(store,code,{},None,threading.Event())['scalars']
    assert report=={'read':'denied','write':'denied','network':'denied','secret_present':False}
    cartography.update_layout(store,{'plugin_id':'qgis','focus_layer_id':result['layer_id'],'map_crs':'EPSG:32610','title':'Native print test','legend_position':'outside-right','items':{'title':{'x':21,'width':190}}})
    scene=qgis.scene(store,cartography.get_layout(store),store.layers());title=next(x for x in scene['elements'] if x['id']=='title')
    assert title['x']==pytest.approx(21) and title['width']==pytest.approx(190)
    pdf=cartography.render_map(store,'pdf',100);assert pdf.startswith(b'%PDF')
    project=qgis.save_project(store,'Native roundtrip');assert (store.root/project['path']).is_file()
    template=qgis.save_template(store,'Reusable print');assert (store.root/template['path']).is_file()
    restored=qgis.open_project(store,project['id']);assert restored['restored_layers']==2
    assert cartography.get_layout(store)['items']['title']['x']==21
    cartography.update_layout(store,{'template_id':template['id']})
    assert cartography.render_map(store,'svg',100).lstrip().startswith(b'<?xml')
