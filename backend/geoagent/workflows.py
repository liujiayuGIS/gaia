"""Bounded deterministic DAG replay with typed algorithm contracts and node receipts."""
import re
import uuid
from .algorithms import get_spec,validate_args
from .store import now

REF=re.compile(r'^\$([a-z][a-z0-9_]{0,31})\.layer_id$')


def validate(nodes):
    if not isinstance(nodes,list) or not 1<=len(nodes)<=12:raise ValueError('工作流需要1–12个节点。')
    ids=set()
    for node in nodes:
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,31}',node.get('id','')) or node['id'] in ids:raise ValueError('节点ID无效或重复。')
        ids.add(node['id']);get_spec(node['algorithm_id']);validate_args(node['algorithm_id'],node['arguments'])
    pending={n['id']:n for n in nodes};ordered=[];done=set()
    while pending:
        ready=[]
        for id,node in pending.items():
            refs={m.group(1) for value in node['arguments'].values() if isinstance(value,str) and (m:=REF.fullmatch(value))}
            if not refs<=ids:raise ValueError('工作流引用了不存在的节点。')
            if refs<=done:ready.append(id)
        if not ready:raise ValueError('工作流存在循环依赖。')
        for id in ready:ordered.append(pending.pop(id));done.add(id)
    return ordered


def save(store,name,nodes):
    ordered=validate(nodes);id=uuid.uuid4().hex
    item={'id':id,'name':name[:100],'nodes':ordered,'created_at':now(),'contract_version':1}
    return store.put_object('workflows',id,item)


def execute(store,registry,workflow_id,run_id,cancel):
    workflow=store.object('workflows',workflow_id);nodes=validate(workflow['nodes']);outputs={};receipt={'id':uuid.uuid4().hex,'workflow_id':workflow_id,'run_id':run_id,'nodes':[],'created_at':now(),'status':'running'}
    store.event(run_id,'plan_updated',{'steps':[{'title':get_spec(n['algorithm_id'])['name'],'status':'pending'} for n in nodes]})
    for node in nodes:
        args={}
        for key,value in node['arguments'].items():
            match=REF.fullmatch(value) if isinstance(value,str) else None
            args[key]=outputs[match.group(1)]['layer_id'] if match else value
        store.event(run_id,'workflow_node_started',{'node_id':node['id'],'algorithm':node['algorithm_id']})
        if ':' in node['algorithm_id']:
            from .plugins import PluginManager
            inputs=PluginManager(store).input_ids(node['algorithm_id'],args)
        else:inputs=[value for key,value in args.items() if key.endswith('_id')]
        for value in inputs:registry.execute(run_id,'inspect_layer',{'layer_id':value},cancel)
        result=registry.execute(run_id,'run_algorithm',{'algorithm_id':node['algorithm_id'],'arguments':args},cancel)
        receipt['nodes'].append({'node_id':node['id'],'arguments':args,'result':result})
        if not result['success']:
            receipt['status']='failed';store.put_object('workflow_runs',receipt['id'],receipt)
            raise ValueError(f"工作流节点 {node['id']} 失败：{result['error']}。已生成的图层保留。")
        outputs[node['id']]=result['data'];store.event(run_id,'workflow_node_completed',{'node_id':node['id'],'layer_id':result['data']['layer_id']})
        store.put_object('workflow_runs',receipt['id'],receipt)
    receipt['status']='completed';store.put_object('workflow_runs',receipt['id'],receipt)
    return {'workflow_id':workflow_id,'receipt_id':receipt['id'],'outputs':outputs,'status':'completed'}
