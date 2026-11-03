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
    warnings.extend(layer.get('import_warnings',[]))
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
    if name=='remove_layer':
        id=data.get('removed_id');errors=[]
        if not id or any(x['id']==id for x in store.layers()):errors.append('图层仍在工作区中，删除未完成')
        try:
            store.object('removed_layers',id)
        except ValueError:errors.append('删除记录不存在')
        return {'passed':not errors,'layers':[],'artifacts':[],'errors':errors,'warnings':[],'checks':['absent_from_workspace','recovery_metadata_retained']}
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
    from .quality import merge_report
    return merge_report({'passed':not errors,'layers':layers,'artifacts':artifacts,'errors':errors,'warnings':warnings,
            'scope':'结构、空间数据有效性、文件完整性、声明的验收条件及适用的独立核验'},data)


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
    exports=[x for x in store.objects('exports') if x.get('run_id')==run['id'] and not x.get('superseded_by')]
    formats={x.get('format') for x in exports}
    for fmt in requirements.get('formats',[]):
        if fmt not in formats:errors.append('缺少要求的导出格式：'+fmt)
    if requirements.get('require_layer') and not layers:errors.append('任务要求生成图层，但没有发布成果')
    for item in exports:
        path=(store.root/item['path']).resolve()
        if not path.is_relative_to(store.root.resolve()) or not path.is_file() or path.stat().st_size==0:errors.append('导出文件丢失或为空：'+item.get('name',''))
    quality=[];unverified=[];seen=set()
    for item in store.objects('quality_reports'):
        if item.get('run_id')!=run['id']:continue
        domain=item['domain'];key=item['preflight']['fingerprint']
        if key in seen:continue
        seen.add(key);quality.append(item)
        if domain.get('output_layer_id') and domain.get('output_hash'):
            try:
                if Memory(store).fingerprint(domain['output_layer_id'])[0]!=domain['output_hash']:errors.append('成果文件发生变化，独立核验报告已失效。')
            except Exception as exc:errors.append(str(exc))
        errors.extend(domain.get('errors',[]));warnings.extend(item['preflight'].get('warnings',[])+domain.get('warnings',[]))
        unverified.extend(item['preflight'].get('unverified',[])+domain.get('unverified',[]))
    code_outputs=set()
    for step in store.steps(run['id']):
        if step.get('name')=='execute_code' and step.get('result',{}).get('success'):
            code_outputs.update(result_layers(step['result'].get('data',{})))
    verified={q['domain'].get('output_layer_id') for q in quality if q['domain'].get('passed') and q['domain'].get('coverage')=='complete_within_scope'}
    if code_outputs-verified:
        message='自定义代码成果尚无完整的独立领域核验：'+', '.join(sorted(code_outputs-verified))
        unverified.append(message)
        if (run.get('analysis_context') or {}).get('verification')=='strict':errors.append(message)
    maps=[]
    for item in exports:
        if not item.get('map_review_id'):continue
        review=store.object('map_reviews',item['map_review_id']);maps.append({'review_id':review['id'],'preview_url':review['preview_url'],**review['report']})
        errors.extend(review['report']['errors']);warnings.extend(review['report']['warnings']);unverified.extend(review['report']['unverified'])
        if run.get('mode')=='model' and run.get('vision_enabled',True) and review['visual_review']['status']!='pass':
            errors.append('导出地图尚未通过视觉审阅，请 inspect_map(export_id='+item['id']+') 后记录观察或修改重出图。')
    return {'passed':not errors,'errors':list(dict.fromkeys(errors)),'warnings':list(dict.fromkeys(warnings)),
            'unverified':list(dict.fromkeys(unverified)),'quality_reports':quality,'map_reviews':maps,
            'layers':layers,'artifact_count':len(exports),'requirements':requirements,'report_url':f"/api/runs/{run['id']}/quality"}
