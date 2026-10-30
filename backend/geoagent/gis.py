"""Deterministic GIS operations and explicit spatial validation."""
from __future__ import annotations
import csv
import io
import json
import math
from pyproj import CRS, Geod, Transformer
from shapely.geometry import Point, mapping, shape
from shapely.ops import transform
from shapely.strtree import STRtree
from shapely.validation import explain_validity

MAX_FEATURES = 20000
GEOD = Geod(ellps='WGS84')


def validate_collection(data, source_crs='EPSG:4326'):
    if not isinstance(data, dict) or data.get('type') != 'FeatureCollection':
        raise ValueError('需要 GeoJSON FeatureCollection。')
    features = data.get('features')
    if not isinstance(features, list) or not 1 <= len(features) <= MAX_FEATURES:
        raise ValueError(f'图层须包含 1–{MAX_FEATURES} 个要素。')
    try:
        crs = CRS.from_user_input(source_crs)
        converter = Transformer.from_crs(crs, 4326, always_xy=True)
    except Exception as exc:
        raise ValueError('无法识别输入坐标系，请填写 EPSG 编码。') from exc
    output = []
    for i, feature in enumerate(features):
        try:
            g = shape(feature['geometry'])
            if g.has_z:
                raise ValueError('第一版仅支持二维几何。')
            if g.geom_type not in ('Point', 'MultiPoint', 'LineString', 'MultiLineString', 'Polygon', 'MultiPolygon'):
                raise ValueError('不支持该几何类型。')
            g = transform(converter.transform, g)
            if g.is_empty or not g.is_valid:
                raise ValueError(explain_validity(g))
            b = g.bounds
            if not all(math.isfinite(x) for x in b) or b[0] < -180 or b[2] > 180 or b[1] < -85 or b[3] > 85:
                raise ValueError('坐标超出 WGS84 地图范围；请检查经纬度顺序和输入坐标系。')
            props = feature.get('properties') or {}
            if not isinstance(props, dict):
                raise ValueError('properties 必须是对象。')
            json.dumps(props, allow_nan=False)
            output.append({'type': 'Feature', 'id': i, 'properties': props, 'geometry': mapping(g)})
        except Exception as exc:
            raise ValueError(f'第 {i+1} 个要素无效：{exc}') from exc
    return {'type': 'FeatureCollection', 'features': output}


def import_bytes(filename, content, source_crs):
    text = content.decode('utf-8-sig')
    if filename.lower().endswith('.csv'):
        reader = csv.DictReader(io.StringIO(text))
        names = {x.lower().strip(): x for x in reader.fieldnames or []}
        lon = next((names[x] for x in ('lon', 'lng', 'longitude', 'x', '经度') if x in names), None)
        lat = next((names[x] for x in ('lat', 'latitude', 'y', '纬度') if x in names), None)
        if not lon or not lat:
            raise ValueError('CSV 需含 lon/lat、longitude/latitude、经度/纬度或 x/y 列。')
        fs = []
        for row in reader:
            if len(fs) >= MAX_FEATURES:
                raise ValueError('CSV 超出要素上限。')
            fs.append({'type': 'Feature', 'properties': row, 'geometry': {'type': 'Point', 'coordinates': [float(row[lon]), float(row[lat])]}})
        data = {'type': 'FeatureCollection', 'features': fs}
    else:
        data = json.loads(text)
        declared = (data.get('crs') or {}).get('properties', {}).get('name')
        if declared and CRS.from_user_input(declared) != CRS.from_user_input(source_crs):
            raise ValueError('文件声明的坐标系与选择不一致，请按文件实际坐标系重新导入。')
    return validate_collection(data, source_crs)


def inspect(store, layer_id):
    meta = store.get_layer(layer_id)
    data = store.data(layer_id)
    return {**meta, 'sample': [f['properties'] for f in data['features'][:3]],
            'validation': {'valid_geometry': True, 'nonempty': True, 'coordinate_bounds': True},
            'note': '坐标范围检查不能识别 GCJ-02/BD-09 偏移；导入数据必须已确认坐标基准。'}


