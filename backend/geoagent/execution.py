"""Tool receipts complement LangGraph checkpoints across non-transactional GIS jobs."""
from contextlib import contextmanager
import time
from langgraph.types import interrupt
from langgraph.errors import GraphInterrupt
from .memory import Memory,digest
from .store import now
from .validation import validate_result


@contextmanager
def scope(registry,prefix):
    old=getattr(registry._local,'frame',None)
    registry._local.frame=[prefix,0]
    try:yield
    finally:registry._local.frame=old


def input_ids(registry,name,args):
    if name in ('remove_layer','restore_layer'):return []
    if name=='run_algorithm':
        if ':' in args.get('algorithm_id',''):
            from .plugins import PluginManager
            return PluginManager(registry.store).input_ids(args['algorithm_id'],args.get('arguments',{}))
        return [v for k,v in args.get('arguments',{}).items() if k.endswith('_id') and isinstance(v,str)]
    if name in ('execute_code','run_code_recipe','verify_code_recipe') or name.startswith('recipe_'):
        return list(args.get('inputs',{}).values())
    return [v for k,v in args.items() if k.endswith('layer_id') and isinstance(v,str)]


def approval_reason(registry,run,name,args,ids):
    # Clicking Run for a concrete code/algorithm request is already authorization.
    if run.get('mode')!='model':return None
    prefs=Memory(registry.store).preferences()
    if name in ('remember_preferences','forget_preferences','promote_code_recipe','set_plugin_enabled'):
        return '此操作会修改长期偏好、可信工具库或插件状态。'
    if name=='execute_code' and not prefs['allow_auto_code'] and not getattr(registry._local,'trusted_recipe',None):
        return '助手生成了自定义代码。请检查代码与输入后允许本次执行。'
    if name=='run_algorithm' and args.get('algorithm_id','').split(':')[0] not in ('python','qgis') and ':' in args.get('algorithm_id',''):
        return '此算法来自第三方执行插件，需要确认。'
    if any(registry.store.get_layer(id).get('count',0)>1000000 for id in ids) and name in ('run_algorithm','execute_code'):
        return '本次输入超过一百万要素或像元，可能需要较多计算时间。'
    return None


def request_approval(store,run_id,step_id,name,args,reason,fingerprints):
    id=digest([run_id,step_id,name,args,fingerprints,reason])[:32]
    try:record=store.object('approvals',id)
    except ValueError:
        record={'id':id,'run_id':run_id,'step_id':step_id,'tool':name,'arguments':args,'reason':reason,
                'input_hashes':fingerprints,'status':'pending','created_at':now()}
        store.put_object('approvals',id,record);store.event(run_id,'approval_requested',record)
    if record['status']=='denied':raise PermissionError('用户拒绝了此操作。')
    if record['status']=='approved':return
    decision=interrupt(record)
    if not isinstance(decision,dict) or decision.get('approval_id')!=id or not isinstance(decision.get('approved'),bool):
        raise ValueError('审批响应与当前操作不一致。')
    record.update(status='approved' if decision['approved'] else 'denied',decided_at=now())
    store.put_object('approvals',id,record);store.event(run_id,'approval_decided',record)
    if not decision['approved']:raise PermissionError('用户拒绝了此操作。')


