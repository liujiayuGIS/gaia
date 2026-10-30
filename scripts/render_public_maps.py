"""Reproduce two real-data print maps through the application's registered tools."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from geoagent.store import Store
from geoagent.harness import Registry
from geoagent import formats

OUT = ROOT / 'outputs' / 'public-cartography'


def main():
    sources = json.loads((OUT / 'sources.json').read_text())
    store = Store(OUT / 'workspace')
    registry = Registry(store)
    existing_ids = {x['id'] for x in store.layers()}
    cancel = threading.Event()
    run = {'id': uuid.uuid4().hex, 'mode': 'offline', 'session_id': 'real-public-maps',
           'status': 'running', 'message_input': '真实公开 SHP / GeoTIFF 专业出图验收',
           'created_at': datetime.now(timezone.utc).isoformat(), 'output_layers': []}
    store.save_run(run)
    store.event(run['id'], 'run_started', {'objective': run['message_input']})
    def call(name, args):
        result = registry.execute(run['id'], name, args, cancel)
        if not result['success']:
            raise ValueError(result['error'])
        return result['data']
    imported = []
    for name in ('washington-counties-shp.zip', 'rainier-usgs-3dep.tif'):
        path = OUT / 'raw' / name
        asset = formats.stage_files(store, [(path.name, path.read_bytes())])
        layer = call('import_data', {'asset_id': asset['id']})
        imported.append(layer)
    counties, dem = imported
    store.patch_layer(counties['id'], {'name': '公开数据 · 华盛顿州县界（Census 2024）',
          'provenance': {**counties['provenance'], 'source_url': sources['vector']['url'], 'vintage': 2024}})
    store.patch_layer(dem['id'], {'name': '公开数据 · 雷尼尔山 DEM（USGS 3DEP）',
          'provenance': {**dem['provenance'], 'source_url': sources['raster']['service'],
                         'request': sources['raster']['request'], 'vertical_units': 'm'}})
    call('inspect_layer', {'layer_id': counties['id']})
    derived = call('run_algorithm', {'algorithm_id': 'calculate_field',
        'arguments': {'layer_id': counties['id'], 'field': 'ALAND',
                      'expression': 'value / 1000000', 'output_field': 'land_km2'}})
    call('style_layer', {'layer_id': derived['layer_id'], 'field': 'land_km2', 'color': '#245247', 'labels': True, 'opacity': 1})
    receipts = []
    specs = [
        ('washington-counties', {'template': 'choropleth', 'focus_layer_id': derived['layer_id'],
          'map_crs': 'EPSG:5070', 'context_layer_id': None, 'legend_title': '陆地面积 / km²',
          'title': '华盛顿州 · 县域陆地面积', 'subtitle': 'Census 2024  /  39 个县  /  分位数分级',
          'source_note': '来源：U.S. Census Bureau · 2024 Cartographic Boundary Files · 1:500,000\n指标：原始 ALAND（m²）÷ 1,000,000；颜色表示县域陆地面积，不是人口或人口密度。'}),
        ('rainier-terrain', {'template': 'terrain', 'focus_layer_id': dem['id'],
          'map_crs': 'EPSG:32610', 'context_layer_id': counties['id'], 'legend_title': '高程 / m',
          'title': '雷尼尔山 · 地形与高程', 'subtitle': 'Mount Rainier, Washington  /  USGS 3DEP  /  真实高程数据',
          'source_note': '来源：USGS 3D Elevation Program · 在线高程服务按研究区裁切与双线性重采样\n1000 × 1000 像元，约 33.84 m；非原生分辨率瓦片，非实测峰顶高度。'})]
    for filename, spec in specs:
        layout = call('update_layout', {'changes': {**spec, 'plugin_id': 'python', 'paper': 'A4', 'orientation': 'landscape',
              'legend': True, 'legend_position': 'outside-right', 'north_arrow': True,
              'north_position': 'top-right', 'scale_bar': True, 'scale_position': 'bottom-left',
              'grid': True, 'extent': None, 'contour_interval': 200}})
        exports = []
        for fmt in ('png', 'pdf'):
            item = call('export_map', {'format': fmt, 'dpi': 300})
            target = OUT / (filename + '.' + fmt)
            shutil.copy2(store.root / item['path'], target)
            exports.append({'format': fmt, 'bytes': target.stat().st_size, 'path': str(target), 'artifact_id': item['id']})
        receipts.append({'name': filename, 'layout': layout, 'exports': exports})
    run.update(status='completed', message='已用真实公开 SHP 和 GeoTIFF 导出两张专业模板地图。',
               finished_at=datetime.now(timezone.utc).isoformat(), output_layers=[x['id'] for x in store.layers() if x['id'] not in existing_ids])
    store.event(run['id'], 'run_finished', {'status': 'completed'})
    store.save_run(run)
    result = {'run_id': run['id'], 'engine': 'GeoAgent professional Matplotlib templates; not QGIS/ArcGIS',
              'maps': receipts, 'sources': sources}
    (OUT / 'maps.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    (OUT / 'run.json').write_text(json.dumps({**run, 'events': store.events(run['id'])}, ensure_ascii=False, indent=2))
    print(json.dumps({'run_id': run['id'], 'outputs': [x['exports'] for x in receipts]}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
