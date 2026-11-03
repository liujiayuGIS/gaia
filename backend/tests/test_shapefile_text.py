"""Real DBF bytes, Chinese paths and values; no mocked GIS reader."""
import io
import zipfile
import geopandas as gpd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import Point
from geoagent.app import create_app
from geoagent.formats import stage_files, import_asset
from geoagent.harness import Registry,execute_run
from geoagent.shapefile_text import inspect_shapefile
from geoagent.store import Store
from geoagent.validation import check_layer
import threading


def dataset(tmp_path, encoding='UTF-8', truncated=False):
    folder=tmp_path/'source';folder.mkdir()
    path=folder/'西安市_地铁站点.shp'
    gpd.GeoDataFrame({'name':['钟楼站','行政中心'], 'field_1':[11,22]},
                    geometry=[Point(108.94,34.26),Point(108.95,34.27)],crs=4326).to_file(
                        path,engine='pyogrio',encoding=encoding)
    if truncated:
        dbf=path.with_suffix('.dbf');raw=bytearray(dbf.read_bytes())
        raw[32:43]='地铁站人口'.encode()[:10]+b'\0'
        dbf.write_bytes(raw)
    return path


def files(path):
    return [(p.name,p.read_bytes()) for p in path.parent.iterdir() if p.is_file()]


@pytest.mark.parametrize('encoding',['UTF-8','GBK','GB18030'])
def test_declared_encodings_preserve_chinese_names_and_values(tmp_path,encoding):
    path=dataset(tmp_path,encoding)
    store=Store(tmp_path/'workspace');asset=stage_files(store,files(path))
    layer=import_asset(store,asset['id'])
    rows=store.data(layer['id'])['features']
    assert [x['properties']['name'] for x in rows]==['钟楼站','行政中心']
    assert [x['properties']['field_1'] for x in rows]==[11,22]
    assert layer['count']==2 and not layer.get('import_warnings')


def test_truncated_name_uses_unique_alias_without_modifying_original_or_values(tmp_path):
    path=dataset(tmp_path,truncated=True)
    store=Store(tmp_path/'workspace');asset=stage_files(store,files(path))
    source=store.root/'inbox'/asset['id']/path.with_suffix('.dbf').name
    original=source.read_bytes()
    issue=asset['resources'][0]['shapefile_text']['field_name_issues'][0]
    assert issue['truncated'] and issue['valid_prefix']=='地铁站'
    layer=import_asset(store,asset['id'])
    repair=layer['provenance']['field_name_repairs'][0]
    assert repair['alias']=='f1_1' and repair['raw_hex']=='地铁站人口'.encode()[:10].hex()
    assert source.read_bytes()==original
    rows=store.data(layer['id'])['features']
    assert [x['properties']['f1_1'] for x in rows]==['钟楼站','行政中心']
    assert [x['properties']['field_1'] for x in rows]==[11,22]
    assert rows[0]['geometry']['coordinates']==[108.94,34.26]
    assert check_layer(store,layer['id'])['warnings']==layer['import_warnings']


def test_wrong_cpg_is_not_lossily_decoded_and_explicit_override_works(tmp_path):
    path=dataset(tmp_path,'GBK');path.with_suffix('.cpg').write_text('UTF-8')
    store=Store(tmp_path/'workspace');asset=stage_files(store,files(path))
    with pytest.raises(ValueError,match='实际文字编码'):
        import_asset(store,asset['id'])
    assert store.layers()==[]
    layer=import_asset(store,asset['id'],encoding='GB18030')
    assert store.data(layer['id'])['features'][0]['properties']['name']=='钟楼站'
    assert layer['provenance']['text_encoding']['encoding_source']=='user'


def test_no_cpg_or_codepage_requires_encoding_for_non_ascii_values(tmp_path):
    path=dataset(tmp_path,'GBK');path.with_suffix('.cpg').unlink()
    dbf=path.with_suffix('.dbf');data=bytearray(dbf.read_bytes());data[29]=0;dbf.write_bytes(data)
    assert inspect_shapefile(path)['needs_encoding']
    store=Store(tmp_path/'workspace');asset=stage_files(store,files(path))
    with pytest.raises(ValueError,match='缺少可识别的编码声明'):
        import_asset(store,asset['id'])
    layer=import_asset(store,asset['id'],encoding='936')
    assert store.data(layer['id'])['features'][1]['properties']['name']=='行政中心'


def test_truncated_field_repair_can_be_disabled(tmp_path):
    path=dataset(tmp_path,truncated=True)
    store=Store(tmp_path/'workspace');asset=stage_files(store,files(path))
    with pytest.raises(ValueError,match='字段名.*截断'):
        import_asset(store,asset['id'],repair_truncated_fields=False)
    assert not store.layers()


def test_unicode_zip_import_through_agent_tool_and_api(tmp_path):
    path=dataset(tmp_path,truncated=True)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        for name,content in files(path):archive.writestr('数据/'+name,content)
    store=Store(tmp_path/'workspace');asset=stage_files(store,[('地铁.zip',stream.getvalue())])
    result=Registry(store).execute('import-check','import_data',{'asset_id':asset['id']},threading.Event())
    assert result['success'] and result['validation']['warnings']
    assert result['data']['provenance']['field_name_repairs']
    client=TestClient(create_app(tmp_path/'api'))
    response=client.post('/api/imports',files=[('files',('地铁.zip',stream.getvalue(),'application/zip'))])
    assert response.status_code==200
    loaded=client.post('/api/imports/'+response.json()['id']+'/load',json={'encoding':'UTF-8'})
    assert loaded.status_code==200 and loaded.json()['import_warnings']


def test_cpg_bom_numeric_alias_and_uppercase_sidecar(tmp_path):
    path=dataset(tmp_path,'GBK')
    cpg=path.with_suffix('.cpg');cpg.unlink();path.with_suffix('.CPG').write_bytes(b'\xef\xbb\xbf936')
    store=Store(tmp_path/'workspace');asset=stage_files(store,files(path));layer=import_asset(store,asset['id'])
    assert store.data(layer['id'])['features'][0]['properties']['name']=='钟楼站'


def test_field_name_encoding_mismatch_does_not_trigger_alias_repair(tmp_path):
    path=dataset(tmp_path,'GBK')
    dbf=path.with_suffix('.dbf');raw=bytearray(dbf.read_bytes())
    raw[32:43]='站名'.encode('gbk').ljust(11,b'\0');dbf.write_bytes(raw)
    path.with_suffix('.cpg').write_text('UTF-8')
    store=Store(tmp_path/'workspace');asset=stage_files(store,files(path))
    with pytest.raises(ValueError,match='字段名与文字编码声明不一致'):
        import_asset(store,asset['id'])
    assert not store.layers()


def test_offline_natural_language_preserves_selected_encoding(tmp_path):
    path=dataset(tmp_path,'GBK');path.with_suffix('.cpg').write_text('UTF-8')
    store=Store(tmp_path/'workspace');stage_files(store,files(path))
    run={'id':'natural-import','mode':'offline','session_id':'s','message_input':f'请导入 {path.name}，文字编码为 GBK'}
    execute_run(store,Registry(store),run,None,threading.Event())
    assert store.run(run['id'])['status']=='completed'
    layer=store.layers()[0]
    assert store.data(layer['id'])['features'][0]['properties']['name']=='钟楼站'
