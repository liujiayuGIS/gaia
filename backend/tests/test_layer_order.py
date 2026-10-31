import io
import os
import threading
import numpy as np
import pytest
import rasterio
from PIL import Image
from shapely.geometry import box, mapping
from fastapi.testclient import TestClient
from geoagent.store import Store
from geoagent.app import create_app
from geoagent import cartography
from geoagent.harness import Registry


def polygon(store, name, color):
    return store.add_layer(name, {'type':'FeatureCollection','features':[
        {'type':'Feature','geometry':mapping(box(116,39,117,40)),'properties':{'name':name}}]},
        style={'color':color,'opacity':1,'visible':True,'labels':False})


def raster(store, tmp_path):
    path=tmp_path/'input.tif'
    with rasterio.open(path,'w',driver='GTiff',height=10,width=10,count=1,dtype='float32',
                       crs='EPSG:4326',transform=rasterio.transform.from_bounds(116,39,117,40,10,10)) as dst:
        dst.write(np.arange(100,dtype='float32').reshape(10,10),1)
    return store.add_raster('DEM',path)


def test_order_api_persistence_invalid_requests_and_new_layers(tmp_path):
    app=create_app(tmp_path/'workspace');store=app.state.store
    a=polygon(store,'red','#e63636');b=polygon(store,'blue','#2463db');c=raster(store,tmp_path)
    store.style_layer(b['id'],visible=False)
    snapshot=store.layers();ids=[c['id'],a['id'],b['id']]
    with TestClient(app) as client:
        result=client.patch('/api/layers/order',json={'layer_ids':ids})
        assert result.status_code==200
        assert [x['id'] for x in result.json()]==ids
        assert [x['id'] for x in client.get('/api/layers').json()]==ids
        for invalid in ([a['id']]*3,ids[:-1],ids+['unknown'],['unknown',*ids[1:]]):
            assert client.patch('/api/layers/order',json={'layer_ids':invalid}).status_code==400
            assert [x['id'] for x in client.get('/api/layers').json()]==ids
    assert store.layers()==snapshot  # chronology, data, visibility and provenance untouched
    reopened=Store(store.root)
    assert [x['id'] for x in reopened.ordered_layers()]==ids
    new=polygon(reopened,'new result','#37a460')
    assert [x['id'] for x in reopened.ordered_layers()]==[new['id'],*ids]
    registry=Registry(reopened)
    changed=[*ids,new['id']]
    assert registry.execute('order-test','reorder_layers',{'layer_ids':changed},threading.Event())['success']
    assert [x['id'] for x in reopened.ordered_layers()]==changed


def test_python_export_uses_stack_for_vectors_and_rasters(tmp_path):
    store=Store(tmp_path/'workspace');a=polygon(store,'red','#e63636');b=polygon(store,'blue','#2463db');c=raster(store,tmp_path)
    cartography.update_layout(store,{'plugin_id':'python','template':'standard','legend':False,'north_arrow':False,'scale_bar':False,'grid':False})
    def center():
        image=Image.open(io.BytesIO(cartography.render_map(store,'png',100))).convert('RGB')
        return image.getpixel((image.width//2,image.height//2))
    store.reorder_layers([a['id'],c['id'],b['id']]);assert center()==(230,54,54)
    store.reorder_layers([b['id'],a['id'],c['id']]);assert center()==(36,99,219)
    store.reorder_layers([c['id'],a['id'],b['id']]);assert center() not in [(230,54,54),(36,99,219)]


@pytest.mark.skipif(os.environ.get('GEOAGENT_NATIVE_TESTS')!='1',reason='Native QGIS integration is opt-in')
def test_native_render_scene_cache_and_project_preserve_order(tmp_path,monkeypatch):
    monkeypatch.delenv('GEOAGENT_DISABLE_QGIS',raising=False)
    from geoagent.plugins import PluginManager
    store=Store(tmp_path/'workspace');a=polygon(store,'red','#e63636');b=polygon(store,'blue','#2463db');c=raster(store,tmp_path)
    store.style_layer(c['id'],visible=False)
    config=cartography.update_layout(store,{'plugin_id':'qgis','template':'standard','focus_layer_id':None,'legend':False,'north_arrow':False,'scale_bar':False,'grid':False})
    qgis=PluginManager(store).get('qgis')
    def visible():return [x for x in store.ordered_layers() if x['style'].get('visible',True)]
    def center():
        image=Image.open(io.BytesIO(cartography.render_map(store,'png',100,preview=True))).convert('RGB')
        return image.getpixel((image.width//2,image.height//2))
    store.reorder_layers([a['id'],c['id'],b['id']]);assert center()==(230,54,54)
    first=qgis.scene(store,config,visible())
    store.reorder_layers([b['id'],c['id'],a['id']]);assert center()==(36,99,219)
    assert qgis.scene(store,config,visible())['id']!=first['id']
    saved=qgis.save_project(store,'order test')
    reopened=qgis.open_project(store,saved['id'],'restore-test')
    restored=store.ordered_layers()[:3]
    assert [x['name'] for x in restored]==['blue','DEM','red']
    assert [x['style']['visible'] for x in restored]==[True,False,True]
    assert len(reopened['layers'])==3
