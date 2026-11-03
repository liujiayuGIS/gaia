"""Executable spatial assumptions. Declarations are evidence, never inferred facts."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from pyproj import CRS
from .memory import Memory, digest
from .store import now


class SpatialContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    purpose: str = Field(default='', max_length=500)
    quantity: Literal['general','population'] = 'general'
    distance_unit: Literal['m','km','layer_units'] | None = None
    travel_mode: Literal['walk','cycle','drive'] | None = None
    cost_unit: Literal['m','km','h','min'] | None = None
    boundary: Literal['covers','contains'] = 'covers'
    overlap: Literal['per_region','unique'] = 'per_region'
    nodata: Literal['propagate','exclude'] = 'propagate'
    required_fields: dict[str,list[str]] = Field(default_factory=dict, max_length=20)
    max_date_gap_days: int | None = Field(default=None, ge=0)
    assumptions: list[str] = Field(default_factory=list, max_length=20)
    verification: Literal['standard','strict'] = 'standard'


class LayerSemantics(BaseModel):
    model_config = ConfigDict(extra='forbid')
    quantity: Literal['unspecified','count_per_cell','density','elevation','categorical','other'] = 'unspecified'
    unit: str = Field(default='', max_length=50)
    reference_date: date | None = None
    source: str = Field(min_length=1, max_length=1000)
    evidence: str = Field(min_length=1, max_length=2000)
    basis: Literal['user_declared','source_metadata','derived'] = 'user_declared'


def report(scope):
    return {'scope':scope,'checks':[],'errors':[],'warnings':[],'unverified':[],'passed':True}


def check(r, code, ok, message, *, evidence=None, severity='error'):
    r['checks'].append({'code':code,'status':'pass' if ok else severity,'message':message,'evidence':evidence or {}})
    if not ok:
        r['errors' if severity=='error' else 'warnings'].append(message)
        if severity=='error':r['passed']=False


def declare_semantics(store, layer_id, value, run_id=None):
    value=LayerSemantics.model_validate(value).model_dump(mode='json')
    value.update(content_hash=Memory(store).fingerprint(layer_id)[0], declared_at=now(),run_id=run_id)
    store.patch_layer(layer_id,{'semantics':value})
    return value


def semantic_metadata(store, layer_id, *, include_removed=False):
    value=store.get_layer(layer_id,include_removed=include_removed).get('semantics',{})
    if value and value.get('content_hash')!=Memory(store).fingerprint(layer_id,include_removed=include_removed)[0]:
        raise ValueError('数据已变化，原有语义声明失效；请重新核对单位、数量含义与数据时间。')
    return value


def family(algorithm_id):
    op=algorithm_id.split(':')[-1]
    if op in ('buffer','buffer_points','simplify','simplifygeometries'):return 'distance'
    if op in ('clip','intersection','union','difference','symmetric_difference','symmetricaldifference'):return 'overlay'
    if op in ('count_points','countpointsinpolygon'):return 'count'
    if op.startswith(('shortestpath','servicearea')):return 'network'
    if op in ('raster_calculator','rastercalculator','ndvi'):return 'raster_math'
    if op in ('raster_reproject','warpreproject','resample'):return 'raster_resample'
    if op in ('slope','aspect','hillshade'):return 'terrain'
    if op in ('zonal_statistics','zonalstatisticsfb','zonalstatistics'):return 'zonal'
    return 'general'


def contract(algorithm_id):
    f=family(algorithm_id)
    rules={
      'distance':['有限距离与单位；QGIS 平面距离使用投影坐标；经纬度距离必须显式声明 layer_units','内置算法限定局部范围，输出距离独立抽样复算'],
      'overlay':['矢量输入 CRS 对齐；面叠加核对集合覆盖范围和面积关系','验证集合几何，不证明每个属性字段的分配'],
      'count':['面与点输入；明确边界和重叠计数','当前统计逐面分别计数；需要全局去重时先融合范围'],
      'network':['线型路网、交通方式、速度与成本单位必须明确','方向字段、正速度、端点连通和路径成本复算；不推断真实通行权限'],
      'raster_math':['所有波段网格须同 CRS、分辨率、原点及尺寸','检查输出网格与 NoData 传播，不能用像元尺寸相同代替对齐'],
      'raster_resample':['分类栅格必须选最近邻或众数；人口数量重采样不自动保证守恒'],
      'terrain':['明确高程单位为米；水平坐标须为米制投影'],
      'zonal':['面与栅格输入；人口任务必须声明 count_per_cell 或 density 及单位','密度不能直接求和当作人口；应先按有效像元面积积分'],
      'general':['通用结构校验；此算法尚无专属独立核验器']}
    return {'version':1,'algorithm_id':algorithm_id,'family':f,'requirements':rules[f],
            'context_schema':SpatialContext.model_json_schema(),'domain_validator':f in ('distance','overlay','count','network','raster_math')}


def bindings(store, algorithm_id, arguments):
    if algorithm_id=='buffer_points':return {'INPUT':arguments['layer_id']}
    if algorithm_id=='count_points' and 'polygon_layer_id' in arguments:return {'INPUT':arguments['polygon_layer_id'],'POINTS':arguments['point_layer_id']}
    if algorithm_id.startswith('qgis:'):
        from .algorithms import get_spec
        spec=get_spec(algorithm_id)
        found={}
        for key,p in spec['parameters'].items():
            value=arguments.get(key)
            if p['type']=='layer' and value:found[key]=value
            elif p['type']=='layers' and value:
                found.update({f'{key}_{i}':id for i,id in enumerate(value)})
        return found
    return {key:value for key,value in arguments.items() if key.endswith('_id') and value}


def preflight(store, algorithm_id, arguments, context=None):
    ctx=SpatialContext.model_validate(context or {});f=family(algorithm_id)
    explicit_speed='DEFAULT_SPEED' in arguments or bool(arguments.get('SPEED_FIELD'))
    if algorithm_id!='buffer_points' and not (algorithm_id=='count_points' and 'polygon_layer_id' in arguments):
        from .algorithms import get_spec,validate_args
        arguments=validate_args(algorithm_id,arguments)
        if algorithm_id.startswith('qgis:'):
            arguments={**{k:p['default'] for k,p in get_spec(algorithm_id)['parameters'].items() if p.get('default') is not None},**arguments}
    r=report('空间语义前置条件');r.update(contract=contract(algorithm_id),context=ctx.model_dump())
    r['arguments']=arguments
    bound=bindings(store,algorithm_id,arguments);r['inputs']=bound
    metas={id:store.get_layer(id) for id in dict.fromkeys(bound.values())}
    r['input_hashes']={id:Memory(store).fingerprint(id)[0] for id in metas}
    crs={id:CRS(m.get('provenance',{}).get('native_crs') or m['crs']) for id,m in metas.items()}
    semantics={id:semantic_metadata(store,id) for id in metas}
    vectors=[id for id,m in metas.items() if m.get('kind')!='raster']
    rasters=[id for id,m in metas.items() if m.get('kind')=='raster']
    for id,fields in ctx.required_fields.items():
        check(r,'required_fields',id in metas and set(fields)<=set(metas.get(id,{}).get('fields',[])),
              '必要字段必须存在于绑定的输入图层。',evidence={'layer_id':id,'fields':fields})
    if ctx.max_date_gap_days is not None:
        dates=[date.fromisoformat(x['reference_date']) for x in semantics.values() if x.get('reference_date')]
        check(r,'data_dates',len(dates)==len(metas),'要求时间一致性时，所有输入必须声明数据日期。')
        if dates:check(r,'date_gap',(max(dates)-min(dates)).days<=ctx.max_date_gap_days,'输入数据日期差超过允许范围。',evidence={'days':(max(dates)-min(dates)).days})
    def geometry(id, allowed):return bool(metas[id].get('geometry_types')) and all(t in allowed for t in metas[id]['geometry_types'])
    if f=='distance' and vectors:
        id=vectors[0]
        if algorithm_id.startswith('qgis:'):
            geographic=crs[id].is_geographic
            check(r,'distance_crs',not geographic or ctx.distance_unit=='layer_units','QGIS 平面距离不能把经纬度当米；先重投影或明确使用角度单位。')
            if ctx.distance_unit in ('m','km'):
                factor=crs[id].axis_info[0].unit_conversion_factor
                check(r,'distance_unit',not geographic and abs(factor-(1000 if ctx.distance_unit=='km' else 1))<1e-9,
                      '声明的距离单位与算法实际输入坐标单位不一致；先换算参数或重投影。')
            elif not geographic and ctx.distance_unit is None:
                check(r,'distance_unit',abs(crs[id].axis_info[0].unit_conversion_factor-1)<1e-9,'非米制投影须明确 distance_unit=layer_units，或先重投影。')
        r['warnings'].append('距离的现实含义仍取决于源数据坐标基准和投影适用范围。')
    if f=='overlay' and len(vectors)>=2:
        if not algorithm_id.startswith('qgis:'):
            r['warnings'].append('内置叠加工具在 WGS84 表示中计算；核验按输出计算坐标系比较集合，再投影测量面积。高精度工程分析请使用投影数据与 QGIS。')
    if f=='count':
        area=bound.get('INPUT') or bound.get('POLYGONS') or bound.get('layer_id');points=bound.get('POINTS') or bound.get('other_id')
        check(r,'count_geometry',bool(area and points) and geometry(area,('Polygon','MultiPolygon')) and geometry(points,('Point',)), '面内计数需要面图层和 Point 图层。')
        check(r,'count_overlap',ctx.overlap=='per_region','当前算法按区域分别计数；全局去重需先融合区域，再计数。')
        # The bundled/native count uses an explicitly documented boundary predicate.
        expected='contains' if algorithm_id.startswith('qgis:') else 'covers'
        check(r,'count_boundary',ctx.boundary==expected,f'此算法使用 {expected} 边界口径；请选择匹配算法或显式确认该口径。')
        if area and points and not algorithm_id.startswith('qgis:'):
            r['warnings'].append('内置计数使用统一的 WGS84 表示；边界点判断受坐标转换精度影响。')
    if f=='network':
        id=bound.get('INPUT')
        check(r,'network_geometry',bool(id) and geometry(id,('LineString','MultiLineString')),'路网必须是线图层。')
        check(r,'travel_mode',bool(ctx.travel_mode),'路网分析必须明确 walk/cycle/drive，不推断交通方式。')
        fastest=int(arguments.get('STRATEGY',0))==1
        check(r,'network_cost',ctx.cost_unit==('h' if fastest else 'm'),'最快路径/服务区成本按小时，最短路径需米制路网；15 分钟应输入 0.25 小时。')
        if id:
            check(r,'network_crs',crs[id].is_projected and abs(crs[id].axis_info[0].unit_conversion_factor-1)<1e-9,'本版路网核验要求米制投影，便于独立复算。')
            for key in ('DIRECTION_FIELD','SPEED_FIELD'):
                if arguments.get(key):check(r,key,arguments[key] in metas[id]['fields'],f'{key} 指定字段不存在。')
        if fastest:
            speed=float(arguments.get('DEFAULT_SPEED',50))
            check(r,'network_speed',explicit_speed and speed>0,'时间成本必须显式提供正速度（km/h）或速度字段。')
            if ctx.travel_mode=='walk' and not arguments.get('SPEED_FIELD'):
                check(r,'walking_speed',0<speed<=12,'步行速度超过 12 km/h，请核对交通方式或速度单位。')
        r['unverified'].append('路网真实可通行性、立交关系及交通管制依赖数据与方法声明。')
    if f=='raster_math' and rasters:
        import rasterio
        from .formats import raster_path
        with rasterio.open(raster_path(store,rasters[0])) as base:
            for id in rasters[1:]:
                with rasterio.open(raster_path(store,id)) as other:
                    check(r,'raster_alignment',base.crs==other.crs and base.shape==other.shape and base.transform.almost_equals(other.transform,precision=1e-9),
                          '栅格网格未对齐：需要相同 CRS、尺寸、分辨率和像元原点。',evidence={'reference':rasters[0],'other':id})
    if f=='terrain':
        for id in rasters:
            check(r,'terrain_horizontal',crs[id].is_projected and abs(crs[id].axis_info[0].unit_conversion_factor-1)<1e-9,'地形分析需要米制投影 DEM。')
            check(r,'elevation_unit',semantics[id].get('quantity')=='elevation' and semantics[id].get('unit')=='m','请根据数据说明声明高程 quantity=elevation、unit=m；不能猜测垂直单位。')
    if ctx.quantity=='population':
        for id in rasters:
            q=semantics[id].get('quantity');unit=semantics[id].get('unit')
            check(r,'population_semantics',q in ('count_per_cell','density'),'人口任务须声明像元为 count_per_cell（人数）或 density（密度）。')
            check(r,'population_unit',(q=='count_per_cell' and unit=='people') or (q=='density' and unit in ('people/km2','people/m2')),'人口单位须为 people、people/km2 或 people/m2。')
            if f=='zonal' and q=='density':check(r,'population_integral',False,'人口密度不能直接求和作为人数；先按有效像元面积积分并明确边界权重。')
            if f=='raster_resample':r['warnings'].append('人口栅格重采样后必须单独核对总量守恒，当前未自动证明守恒。')
    for id in rasters:
        if f=='raster_resample' and semantics[id].get('quantity')=='categorical':
            check(r,'categorical_resampling',algorithm_id.endswith('warpreproject') and arguments.get('RESAMPLING',0) in (0,6),
                  '分类栅格重采样必须使用最近邻或众数；内置双线性重采样不适用。')
    if f=='general':r['unverified'].append('此算法尚无专属语义规则与独立领域核验器。')
    r['declarations']=semantics
    r['needs_user_input']=any(x['status']=='error' and x['code'] in ('population_semantics','population_unit','elevation_unit','travel_mode','data_dates') for x in r['checks'])
    r['fingerprint']=digest([algorithm_id,arguments,r['context'],r['input_hashes'],semantics])
    return r
