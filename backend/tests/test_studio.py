import io
import json
import threading
import zipfile
from pathlib import Path
import geopandas as gpd
import numpy as np
import pytest
import rasterio
from PIL import Image
from shapely.geometry import Point,box
from fastapi.testclient import TestClient
from geoagent.store import Store
from geoagent import formats,algorithms,cartography
from geoagent.app import create_app
from geoagent.harness import Registry,execute_run

@pytest.fixture
def store(tmp_path):return Store(tmp_path/'project')

def points(store):
    g=gpd.GeoDataFrame({'name':['A','B','C'],'value':[10.,20.,30.]},geometry=[Point(116.39,39.91),Point(116.392,39.912),Point(116.42,39.93)],crs=4326)
    return formats.add_frame(store,'stations',g,{},source='upload')

def polygon(store):
    g=gpd.GeoDataFrame({'name':['area']},geometry=[box(116.38,39.90,116.40,39.92)],crs=4326)
    return formats.add_frame(store,'area',g,{},source='upload')

def raster(store,tmp_path):
    path=tmp_path/'dem.tif';profile={'driver':'GTiff','height':20,'width':20,'count':2,'dtype':'float32','crs':'EPSG:3857','transform':rasterio.transform.from_origin(12956000,4853000,100,100),'nodata':-9999}
    with rasterio.open(path,'w',**profile) as dst:
        arr=np.arange(400,dtype='float32').reshape(20,20);arr[0,0]=-9999;dst.write(arr,1);dst.write(arr*2,2)
    asset=formats.stage_files(store,[('dem.tif',path.read_bytes())]);return formats.import_asset(store,asset['id'])

@pytest.mark.parametrize('fmt',['gpkg','shp','fgb','parquet'])
def test_vector_export_and_reimport(store,tmp_path,fmt):
    src=points(store);path=formats.export_vector(store,src['id'],fmt)
    asset=formats.stage_files(store,[(path.name,path.read_bytes())]);imported=formats.import_asset(store,asset['id'])
    assert imported['count']==3 and 'value' in imported['fields']
    assert imported['sha256']


def test_shapefile_parts_and_zip_traversal(store,tmp_path):
    g=gpd.GeoDataFrame({'name':['one']},geometry=[Point(116,40)],crs=4326);g.to_file(tmp_path/'p.shp',engine='pyogrio')
    files=[(p.name,p.read_bytes()) for p in tmp_path.glob('p.*')]
    asset=formats.stage_files(store,files);out=formats.import_asset(store,asset['id']);assert out['count']==1
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:z.writestr('../escape.geojson','{}')
    with pytest.raises(ValueError,match='不安全'):formats.stage_files(store,[('attack.zip',buf.getvalue())])


def test_raster_import_preview_calculation_and_nodata(store,tmp_path):
    src=raster(store,tmp_path)
    assert src['kind']=='raster' and src['bands']==2 and src['crs']=='EPSG:3857'
    image=Image.open(io.BytesIO(formats.raster_preview(store,src['id'])));assert image.mode=='RGBA'
    result=algorithms.run_algorithm(store,'raster_calculator',{'layer_id':src['id'],'expression':'b1 + 3'},'r')
    with rasterio.open(formats.raster_path(store,result['layer_id'])) as dst:
        arr=dst.read(1,masked=True);assert arr.mask[0,0];assert arr[2,3]==46
    ndvi=algorithms.run_algorithm(store,'ndvi',{'layer_id':src['id'],'red_band':1,'nir_band':2},'r')
    with rasterio.open(formats.raster_path(store,ndvi['layer_id'])) as dst:assert dst.read(1)[2,3]==pytest.approx(1/3)


@pytest.mark.parametrize('algorithm',['centroid','convex_hull','envelope','explode','measure','repair','point_on_surface','boundary','dissolve'])
def test_geometry_algorithms_publish_new_immutable_layer(store,algorithm):
    src=polygon(store);original=store.data(src['id']);out=algorithms.run_algorithm(store,algorithm,{'layer_id':src['id']},'r')
    assert out['layer_id']!=src['id'];assert store.data(src['id'])==original
    assert store.get_layer(out['layer_id'])['provenance']['input_sha256']==[src['sha256']]


def test_overlay_count_filter_and_field_expression(store):
    a=polygon(store);p=points(store)
    out=algorithms.run_algorithm(store,'count_points',{'layer_id':a['id'],'other_id':p['id']},'r')
    assert store.data(out['layer_id'])['features'][0]['properties']['poi_count']==2
    filtered=algorithms.run_algorithm(store,'filter',{'layer_id':p['id'],'field':'value','operator':'gt','value':'15'},'r');assert filtered['count']==2
    calc=algorithms.run_algorithm(store,'calculate_field',{'layer_id':p['id'],'field':'value','expression':'value * 2','output_field':'double'},'r')
    assert store.data(calc['layer_id'])['features'][0]['properties']['double']==20
    with pytest.raises(ValueError):algorithms.evaluate('__import__("os").system("pwd")',{'value':1})
    clip=algorithms.run_algorithm(store,'clip',{'layer_id':p['id'],'other_id':a['id']},'r');assert clip['count']==2


