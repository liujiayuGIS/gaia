"""Deterministic GIS/artifact acceptance, independent of the model's final prose."""
import json
import math
import hashlib
from pathlib import Path
from .memory import Memory


def result_layers(data):
    if not isinstance(data,dict):return []
    ids=[data['layer_id']] if data.get('layer_id') else []
    ids.extend(x['layer_id'] for x in data.get('layers',[]) if isinstance(x,dict) and x.get('layer_id'))
    return list(dict.fromkeys(ids))


def check_layer(store,id,requirements=None):
    from pyproj import CRS
    requirements=requirements or {};errors=[];warnings=[]
    layer=store.get_layer(id)
    content_hash,_=Memory(store).fingerprint(id)
    if layer.get('kind')=='raster':
        import rasterio
        from .formats import raster_path
        with rasterio.open(raster_path(store,id)) as src:
            if not src.crs or src.width<=0 or src.height<=0:errors.append('栅格缺少 CRS 或有效尺寸')
            if src.width*src.height!=layer.get('count'):errors.append('栅格尺寸与目录不一致')
    else:
        from shapely.geometry import shape
        data=store.data(id);features=data['features']
        if len(features)!=layer['count']:errors.append('要素数量与目录不一致')
        for f in features:
            g=shape(f['geometry'])
            if not g.is_valid or g.is_empty:errors.append('包含无效或空几何');break
            if not all(math.isfinite(x) for x in g.bounds):errors.append('几何范围包含非有限数值');break
        if requirements.get('geometry_type') and requirements['geometry_type'] not in layer['geometry_types']:errors.append('几何类型不符合验收条件')
    CRS(layer['crs'])
    native=layer.get('provenance',{}).get('native_crs',layer['crs'])
    if requirements.get('crs') and CRS(native)!=CRS(requirements['crs']):errors.append('成果 CRS 不符合验收条件')
    if not set(requirements.get('fields',[]))<=set(layer.get('fields',[])):errors.append('缺少要求的输出字段')
    if 'min_count' in requirements and layer['count']<requirements['min_count']:errors.append('成果数量小于验收要求')
    if requirements.get('max_count') is not None and layer['count']>requirements['max_count']:errors.append('成果数量超过验收要求')
    if layer['count']==0:warnings.append('结果为空，请确认空间范围和筛选条件')
    return {'layer_id':id,'passed':not errors,'errors':errors,'warnings':warnings,'content_hash':content_hash,
            'checks':['file_exists','crs','geometry_or_dimensions','count','declared_requirements']}


def validate_result(store,name,data,requirements=None):
    if not isinstance(data,dict):return {'passed':True,'layers':[],'artifacts':[],'errors':[],'warnings':[]}
    layers=[];errors=[];warnings=[];artifacts=[]
    if requirements and any(requirements.get(k) for k in ('fields','crs','geometry_type','min_count')) and not result_layers(data):
        errors.append('验收条件要求空间图层，但工具未发布图层')
    for id in result_layers(data):
        try:report=check_layer(store,id,requirements)
        except Exception as exc:report={'layer_id':id,'passed':False,'errors':[str(exc)],'warnings':[]}
        layers.append(report);errors.extend(report['errors']);warnings.extend(report['warnings'])
    candidates=list(data.get('artifacts',[]))
    if data.get('path') and data.get('url'):candidates.append(data)
    for item in candidates:
        if not item.get('path'):continue
        path=(store.root/item['path']).resolve()
        passed=path.is_relative_to(store.root.resolve()) and path.is_file() and path.stat().st_size>0
        checksum=None
        if passed:
            with path.open('rb') as stream:checksum=hashlib.file_digest(stream,'sha256').hexdigest()
        artifacts.append({'id':item.get('id'),'format':item.get('format'),'passed':passed,'path':item['path'],'sha256':checksum})
        if not passed:errors.append('导出成果不存在、为空或位于工作区外')
    inherited=data.get('validation',{})
    if isinstance(inherited,dict):
        for key,value in inherited.items():
            if value is False:
                if key=='nonempty':warnings.append('图层为空，请确认筛选条件')
                else:errors.append('工具后置校验失败：'+key)
    if name=='execute_code' and not layers and not candidates and not data.get('scalars'):
        errors.append('代码没有发布图层、文件或统计结果')
    return {'passed':not errors,'layers':layers,'artifacts':artifacts,'errors':errors,'warnings':warnings,
            'scope':'结构、空间数据有效性、文件完整性与声明的验收条件；不替代领域方法或视觉审核'}


def validate_run(store,run):
    errors=[];warnings=[];layers=[];unresolved={}
    for step in store.steps(run['id']):
        if step.get('status')!='completed':continue
        result=step.get('result',{})
        warnings.extend(result.get('validation',{}).get('warnings',[]))
        if result.get('success'):unresolved.pop(step['name'],None)
        else:unresolved[step['name']]=result.get('error','工具执行失败')
    errors.extend(unresolved.values())
    plan=store.setting('plan:'+run['id'],{})
    if any(x.get('status')=='blocked' for x in plan.get('steps',[])):errors.append('执行计划仍有阻塞步骤')
    elif any(x.get('status')!='completed' for x in plan.get('steps',[])):warnings.append('部分计划步骤尚未关联完成证据，请检查执行记录')
    requirements=store.setting('acceptance:'+run['id'],run.get('acceptance',{}))
    published=[x for x in store.layers() if x.get('provenance',{}).get('run_id')==run['id']]
    for layer in published:
        try:report=check_layer(store,layer['id'],requirements.get('layer',{}) if layer['id']==published[-1]['id'] else {})
        except Exception as exc:report={'passed':False,'layer_id':layer['id'],'errors':[str(exc)],'warnings':[]}
        layers.append(report);errors.extend(report['errors']);warnings.extend(report['warnings'])
    exports=[x for x in store.objects('exports') if x.get('run_id')==run['id']]
    formats={x.get('format') for x in exports}
    for fmt in requirements.get('formats',[]):
        if fmt not in formats:errors.append('缺少要求的导出格式：'+fmt)
    if requirements.get('require_layer') and not layers:errors.append('任务要求生成图层，但没有发布成果')
    for item in exports:
        path=(store.root/item['path']).resolve()
        if not path.is_relative_to(store.root.resolve()) or not path.is_file() or path.stat().st_size==0:errors.append('导出文件丢失或为空：'+item.get('name',''))
    return {'passed':not errors,'errors':list(dict.fromkeys(errors)),'warnings':list(dict.fromkeys(warnings)),
            'layers':layers,'artifact_count':len(exports),'requirements':requirements}
