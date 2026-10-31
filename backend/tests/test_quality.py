import io
import json
import os
import threading
import numpy as np
import geopandas as gpd
import pytest
import rasterio
from shapely.geometry import Point,LineString,box
from PIL import Image
from geoagent.store import Store
from geoagent import algorithms,formats,cartography,durable
from geoagent.harness import Registry,execute_run
from geoagent.spatial_contracts import preflight,declare_semantics,semantic_metadata
from geoagent.spatial_validation import validate_spatial
from geoagent.map_quality import analyze,create_audit,image_message,record_visual


def vector(store,geometries,crs=32650,**columns):
    return formats.add_frame(store,'fixture',gpd.GeoDataFrame(columns,geometry=geometries,crs=crs),{})


def raster(store,tmp_path,name='raster',shift=0,data=None):
    path=tmp_path/(name+'.tif');data=np.array([[1,2],[-9999,4]],dtype='float32') if data is None else data
    with rasterio.open(path,'w',driver='GTiff',height=2,width=2,count=1,dtype='float32',crs='EPSG:32650',
                       transform=rasterio.transform.from_origin(500000+shift,4400000,100,100),nodata=-9999) as dst:dst.write(data,1)
    return store.add_raster(name,path)


def test_metric_crs_dates_fields_and_stale_declarations(tmp_path):
    store=Store(tmp_path/'workspace');a=vector(store,[Point(116,40)],4326,value=[1])
    r=preflight(store,'qgis:native:buffer',{'INPUT':a['id'],'DISTANCE':100},{'distance_unit':'m'})
    assert not r['passed'] and any(x['code']=='distance_crs' and x['status']=='error' for x in r['checks'])
    assert preflight(store,'qgis:native:buffer',{'INPUT':a['id'],'DISTANCE':.01},{'distance_unit':'layer_units'})['passed']
    declare_semantics(store,a['id'],{'source':'test metadata','evidence':'2020 survey','reference_date':'2020-01-01'})
    b=vector(store,[Point(116.1,40)],4326,value=[2])
    declare_semantics(store,b['id'],{'source':'test metadata','evidence':'2025 survey','reference_date':'2025-01-01'})
    r=preflight(store,'intersection',{'layer_id':a['id'],'other_id':b['id']},{'max_date_gap_days':365,'required_fields':{a['id']:['missing']}})
    assert not r['passed'] and len(r['errors'])==2
    path=store.root/'layers'/(a['id']+'.geojson');data=json.loads(path.read_text());data['features'][0]['properties']['value']=3;path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='失效'):semantic_metadata(store,a['id'])


def test_population_and_grid_semantics(tmp_path):
    store=Store(tmp_path/'workspace');a=raster(store,tmp_path);b=raster(store,tmp_path,'shifted',shift=50);areas=vector(store,[box(500000,4399800,500200,4400000)])
    args={'INPUT_A':a['id'],'INPUT_B':b['id'],'FORMULA':'A+B'}
    assert not preflight(store,'qgis:gdal:rastercalculator',args)['passed']
    args={'INPUT':areas['id'],'INPUT_RASTER':a['id'],'STATISTICS':[1]}
    r=preflight(store,'qgis:native:zonalstatisticsfb',args,{'quantity':'population'})
    assert not r['passed'] and r['needs_user_input']
    declare_semantics(store,a['id'],{'quantity':'density','unit':'people/km2','source':'source documentation','evidence':'density per square kilometre'})
    assert not preflight(store,'qgis:native:zonalstatisticsfb',args,{'quantity':'population'})['passed']
    declare_semantics(store,a['id'],{'quantity':'count_per_cell','unit':'people','source':'corrected source','evidence':'count per cell'})
    assert preflight(store,'qgis:native:zonalstatisticsfb',args,{'quantity':'population'})['passed']


