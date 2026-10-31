"""Shared quality hooks for model calls, manual tools and replayed workflows."""
from .spatial_contracts import preflight, SpatialContext, contract, LayerSemantics, declare_semantics
from .spatial_validation import validate_spatial
from .memory import digest
from .store import now


class QualityError(ValueError):
    def __init__(self,report):
        self.report=report
        super().__init__('；'.join(report['errors']))


def invocation(tool,args):
    if tool.name=='run_algorithm':return args.algorithm_id,args.arguments,args.context.model_dump() if args.context else {}
    if tool.name in ('buffer_points','count_points'):return tool.name,args.model_dump(),{}
    return None


def before(registry,tool,args,run_id):
    call=invocation(tool,args)
    if not call:return
    algorithm,parameters,context=call
    try:requested=registry.store.run(run_id).get('analysis_context') or {}
    except KeyError:requested={}
    # Explicit user requirements take precedence over model-supplied defaults.
    context={**context,**requested}
    value=preflight(registry.store,algorithm,parameters,context)
    registry.store.event(run_id,'spatial_preflight',value)
    if not value['passed']:raise QualityError(value)
    registry._local.spatial_preflight=value


def after(registry,tool,args,data,run_id):
    call=invocation(tool,args)
    if not call or not isinstance(data,dict):return
    algorithm,parameters,_=call
    value=getattr(registry._local,'spatial_preflight',None)
    if value is None:return
    result=validate_spatial(registry.store,algorithm,parameters,data,value)
    id=digest([run_id,algorithm,parameters,value['fingerprint'],result.get('output_layer_id')])[:32]
    evidence={'id':id,'run_id':run_id,'created_at':now(),'preflight':value,'domain':result}
    registry.store.put_object('quality_reports',id,evidence)
    if result.get('output_layer_id'):
        registry.store.patch_layer(result['output_layer_id'],{'quality':{'report_id':id,'passed':result['passed'],'unverified':result['unverified']}})
    data['quality']={'report_id':id,'preflight':value,'domain':result}
    registry.store.event(run_id,'spatial_validation',data['quality'])


def install(registry,Tool,Args):
    from pydantic import Field
    store=registry.store
    class Algorithm(Args):algorithm_id:str
    class Preflight(Algorithm):
        arguments:dict
        context:SpatialContext=Field(default_factory=SpatialContext)
    class Semantics(Args):
        layer_id:str
        semantics:LayerSemantics
    class Verify(Preflight):output_layer_id:str
    def verify(a,r):
        before=preflight(store,a.algorithm_id,a.arguments,a.context.model_dump())
        if not before['passed']:raise QualityError(before)
        result=validate_spatial(store,a.algorithm_id,a.arguments,{'layer_id':a.output_layer_id},before)
        id=digest([r,a.model_dump(),before['fingerprint'],result])[:32]
        store.put_object('quality_reports',id,{'id':id,'run_id':r,'created_at':now(),'preflight':before,'domain':result})
        return {'quality':{'report_id':id,'preflight':before,'domain':result}}
    registry.register(Tool('get_spatial_contract','读取算法的空间语义前提、支持的独立核验范围和 context 参数。',Algorithm,lambda a,r:contract(a.algorithm_id)))
    registry.register(Tool('preflight_analysis','不运行算法，检查空间单位、几何、字段、日期、路网成本、栅格对齐和人口含义；返回需补充的信息。',Preflight,lambda a,r:preflight(store,a.algorithm_id,a.arguments,a.context.model_dump())))
    registry.register(Tool('set_layer_semantics','根据用户明确说明或数据文档记录数量含义、单位、日期和证据。禁止猜测；与文件哈希绑定。',Semantics,lambda a,r:declare_semantics(store,a.layer_id,a.semantics.model_dump(mode='json'),r),True))
    registry.register(Tool('verify_spatial_result','独立核验已有成果，可用于自定义代码结果。声明实际采用的算法、原输入与口径；不修改数据。',Verify,verify))
    from .map_quality import install as install_map_quality
    install_map_quality(registry,Tool,Args)


def merge_report(report,data):
    quality=data.get('quality',{}) if isinstance(data,dict) else {}
    for key in ('preflight','domain','cartography'):
        part=quality.get(key)
        if part:
            report.setdefault('quality',{})[key]=part
            report['errors'].extend(part.get('errors',[]));report['warnings'].extend(part.get('warnings',[]))
            report.setdefault('unverified',[]).extend(part.get('unverified',[]))
    report['passed']=not report['errors']
    return report