def buffer_points(store, layer_id, distance_m, run_id):
    source = store.get_layer(layer_id)
    fs = store.data(layer_id)['features']
    if source['geometry_types'] != ['Point']:
        raise ValueError('第一版距离缓冲仅支持 Point 图层。')
    if len(fs) > 2000:
        raise ValueError('第一版缓冲最多支持 2000 个点。')
    b = source['bounds']
    if b[2] - b[0] > 6 or b[3] - b[1] > 6 or max(abs(b[1]), abs(b[3])) > 80:
        raise ValueError('第一版缓冲面向城市尺度数据（经纬度跨度均 ≤ 6°、纬度 ±80°），请先缩小范围。')
    output = []
    for i, f in enumerate(fs):
        lon, lat = f['geometry']['coordinates']
        aeqd = CRS.from_proj4(f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m')
        back = Transformer.from_crs(aeqd, 4326, always_xy=True)
        polygon = transform(back.transform, Point(0, 0).buffer(distance_m, quad_segs=64))
        coords = polygon.exterior.coords
        # Verify independent ellipsoidal distances from the point to every boundary vertex.
        errors = [abs(GEOD.inv(lon, lat, x, y)[2] - distance_m) for x, y in coords]
        if polygon.bounds[2] - polygon.bounds[0] > 6:
            raise ValueError('缓冲区跨越国际日期变更线，第一版暂不支持；请使用专门的全球几何处理流程。')
        if not polygon.is_valid or max(errors) > 0.05:
            raise ValueError('缓冲距离或几何校验失败。')
        props = {**f['properties'], 'source_id': i, 'distance_m': distance_m}
        output.append({'type': 'Feature', 'id': i, 'properties': props, 'geometry': mapping(polygon)})
    data = validate_collection({'type': 'FeatureCollection', 'features': output})
    provenance = {'run_id': run_id, 'tool': 'buffer_points', 'input': layer_id, 'input_sha256': source['sha256'],
                  'distance_m': distance_m, 'method': '每点局部 WGS84 AEQD 投影，256 段多边形近似',
                  'validation': {'geometry_valid': True, 'feature_count_preserved': True, 'boundary_vertex_error_m': '<0.05'},
                  'limitations': '直线距离缓冲，非路网服务区；边界为多边形近似。'}
    meta = store.add_layer(f"{source['name']} · {distance_m:g} m 缓冲", data, source='analysis', provenance=provenance,
                           style={'color': '#1c9c87', 'visible': True, 'opacity': 0.18})
    return {'layer_id': meta['id'], 'name': meta['name'], 'count': meta['count'], 'validation': provenance['validation'], 'method': provenance['method'], 'limitations': provenance['limitations']}


def count_points(store, polygon_layer_id, point_layer_id, run_id):
    polygons, points = store.get_layer(polygon_layer_id), store.get_layer(point_layer_id)
    if not set(polygons['geometry_types']) <= {'Polygon', 'MultiPolygon'}:
        raise ValueError('统计范围图层必须是多边形。')
    if points['geometry_types'] != ['Point']:
        raise ValueError('被统计图层必须是 Point。')
    point_geoms = [shape(f['geometry']) for f in store.data(point_layer_id)['features']]
    tree = STRtree(point_geoms)
    out, rows = [], []
    for i, f in enumerate(store.data(polygon_layer_id)['features']):
        g = shape(f['geometry'])
        n = len(tree.query(g, predicate='covers'))
        assert 0 <= n <= points['count']
        props = {**f['properties'], 'poi_count': int(n)}
        out.append({**f, 'properties': props})
        rows.append({'name': props.get('name', props.get('名称', f'范围 {i+1}')), 'poi_count': int(n)})
    prov = {'run_id': run_id, 'tool': 'count_points', 'inputs': [polygon_layer_id, point_layer_id],
            'input_sha256': [polygons['sha256'], points['sha256']], 'predicate': 'covers（包含边界）',
            'validation': {'nonnegative_integer_counts': True, 'count_not_above_input': True, 'feature_count_preserved': True},
            'limitations': '重叠范围分别计数；各范围计数之和不是去重后的 POI 总数。'}
    meta = store.add_layer(f"{polygons['name']} · POI 统计", {'type': 'FeatureCollection', 'features': out},
                           source='analysis', provenance=prov, style={'color': '#147d6c', 'visible': True, 'field': 'poi_count', 'opacity': 0.38})
    return {'layer_id': meta['id'], 'name': meta['name'], 'rows': rows[:100], 'total_regions': len(rows), 'validation': prov['validation'], 'limitations': prov['limitations']}