def test_overlay_wrong_result_and_count_boundary_dedup(tmp_path):
    store=Store(tmp_path);a=vector(store,[box(500000,4400000,500100,4400100)]);b=vector(store,[box(500050,4400000,500150,4400100)])
    args={'layer_id':a['id'],'other_id':b['id']};before=preflight(store,'intersection',args)
    right=algorithms.run_algorithm(store,'intersection',args,'test')
    assert validate_spatial(store,'intersection',args,right,before)['passed']
    assert not validate_spatial(store,'intersection',args,{'layer_id':a['id']},before)['passed']
    points=vector(store,[Point(500050,4400050),Point(500000,4400050),Point(500200,4400050)])
    args={'layer_id':a['id'],'other_id':points['id']};before=preflight(store,'count_points',args)
    out=algorithms.run_algorithm(store,'count_points',args,'count')
    value=validate_spatial(store,'count_points',args,out,before)
    assert value['passed'] and value['metrics']['unique_points_in_union']==2
    assert not preflight(store,'count_points',args,{'overlap':'unique'})['passed']
    wrong=vector(store,[box(500000,4400000,500100,4400100)],poi_count=[1])
    assert not validate_spatial(store,'count_points',args,{'layer_id':wrong['id']},before)['passed']


def test_raster_nodata_leak_is_independently_rejected(tmp_path):
    store=Store(tmp_path/'workspace');a=raster(store,tmp_path);wrong=raster(store,tmp_path,'wrong',data=np.ones((2,2),dtype='float32'))
    args={'layer_id':a['id'],'expression':'b1 + 1'};before=preflight(store,'raster_calculator',args)
    good=algorithms.run_algorithm(store,'raster_calculator',args,'math')
    assert validate_spatial(store,'raster_calculator',args,good,before)['passed']
    result=validate_spatial(store,'raster_calculator',args,{'layer_id':wrong['id']},before)
    assert not result['passed'] and any(x['code']=='nodata_propagation' and x['status']=='error' for x in result['checks'])


def test_network_declared_walking_speed_direction_and_cost(tmp_path):
    store=Store(tmp_path);a=(500000,4400000);b=(500100,4400000);c=(500200,4400000)
    net=vector(store,[LineString([a,b]),LineString([b,c])],speed=[5,5],direction=['f','f'])
    args={'INPUT':net['id'],'START_POINT':'500000,4400000','END_POINT':'500200,4400000','STRATEGY':1,'DEFAULT_SPEED':50,'DIRECTION_FIELD':'direction','VALUE_FORWARD':'f'}
    context={'travel_mode':'walk','cost_unit':'h'}
    assert not preflight(store,'qgis:native:shortestpathpointtopoint',args,context)['passed']
    args['DEFAULT_SPEED']=5;before=preflight(store,'qgis:native:shortestpathpointtopoint',args,context);assert before['passed']
    good=vector(store,[LineString([a,b,c])],cost=[.04]);bad=vector(store,[LineString([c,b,a])],cost=[.04]);wrong=vector(store,[LineString([a,b,c])],cost=[15]);wrong_end=vector(store,[LineString([a,b])],cost=[.02])
    for output,expected in [(good,True),(bad,False),(wrong,False),(wrong_end,False)]:
        assert validate_spatial(store,'qgis:native:shortestpathpointtopoint',args,{'layer_id':output['id']},before)['passed']==expected


def test_strict_scope_and_user_requirements_cannot_be_downgraded(tmp_path):
    store=Store(tmp_path);a=vector(store,[box(500000,4400000,500100,4400100)])
    args={'layer_id':a['id']};before=preflight(store,'centroid',args,{'verification':'strict'})
    result=algorithms.run_algorithm(store,'centroid',args,'r')
    report=validate_spatial(store,'centroid',args,result,before)
    assert report['coverage']=='partial' and not report['passed']
    store.save_run({'id':'r','analysis_context':{'verification':'strict'}})
    registry=Registry(store);registry.execute('r','inspect_layer',args,threading.Event())
    result=registry.execute('r','run_algorithm',{'algorithm_id':'centroid','arguments':args,'context':{'verification':'standard'}},threading.Event())
    assert not result['success']
    assert result['data']['quality']['preflight']['context']['verification']=='strict'