def test_cluster_and_interpolation(store):
    src=points(store)
    result=algorithms.run_algorithm(store,'dbscan',{'layer_id':src['id'],'distance_m':500,'min_points':2},'r')
    labels=[f['properties']['cluster'] for f in store.data(result['layer_id'])['features']];assert labels==[0,0,-1]
    out=algorithms.run_algorithm(store,'idw',{'layer_id':src['id'],'field':'value','cell_size_m':500},'r')
    assert store.get_layer(out['layer_id'])['kind']=='raster'


@pytest.mark.parametrize('fmt',['png','jpeg','tiff','svg','pdf'])
def test_real_map_exports(store,fmt):
    points(store);cartography.update_layout(store,{'title':'地图测试','north_position':'top-left'})
    item=cartography.export_map(store,fmt,100);content=(store.root/item['path']).read_bytes()
    if fmt in ('png','jpeg','tiff'):
        image=Image.open(io.BytesIO(content));assert image.width>800 and image.height>600
    elif fmt=='pdf':assert content.startswith(b'%PDF-')
    else:assert b'<svg' in content
    assert item['layout']['north_position']=='top-left'


def test_natural_language_import_and_layout(store):
    from geoagent.demo import seed
    seed(store)
    asset=formats.stage_files(store,[('my-points.csv',b'name,lon,lat\na,116,40')])
    run={'id':'import','mode':'offline','message_input':'导入 my-points.csv'}
    execute_run(store,Registry(store),run,None,threading.Event());assert store.run('import')['status']=='completed'
    assert store.object('assets',asset['id'])['status']=='imported'
    run={'id':'map','mode':'offline','message_input':'把指北针放到左上角，导出 SVG 地图'}
    execute_run(store,Registry(store),run,None,threading.Event());assert store.run('map')['status']=='completed'
    assert cartography.get_layout(store)['north_position']=='top-left';assert store.objects('exports')


def test_empty_selection_is_a_valid_new_layer(store):
    p=points(store);r=algorithms.run_algorithm(store,'filter',{'layer_id':p['id'],'field':'value','operator':'gt','value':'999'},'r')
    assert r['count']==0 and store.data(r['layer_id'])['features']==[]


@pytest.mark.parametrize('op',['intersection','union','difference','symmetric_difference'])
def test_overlay_area_contract(store,op):
    left=formats.add_frame(store,'left',gpd.GeoDataFrame(geometry=[box(0,0,2,2)],crs=4326),{})
    right=formats.add_frame(store,'right',gpd.GeoDataFrame(geometry=[box(1,0,3,2)],crs=4326),{})
    out=algorithms.run_algorithm(store,op,{'layer_id':left['id'],'other_id':right['id']},'r')
    areas={'intersection':2,'union':6,'difference':2,'symmetric_difference':4}
    assert formats.frame(store,out['layer_id']).geometry.map(lambda x:x.area).sum()==pytest.approx(areas[op])


@pytest.mark.parametrize('op',['slope','aspect','hillshade','polygonize','raster_reproject'])
def test_raster_algorithms(store,tmp_path,op):
    src=raster(store,tmp_path)
    args={'layer_id':src['id']}
    if op=='raster_reproject':args['target_crs']='EPSG:4326'
    out=algorithms.run_algorithm(store,op,args,'r')
    assert out['layer_id']!=src['id']
    assert store.get_layer(out['layer_id'])['count']>0


@pytest.mark.parametrize('op',['nearest','spatial_join','grid','simplify','reproject','heatmap'])
def test_remaining_vector_algorithms(store,op):
    p=points(store);a=polygon(store);args={'layer_id':p['id'] if op in ('nearest','spatial_join','heatmap') else a['id']}
    if op in ('nearest','spatial_join'):args['other_id']=a['id']
    if op=='reproject':args['target_crs']='EPSG:3857'
    out=algorithms.run_algorithm(store,op,args,'r');assert store.get_layer(out['layer_id'])['count']>0


