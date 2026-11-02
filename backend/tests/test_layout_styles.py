import os
import threading
import pytest
from fastapi.testclient import TestClient
from geoagent import cartography
from geoagent.app import create_app
from geoagent.store import Store
from geoagent.harness import Registry,execute_run
from geoagent.layout_language import parse_style_commands
from geoagent.plugins.cartography_styles import catalog


@pytest.mark.parametrize('changes',[
    {'north_style':'invented'},{'terrain_palette':'unknown'}, {'scale_style':'fake'},
    {'scale_units':'degrees'},{'scale_segments':0},{'legend_precision':4},
    {'items':{'title':{'font_weight':42}}},{'items':{'legend':{'legend_columns':5}}},
    {'items':{'north_arrow':{'north_color':'red'}}}, {'items':{'title':{'font_family':'../font.ttf'}}},
    {'items':{'scale_bar':{'scale_segments':True}}},
])
def test_invalid_style_is_not_persisted(tmp_path,changes):
    s=Store(tmp_path);before=cartography.get_layout(s)
    with pytest.raises(ValueError):cartography.update_layout(s,changes)
    assert cartography.get_layout(s)==before


def test_element_patch_preserves_other_elements_and_rejects_missing_font(tmp_path,monkeypatch):
    s=Store(tmp_path)
    monkeypatch.setattr(cartography,'layout_styles',lambda s:{**catalog(),'fonts':[{'family':'Test Sans'}]})
    cartography.update_layout(s,{'items':{'title':{'x':18,'font_size':20},'legend':{'x':230,'y':48}}})
    result=cartography.update_layout_element(s,'title',{'font_family':'Test Sans','font_weight':600})
    assert result['items']['title']=={'x':18,'font_size':20,'font_family':'Test Sans','font_weight':600}
    assert result['items']['legend']=={'x':230,'y':48}
    with pytest.raises(ValueError,match='字体未安装'):cartography.update_layout_element(s,'title',{'font_family':'Missing'})
    assert cartography.get_layout(s)==result


def test_offline_styles_share_layout_and_keep_manual_geometry(tmp_path,monkeypatch):
    s=Store(tmp_path)
    monkeypatch.setattr(cartography,'layout_styles',lambda s:{**catalog(),'fonts':[{'family':'PingFang SC'}]})
    cartography.update_layout(s,{'items':{'title':{'x':18,'width':210},'legend':{'x':230,'y':48},'north_arrow':{'x':88,'y':99}}})
    run={'id':'style','mode':'offline','message_input':'指北针改成罗盘玫瑰，放到右上角，比例尺用双线框，单位米，分4段，高程改成蓝绿色带，标题用苹方，字号24，加粗'}
    execute_run(s,Registry(s),run,None,threading.Event())
    assert s.run('style')['status']=='completed',s.run('style')['message']
    value=cartography.get_layout(s)
    assert value['items']['north_arrow']['north_style']=='rose'
    assert value['north_position']=='top-right'
    assert 'x' not in value['items']['north_arrow']
    assert value['items']['scale_bar']=={'scale_style':'Double Box','scale_units':'m','scale_segments':4}
    assert value['terrain_palette']=='bluegreen'
    assert value['items']['title']=={'x':18,'width':210,'font_family':'PingFang SC','font_size':24,'font_weight':700}
    assert value['items']['legend']=={'x':230,'y':48}
    run={'id':'unknown','mode':'offline','message_input':'指北针改成龙形'}
    execute_run(s,Registry(s),run,None,threading.Event())
    assert '尚未识别' in s.run('unknown')['message']
    assert cartography.get_layout(s)==value


def test_style_api_and_model_tool_use_same_validated_merge(tmp_path,monkeypatch):
    monkeypatch.setenv('GEOAGENT_DISABLE_QGIS','1')
    monkeypatch.setattr(cartography,'layout_styles',lambda s:{**catalog(),'fonts':[{'family':'Test Sans'}]})
    app=create_app(tmp_path)
    with TestClient(app) as client:
        assert client.get('/api/layout/styles').json()['north_styles'][0]['svg'].startswith('<svg')
        font=client.get('/api/layout/fonts/noto-regular');assert font.status_code==200 and font.content[:4]==b'OTTO'
        assert client.get('/api/layout/fonts/missing').status_code==404
        response=client.patch('/api/layout/items/title',json={'font_family':'Test Sans','font_weight':600})
        assert response.status_code==200
        assert client.patch('/api/layout/items/title',json={'font_family':'Missing'}).status_code==400
    registry=Registry(Store(tmp_path))
    result=registry.execute('style-test','update_layout_element',{'element_id':'title','changes':{'font_size':22}},threading.Event())
    assert result['success'],result
    assert result['data']['items']['title']['font_family']=='Test Sans'