def test_algorithm_defaults_are_used_by_validator(tmp_path):
    store=Store(tmp_path);p=vector(store,[Point(500000,4400000)])
    args={'layer_id':p['id']};before=preflight(store,'buffer',args)
    result=algorithms.run_algorithm(store,'buffer',args,'r')
    assert before['arguments']['distance_m']==800
    assert validate_spatial(store,'buffer',args,result,before)['passed']
    a=vector(store,[box(499000,4399000,501000,4401000)])
    value=preflight(store,'qgis:native:countpointsinpolygon',{'POLYGONS':a['id'],'POINTS':p['id']},{'boundary':'contains'})
    assert value['arguments']['FIELD']=='NUMPOINTS'


def test_strict_code_outputs_need_independent_verification(tmp_path):
    from geoagent.validation import validate_run
    store=Store(tmp_path);layer=vector(store,[Point(500000,4400000)])
    store.save_step('r','code',{'name':'execute_code','status':'completed','result':{'success':True,'data':{'layer_id':layer['id']}}})
    value=validate_run(store,{'id':'r','mode':'code','analysis_context':{'verification':'strict'}})
    assert not value['passed'] and any('自定义代码' in x for x in value['errors'])


def test_map_audit_overflow_collision_legend_and_visual_evidence(tmp_path):
    store=Store(tmp_path);image=store.root/'map.png';Image.new('RGB',(300,200),'blue').save(image)
    evidence={'width':297,'height':210,'labeling_available':True,'elements':[
        {'id':'map','uuid':'m','kind':'map','visible':True,'bounds':[15,40,215,185],'map_layers':['a','b']},
        {'id':'title','uuid':'t','kind':'label','visible':True,'bounds':[14,-10,280,20],'font_size':5,'text':'Map','size':[266,30],'required_size':[266,30]},
        {'id':'legend','uuid':'l','kind':'legend','visible':True,'bounds':[220,45,280,100],'linked_map':'m','legend_layers':['a']},
        {'id':'scale','uuid':'s','kind':'scale','visible':True,'bounds':[220,50,260,60],'linked_map':'m','units_per_segment':0,'segments':2,'unit_label':'km'}]}
    report=analyze(evidence,image);assert not report['passed']
    assert {'page_bounds','legend_coverage','layout_overlap','scale_value'}<=set(x['code'] for x in report['checks'] if x['status']!='pass')
    audit=create_audit(store,evidence,{},'r',preview=image)
    message=image_message(store,audit['id'],'responses');assert message['content'][1]['type']=='input_image'
    with pytest.raises(ValueError,match='尚未收到'):record_visual(store,'r',audit['id'],'pass',['looks good'])
    store.event('r','map_image_presented',{'review_id':audit['id']})
    assert record_visual(store,'r',audit['id'],'needs_revision',['标题超出纸张上沿'])['status']=='needs_revision'
    (store.root/audit['preview_path']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='变化'):image_message(store,audit['id'],'responses')


def test_automatic_repair_is_bounded_and_visual_input_is_real(tmp_path,monkeypatch):
    store=Store(tmp_path);image=store.root/'map.png';Image.new('RGB',(300,200),'blue').save(image)
    audit=create_audit(store,{}, {},'r',preview=image)
    import geoagent.map_quality as quality
    monkeypatch.setattr(quality,'inspect_map',lambda *a,**kw:{'review_id':audit['id'],'quality':{'cartography':audit['report']}})
    calls=[]
    def respond(client,config,payload):
        calls.append(payload)
        if len(calls)==1:
            return {'output':[{'type':'function_call','name':'inspect_map','arguments':'{}','call_id':'inspect'}]}
        if len(calls)==2:
            assert any(isinstance(m.get('content'),list) and any(x.get('type')=='input_image' for x in m['content']) for m in payload['input'])
            return {'output':[{'type':'function_call','name':'record_map_review','arguments':json.dumps({'review_id':audit['id'],'verdict':'uncertain','observations':['内容不足']}),'call_id':'review'}]}
        return {'output':[{'type':'message','content':[{'type':'output_text','text':'需要补充数据'}]}]}
    monkeypatch.setattr(durable,'request_responses',respond)
    config={'protocol':'responses','model':'test','base_url':'https://example.test','api_key':'SECRET'}
    run={'id':'r','mode':'model','session_id':'s','message_input':'review','acceptance':{'require_layer':True}}
    execute_run(store,Registry(store),run,config,threading.Event())
    assert store.run('r')['status']=='needs_attention'
    assert len([e for e in store.events('r') if e['type']=='quality_repair_requested'])==2
    assert store.object('map_reviews',audit['id'])['visual_review']['status']=='uncertain'