def execute(registry,run_id,name,raw,cancel):
    if cancel.is_set():raise InterruptedError('用户已停止任务')
    store=registry.store;registry._local.cancel=cancel
    frame=getattr(registry._local,'frame',None)
    if frame is None:return registry._execute_untracked(run_id,name,raw,cancel)
    step_id=frame[0]+':'+str(frame[1]);frame[1]+=1
    signature=digest([name,raw]);previous=store.step(run_id,step_id)
    if previous and previous['signature']!=signature:raise ValueError('恢复时工具参数发生变化，请新建任务。')
    if previous and previous['status']=='completed' and previous.get('result',{}).get('success'):
        removed={s.get('result',{}).get('data',{}).get('removed_id') for s in store.steps(run_id)
                 if s.get('name')=='remove_layer' and s.get('result',{}).get('success')}
        from .spatial_contracts import semantic_metadata
        declarations=previous['result'].get('data',{}).get('quality',{}).get('preflight',{}).get('declarations',{})
        for id,old in declarations.items():
            if semantic_metadata(store,id,include_removed=id in removed)!=old:raise ValueError('输入的空间语义声明在暂停后变化，请重新规划任务。')
        for id,expected in previous.get('input_hashes',{}).items():
            if Memory(store).fingerprint(id,include_removed=id in removed)[0]!=expected:raise ValueError('已完成步骤的输入发生变化，不能安全续跑。')
        # Check the exact published result rather than recreating it.
        if previous['result'].get('success'):
            for item in previous['result'].get('validation',{}).get('layers',[]):
                current,_=Memory(store).fingerprint(item['layer_id'],include_removed=item['layer_id'] in removed)
                if current!=item.get('content_hash'):raise ValueError('已完成步骤的成果发生变化，不能安全续跑。')
            import hashlib
            for item in previous['result'].get('validation',{}).get('artifacts',[]):
                path=store.root/item['path']
                if not path.is_file():raise ValueError('已完成步骤的导出文件丢失，不能安全续跑。')
                with path.open('rb') as stream:current=hashlib.file_digest(stream,'sha256').hexdigest()
                if current!=item['sha256']:raise ValueError('已完成步骤的导出文件变化，不能安全续跑。')
        if name in ('remove_layer','restore_layer') and not validate_result(store,name,previous['result']['data'])['passed']:
            raise ValueError('图层删除或恢复状态在暂停后变化，请新建任务。')
        store.event(run_id,'tool_replayed',{'step_id':step_id,'name':name})
        return previous['result']
    start=time.monotonic();run=store.run(run_id)
    record={'id':step_id,'name':name,'arguments':raw,'signature':signature,'status':'prepared',
            'attempt':(previous or {}).get('attempt',0),'created_at':(previous or {}).get('created_at',now())}
    try:
        tool=registry.tools.get(name)
        if not tool:raise ValueError('未知工具；只能调用当前注册工具。')
        args=tool.args.model_validate(raw);ids=input_ids(registry,name,raw)
        for id in ids:
            try:catalog=store.object('catalog',id)
            except ValueError:catalog={}
            if catalog.get('source_changed') or catalog.get('stale'):raise ValueError('输入数据已失效，请重新导入源数据或重算上游成果。')
        hashes={id:Memory(store).fingerprint(id)[0] for id in ids}
        for id,value in hashes.items():
            try:known=store.object('catalog',id)
            except ValueError:continue
            if known['content_hash']!=value:raise ValueError('输入文件与项目目录版本不一致，请刷新目录并重新导入。')
        if previous and previous.get('input_hashes',hashes)!=hashes:raise ValueError('输入数据在暂停后变化，请新建任务。')
        record['input_hashes']=hashes
        for hook in registry.pre_hooks:hook(tool,args,run_id)
        composite=name in ('run_workflow','run_code_recipe','verify_code_recipe') or name.startswith('recipe_')
        if previous and ((previous['status']=='running' and not composite) or previous.get('uncertain') or (not previous.get('result',{}).get('success') and previous.get('published_layers'))):
            record['uncertain']=True
            request_approval(store,run_id,step_id,name,raw,'上次执行在成果确认前中断，可能已有输出。请检查运行记录，允许后才重新执行此步。',hashes)
        reason=approval_reason(registry,run,name,raw,ids)
        if reason:request_approval(store,run_id,step_id,name,raw,reason,hashes)
        record.update(status='running',uncertain=False,attempt=record['attempt']+1,started_at=now())
        before={x['id'] for x in store.layers()}
        store.save_step(run_id,step_id,record)
        store.event(run_id,'tool_started',{'step_id':step_id,'name':name,'arguments':raw})
        store.event(run_id,'permission_checked',{'step_id':step_id,'tool':name,'decision':'allow','policy':'explicit approval' if reason else 'workspace scoped operation'})
        with scope(registry,step_id):data=tool.handler(args,run_id)
        for hook in registry.post_hooks:hook(tool,args,data,run_id)
        report=validate_result(store,name,data)
        store.event(run_id,'validation_completed',{'step_id':step_id,'tool':name,'checks':report})
        result={'success':report['passed'],'data':data,'validation':report}
        if not report['passed']:result['error']='；'.join(report['errors'])
    except GraphInterrupt:
        record['status']='waiting_approval';store.save_step(run_id,step_id,record)
        raise
    except InterruptedError:raise
    except Exception as exc:
        result={'success':False,'error':str(exc),'retry':'检查图层、参数、数据版本和工具说明后再调用。'}
        if hasattr(exc,'report'):result['quality']=exc.report
    if 'before' in locals():record['published_layers']=[x['id'] for x in store.layers() if x['id'] not in before]
    result['step_id']=step_id
    record.update(status='completed',result=result,finished_at=now())
    store.save_step(run_id,step_id,record)
    store.event(run_id,'tool_completed',{'step_id':step_id,'name':name,'result':result,'duration_ms':round((time.monotonic()-start)*1000)})
    return result
