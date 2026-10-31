"""Harness-facing plugin, skill, code and reusable-document tools."""
import hashlib
import uuid
from typing import Any
from pydantic import Field
from .plugins import PluginManager
from .skills import SkillManager
from .store import now


def install(registry,Tool,Args):
    store=registry.store
    class Plugin(Args):plugin_id:str
    class Toggle(Plugin):enabled:bool
    class SearchSkill(Args):query:str=''
    class Skill(Args):skill_id:str
    class SkillResource(Skill):resource:str
    class Code(Plugin):
        code:str=Field(min_length=1,max_length=30000)
        inputs:dict[str,str]=Field(default_factory=dict,max_length=20)
        timeout:int=Field(default=60,ge=1,le=120)
        save_as:str | None=Field(default=None,max_length=100)
    class Recipe(Args):
        recipe_id:str
        inputs:dict[str,str]=Field(default_factory=dict)
    class SaveProject(Plugin):name:str=Field(min_length=1,max_length=100)
    class OpenProject(Plugin):project_id:str
    class Template(Args):
        template_id:str
        bindings:dict[str,str]=Field(default_factory=dict)
    def code(a,r):
        plugin=PluginManager(store).get(a.plugin_id)
        for layer_id in a.inputs.values():registry.execute(r,'inspect_layer',{'layer_id':layer_id},registry._local.cancel)
        result=plugin.execute_code(store,a.code,a.inputs,r,registry._local.cancel,a.timeout)
        result.pop('code',None)
        code_hash=hashlib.sha256(a.code.encode()).hexdigest();result['code_sha256']=code_hash
        if a.save_as:
            id=uuid.uuid4().hex
            recipe={'id':id,'name':a.save_as,'plugin_id':a.plugin_id,'code':a.code,'code_sha256':code_hash,
                    'inputs':a.inputs,'timeout':a.timeout,'created_at':now(),'status':'draft','version':0}
            store.put_object('recipes',id,recipe);result['recipe_id']=id
        return result
    def run_recipe(a,r):
        recipe=store.object('recipes',a.recipe_id)
        return code(Code(plugin_id=recipe['plugin_id'],code=recipe['code'],inputs=a.inputs or recipe['inputs'],timeout=recipe.get('timeout',60)),r)
    def read_skill(a,r):
        skill=SkillManager(store).read(a.skill_id)
        store.event(r,'skill_loaded',{k:skill[k] for k in ('id','name','version','sha256')})
        return skill
    def apply(a,r):
        from .cartography import update_layout
        template=store.object('templates',a.template_id);layout=template['layout'].copy()
        for key in ('focus_layer_id','context_layer_id'):
            if layout.get(key):layout[key]=a.bindings.get(layout[key],layout[key])
        layout.update(plugin_id=template['plugin_id'],template_id=a.template_id,template_bindings=a.bindings)
        return update_layout(store,layout)
    registry.register(Tool('list_plugins','列出真实插件、版本、健康状态与执行能力；不可把未安装能力宣称可用。',Args,lambda a,r:PluginManager(store).manifests()))
    registry.register(Tool('set_plugin_enabled','启用或停用本机已注册/已安装的插件。不会自动下载安装未知包。',Toggle,lambda a,r:PluginManager(store).toggle(a.plugin_id,a.enabled),True))
    registry.register(Tool('search_skills','检索已安装的 SKILL.md 任务方法。Skill 不授予新的执行权限。',SearchSkill,lambda a,r:SkillManager(store).list(a.query)))
    registry.register(Tool('read_skill','读取 Skill 步骤、约束和验收规则，记录版本与哈希。',Skill,read_skill))
    registry.register(Tool('read_skill_resource','读取 Skill 包内的脚本或参考文本，不自动执行。',SkillResource,lambda a,r:SkillManager(store).resource(a.skill_id,a.resource)))
    registry.register(Tool('execute_code','在独立、限制文件与网络访问的 Python/PyQGIS 作业中执行分析代码。plugin_id=python 或 qgis；inputs 为变量名到图层ID。代码使用 inputs/input_paths/output_dir；outputs={名称:输出文件路径}；metrics={统计值}。可 save_as 保存配方。禁止宿主机任意路径和网络。',Code,code,True))
    registry.register(Tool('list_code_recipes','列出已保存的代码配方。',Args,lambda a,r:[{k:v for k,v in x.items() if k!='code'} for x in store.objects('recipes')]))
    registry.register(Tool('run_code_recipe','使用绑定输入重新执行代码配方，生成新的独立成果。',Recipe,run_recipe,True))
    registry.register(Tool('save_project','通过支持工程能力的插件保存完整工程与数据包；QGIS 同时保存 QGZ、QPT、QML 和相对路径数据。',SaveProject,lambda a,r:PluginManager(store).get(a.plugin_id).save_project(store,a.name),True))
    registry.register(Tool('list_projects','列出可重新打开的已保存工程。',Args,lambda a,r:store.objects('projects')))
    registry.register(Tool('open_project','通过原插件重新打开已保存工程，将数据与布局恢复到当前工作区。',OpenProject,lambda a,r:PluginManager(store).get(a.plugin_id).open_project(store,a.project_id,r),True))
    registry.register(Tool('save_layout_template','通过插件保存可复用 QPT 布局模板。',SaveProject,lambda a,r:PluginManager(store).get(a.plugin_id).save_template(store,a.name),True))
    registry.register(Tool('list_layout_templates','列出可调用的已保存布局模板。',Args,lambda a,r:store.objects('templates')))
    registry.register(Tool('apply_layout_template','应用保存的布局模板；跨图层复用时 bindings 把原图层ID映射为当前图层ID。',Template,apply,True))