def test_raster_clip_and_zonal_statistics(store,tmp_path):
    src=raster(store,tmp_path);bbox=store.get_layer(src['id'])['bounds']
    mask=formats.add_frame(store,'mask',gpd.GeoDataFrame(geometry=[box(*bbox)],crs=4326),{})
    clipped=algorithms.run_algorithm(store,'raster_clip',{'layer_id':src['id'],'other_id':mask['id']},'r')
    assert store.get_layer(clipped['layer_id'])['kind']=='raster'
    stats=algorithms.run_algorithm(store,'zonal_statistics',{'layer_id':mask['id'],'other_id':src['id']},'r')
    assert store.data(stats['layer_id'])['features'][0]['properties']['pixel_count']==399


def test_workflow_dag_replay_hashes_and_cycle_guard(store):
    from geoagent import workflows
    p=points(store);a=polygon(store)
    flow=workflows.save(store,'buffer and count',[{'id':'count','algorithm_id':'count_points','arguments':{'layer_id':'$buffer.layer_id','other_id':p['id']}},{'id':'buffer','algorithm_id':'buffer','arguments':{'layer_id':p['id'],'distance_m':500}}])
    hashes=[]
    for rid in ('flow1','flow2'):
        r={'id':rid,'mode':'workflow','message_input':'运行流程','workflow_id':flow['id']}
        execute_run(store,Registry(store),r,None,threading.Event())
        assert store.run(rid)['status']=='completed'
        out=store.run(rid)['output_layers'][-1];hashes.append(store.get_layer(out)['sha256'])
        assert len([e for e in store.events(rid) if e['type']=='workflow_node_completed'])==2
    assert hashes[0]==hashes[1]
    with pytest.raises(ValueError,match='循环'):
        workflows.save(store,'cycle',[{'id':'a','algorithm_id':'buffer','arguments':{'layer_id':'$b.layer_id'}},{'id':'b','algorithm_id':'buffer','arguments':{'layer_id':'$a.layer_id'}}])


def test_manual_raster_run_archives_published_result(store,tmp_path):
    src=raster(store,tmp_path)
    run={'id':'manual-raster','mode':'algorithm','message_input':'栅格计算','algorithm_id':'raster_calculator','arguments':{'layer_id':src['id'],'expression':'b1 + 1'}}
    execute_run(store,Registry(store),run,None,threading.Event())
    result=store.run(run['id'])
    assert result['status']=='completed' and len(result['output_layers'])==1
    output=store.get_layer(result['output_layers'][0])
    assert output['kind']=='raster' and output['count']==400
    assert output['provenance']['input_sha256']==[src['sha256']]


def test_projected_native_snapshot_and_crs_conflict(store,tmp_path):
    original=gpd.GeoDataFrame({'name':['projected']},geometry=[Point(12956586.752,4851421.175)],crs=3857)
    original.to_file(tmp_path/'projected.gpkg',driver='GPKG',engine='pyogrio')
    asset=formats.stage_files(store,[('projected.gpkg',(tmp_path/'projected.gpkg').read_bytes())])
    with pytest.raises(ValueError,match='不一致'):
        formats.import_asset(store,asset['id'],source_crs='EPSG:4326')
    imported=formats.import_asset(store,asset['id'])
    exported=gpd.read_file(formats.export_vector(store,imported['id'],'gpkg'))
    assert exported.crs.to_epsg()==3857
    assert exported.geometry.iloc[0].x==pytest.approx(original.geometry.iloc[0].x,abs=1e-8)
    with pytest.raises(ValueError,match='范围'):
        formats.add_frame(store,'bad',gpd.GeoDataFrame(geometry=[Point(116,100)],crs=4326),{},source='upload')


def test_true_color_preview_preserves_uint8_channels(store,tmp_path):
    path=tmp_path/'rgb.tif'
    with rasterio.open(path,'w',driver='GTiff',width=10,height=10,count=3,dtype='uint8',crs=3857,transform=rasterio.transform.from_origin(12956000,4853000,100,100)) as dst:
        dst.write(np.stack([np.full((10,10),v,dtype='uint8') for v in (200,100,50)]))
        dst.colorinterp=(rasterio.enums.ColorInterp.red,rasterio.enums.ColorInterp.green,rasterio.enums.ColorInterp.blue)
    layer=store.add_raster('rgb',path)
    preview=np.asarray(Image.open(io.BytesIO(formats.raster_preview(store,layer['id']))))
    assert preview[5,5].tolist()==[200,100,50,255]


def test_offline_named_poi_survives_unrelated_import(store):
    from geoagent.demo import seed
    seed(store)
    formats.add_frame(store,'unrelated points',gpd.GeoDataFrame(geometry=[Point(116.39,39.91)],crs=4326),{},source='upload')
    run={'id':'named-poi','mode':'offline','message_input':'统计地铁站 800 米直线范围内的公园数量'}
    execute_run(store,Registry(store),run,None,threading.Event())
    assert store.run(run['id'])['status']=='completed'
    assert len(store.run(run['id'])['output_layers'])==2
