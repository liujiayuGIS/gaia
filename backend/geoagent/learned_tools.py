"""Draft code -> executable verification -> explicit review -> typed reusable tool."""
import hashlib
import uuid
import math
from pydantic import create_model
from .memory import Memory,digest
from .store import now
from .validation import validate_result


def check_result(store,data,checks):
    report=validate_result(store,'execute_code',data,checks.get('layer',{}))
    for key,bounds in checks.get('metrics',{}).items():
        value=data.get('scalars',{}).get(key)
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or not bounds['min']<=value<=bounds['max']:
            report['errors'].append('统计指标未通过：'+key)
    report['passed']=not report['errors']
    return report


def verify(registry,recipe_id,inputs,checks,run_id):
    store=registry.store;recipe=store.object('recipes',recipe_id)
    bindings=inputs or recipe['inputs']
    if set(bindings)!=set(recipe['inputs']):raise ValueError('验证输入别名必须与配方一致。')
    result=registry.execute(run_id,'execute_code',{'plugin_id':recipe['plugin_id'],'code':recipe['code'],
        'inputs':bindings,'timeout':recipe.get('timeout',60)},registry._local.cancel)
    if not result['success']:raise ValueError(result['error'])
    report=check_result(store,result['data'],checks)
    from .plugins import PluginManager
    case={'id':uuid.uuid4().hex,'run_id':run_id,'code_sha256':hashlib.sha256(recipe['code'].encode()).hexdigest(),
          'inputs':bindings,'input_hashes':{id:Memory(store).fingerprint(id)[0] for id in bindings.values()},
          'checks':checks,'report':report,'runtime':PluginManager(store).get(recipe['plugin_id']).status(),
          'artifacts':result['data'].get('artifacts',[]),'created_at':now()}
    recipe['verification']=case;recipe['status']='verified' if report['passed'] else 'draft'
    store.put_object('recipes',recipe_id,recipe)
    if not report['passed']:raise ValueError('配方验证失败：'+'；'.join(report['errors']))
    return {'recipe_id':recipe_id,'status':'verified','verification':case}


def promote(store,recipe_id,reviewed):
    recipe=store.object('recipes',recipe_id);case=recipe.get('verification',{})
    if not reviewed:raise ValueError('请检查代码、验证指标与成果后再确认推广。')
    if recipe.get('status') not in ('verified','promoted') or not case.get('report',{}).get('passed'):
        raise ValueError('配方需要先完成可执行验证。')
    if case['code_sha256']!=hashlib.sha256(recipe['code'].encode()).hexdigest():raise ValueError('代码已改变，请重新验证。')
    for id,expected in case['input_hashes'].items():
        if Memory(store).fingerprint(id)[0]!=expected:raise ValueError('验证数据已改变，请重新验证。')
    recipe.update(status='promoted',reviewed_at=now(),tool_name='recipe_'+recipe_id,version=recipe.get('version',0)+1)
    return store.put_object('recipes',recipe_id,recipe)


def register_recipes(registry,Tool,Args):
    for recipe in registry.store.objects('recipes'):
        if recipe.get('status')!='promoted':continue
        aliases=recipe.get('inputs',{})
        # Parameter schemas expose required bindings, rather than an untyped script blob.
        Inputs=create_model('RecipeInputs_'+recipe['id'],__base__=Args,**{name:(str,...) for name in aliases})
        Arguments=create_model('RecipeArgs_'+recipe['id'],__base__=Args,inputs=(Inputs,...))
        def run(a,r,recipe_id=recipe['id']):
            current=registry.store.object('recipes',recipe_id)
            if current.get('status')!='promoted':raise ValueError('此工具已失效，请重新验证并审核。')
            if hashlib.sha256(current['code'].encode()).hexdigest()!=current['verification']['code_sha256']:
                raise ValueError('工具代码版本已变化，必须重新验证。')
            bindings=a.inputs.model_dump()
            registry._local.trusted_recipe=current['id']
            try:
                result=registry.execute(r,'execute_code',{'plugin_id':current['plugin_id'],'code':current['code'],
                    'inputs':bindings,'timeout':current.get('timeout',60)},registry._local.cancel)
            finally:registry._local.trusted_recipe=None
            if not result['success']:raise ValueError(result['error'])
            report=check_result(registry.store,result['data'],current['verification']['checks'])
            if not report['passed']:raise ValueError('复用工具的输出未通过原验收条件：'+'；'.join(report['errors']))
            return {**result['data'],'recipe_id':recipe_id,'recipe_version':current['version']}
        registry.register(Tool(recipe['tool_name'],'经验证与人工审核的工具：'+recipe['name'],Arguments,run,True))