@pytest.mark.skipif(os.environ.get('GEOAGENT_NATIVE_TESTS')!='1',reason='Native QGIS integration is opt-in')
def test_native_route_independent_cost_validation(tmp_path,monkeypatch):
    monkeypatch.delenv('GEOAGENT_DISABLE_QGIS',raising=False)
    from geoagent.plugins import PluginManager
    store=Store(tmp_path);a=(500000,4400000);b=(500100,4400000);c=(500200,4400000)
    net=vector(store,[LineString([a,b]),LineString([b,c])])
    args={'INPUT':net['id'],'START_POINT':'500000,4400000 [EPSG:32650]','END_POINT':'500200,4400000 [EPSG:32650]',
          'STRATEGY':1,'DEFAULT_SPEED':5,'DEFAULT_DIRECTION':2,'TOLERANCE':0}
    before=preflight(store,'qgis:native:shortestpathpointtopoint',args,{'travel_mode':'walk','cost_unit':'h','verification':'strict'})
    assert before['passed']
    out=PluginManager(store).get('qgis').execute(store,'qgis:native:shortestpathpointtopoint',args,'route',threading.Event())
    result=validate_spatial(store,'qgis:native:shortestpathpointtopoint',args,out,before)
    assert result['passed'],result
    assert any(x['code']=='route_connectivity_cost' for x in result['checks'])


@pytest.mark.skipif(os.environ.get('GEOAGENT_NATIVE_TESTS')!='1',reason='Native QGIS integration is opt-in')
def test_native_map_audit_and_boundary_semantics(tmp_path,monkeypatch):
    monkeypatch.delenv('GEOAGENT_DISABLE_QGIS',raising=False)
    from geoagent.plugins import PluginManager
    store=Store(tmp_path);a=vector(store,[box(500000,4400000,500100,4400100)],name=['District'])
    points=vector(store,[Point(500050,4400050),Point(500000,4400050),Point(500200,4400050)],name=['Inside','Boundary','Outside'])
    args={'POLYGONS':a['id'],'POINTS':points['id'],'FIELD':'n'}
    plugin=PluginManager(store).get('qgis')
    result=plugin.execute(store,'qgis:native:countpointsinpolygon',args,'count',threading.Event())
    assert formats.frame(store,result['layer_id'])['n'].iloc[0]==1
    store.style_layer(a['id'],labels=True);store.style_layer(points['id'],labels=True)
    cartography.update_layout(store,{'plugin_id':'qgis','template':'standard','focus_layer_id':None,'legend_position':'outside-right','title':'Spatial quality test','items':{'title':{'y':-8}}})
    exported=cartography.export_map(store,'pdf',150,run_id='native')
    review=store.object('map_reviews',exported['map_review_id'])
    assert not review['report']['passed']
    assert any(c['code']=='page_bounds' and c['status']=='error' for c in review['report']['checks'])
    assert review['evidence']['labeling_available']
    assert sum(len(x['labels']) for x in review['evidence']['label_maps'])>0
    assert not any(c['code']=='legend_coverage' and c['status']!='pass' for c in review['report']['checks'])
    assert (store.root/review['preview_path']).is_file()