def test_offline_font_alias_requires_real_installed_font():
    with pytest.raises(ValueError,match='未安装'):parse_style_commands('标题用苹方',[])
    changes,items=parse_style_commands('地图字体用宋体，比例尺使用下方刻度，单位千米，关闭等高线', [{'family':'SimSun'}])
    assert changes=={'font_family':'SimSun','terrain_contours':False}
    assert items['scale_bar']=={'scale_style':'Line Ticks Down','scale_units':'km'}


@pytest.mark.skipif(os.environ.get('GEOAGENT_NATIVE_TESTS')!='1',reason='Native QGIS integration is opt-in')
def test_native_styles_and_unit_conversion_survive_project_roundtrip(tmp_path,monkeypatch):
    import geopandas as gpd
    from shapely.geometry import Point
    from geoagent import formats
    from geoagent.plugins import PluginManager
    monkeypatch.delenv('GEOAGENT_DISABLE_QGIS',raising=False)
    s=Store(tmp_path);layer=formats.add_frame(s,'points',gpd.GeoDataFrame({'name':['A','B']},geometry=[Point(550000,5180000),Point(552000,5181000)],crs=32610),{})
    qgis=PluginManager(s).get('qgis');options=cartography.layout_styles(s)
    assert options['default_cjk']
    assert any(f.get('bundled') and f['family']=='Noto Sans CJK SC' for f in options['fonts'])
    family='Noto Sans CJK SC';assert family in {f['family'] for f in options['fonts']}
    cartography.update_layout(s,{'plugin_id':'qgis','focus_layer_id':layer['id'],'map_crs':'EPSG:32610','font_family':family})
    def scene():return {e['id']:e for e in qgis.scene(s,cartography.get_layout(s),s.layers())['elements']}
    baseline=scene();meters=baseline['scale_bar']['scale_ground_segment_m']
    cartography.update_layout_element(s,'title',{'font_family':family,'font_size':24,'font_weight':700,'color':'#254c60'})
    cartography.update_layout_element(s,'north_arrow',{'north_style':'rose','north_color':'#235a63'})
    cartography.update_layout_element(s,'scale_bar',{'scale_style':'Double Box','scale_units':'m','scale_segments':4,'font_family':family,'color':'#254c60'})
    result=scene()
    assert result['scale_bar']['scale_units']=='m'
    assert result['scale_bar']['scale_style']=='Double Box'
    assert result['scale_bar']['scale_segments']==4
    assert result['scale_bar']['scale_ground_segment_m']==pytest.approx(meters)
    assert result['title']['font_family']==family and result['title']['font_weight']==700
    assert result['title']['font_size']==24 and result['title']['color']=='#254c60'
    assert result['north_arrow']['north_style']=='rose'
    assert cartography.render_map(s,'pdf',100).startswith(b'%PDF-')
    project=qgis.save_project(s,'Style roundtrip')
    qgis.open_project(s,project['id'])
    restored=scene()
    assert restored['scale_bar']['scale_style']=='Double Box'
    assert restored['title']['font_family']==family
    assert restored['north_arrow']['north_color']=='#235a63'


@pytest.mark.skipif(os.environ.get('GEOAGENT_NATIVE_TESTS')!='1',reason='Native QGIS integration is opt-in')
def test_every_advertised_scale_style_renders_without_silent_fallback(tmp_path,monkeypatch):
    from geoagent.plugins import PluginManager
    monkeypatch.delenv('GEOAGENT_DISABLE_QGIS',raising=False)
    s=Store(tmp_path);plugin=PluginManager(s).get('qgis')
    advertised=[x['id'] for x in cartography.layout_styles(s)['scale_styles']]
    code="""from qgis.core import *
project=QgsProject.instance();layout=QgsPrintLayout(project);layout.initializeDefaults()
main=QgsLayoutItemMap(layout);layout.addLayoutItem(main);main.setCrs(QgsCoordinateReferenceSystem('EPSG:32610'));main.attemptResize(QgsLayoutSize(180,120));main.zoomToExtent(QgsRectangle(550000,5180000,555000,5184000))
styles=STYLES
for index,name in enumerate(styles):
 scale=QgsLayoutItemScaleBar(layout);layout.addLayoutItem(scale);scale.setLinkedMap(main);scale.applyDefaultSize();scale.setStyle(name);scale.attemptMove(QgsLayoutPoint(15,15+index*20));assert scale.style()==name,(name,scale.style())
path=output_dir/'scale-styles.png';settings=QgsLayoutExporter.ImageExportSettings();settings.dpi=100
assert QgsLayoutExporter(layout).exportToImage(str(path),settings)==QgsLayoutExporter.Success
outputs={'scale_styles':str(path)};metrics['styles']=styles
""".replace('STYLES',repr(advertised))
    result=plugin.execute_code(s,code,{},None,threading.Event())
    assert result['scalars']['styles']==advertised
    assert 'stepped' in advertised and 'hollow' in advertised
