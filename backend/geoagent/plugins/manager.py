"""Host-owned registry; providers may be supplied through geoagent.plugins entry points."""
import importlib.metadata

_FACTORIES={}


def register(plugin_id,factory):
    if plugin_id in _FACTORIES:raise ValueError('插件ID重复：'+plugin_id)
    _FACTORIES[plugin_id]=factory


class PluginManager:
    def __init__(self,store):
        self.store=store
        from .python_plugin import PythonPlugin
        from .qgis_plugin import QGISPlugin
        self.plugins={'python':PythonPlugin(),'qgis':QGISPlugin()}
        for name,factory in _FACTORIES.items():self.plugins[name]=factory()

    def enabled(self,plugin_id):
        return self.store.setting('plugins',{}).get(plugin_id,True)

    def get(self,plugin_id):
        if plugin_id not in self.plugins:raise ValueError('插件未注册，请先检查插件列表。')
        if not self.enabled(plugin_id):raise ValueError('插件已停用：'+plugin_id)
        plugin=self.plugins[plugin_id]
        status=plugin.status()
        if not status.get('available'):raise ValueError(status.get('error') or '插件运行时不可用。')
        return plugin

    def manifests(self):
        installed=[]
        for name,plugin in self.plugins.items():
            installed.append({'id':name,'name':plugin.name,'contract_version':plugin.contract_version,
                              'enabled':self.enabled(name),**plugin.status()})
        # Distribution entry points are discoverable but never imported implicitly.
        for entry in importlib.metadata.entry_points(group='geoagent.plugins'):
            if entry.name not in self.plugins:
                installed.append({'id':entry.name,'name':entry.name,'available':False,'enabled':False,
                                  'distribution':entry.dist.name,'status':'installed; explicit activation required'})
        return installed

    def toggle(self,plugin_id,enabled):
        if plugin_id not in self.plugins:
            entry=next((x for x in importlib.metadata.entry_points(group='geoagent.plugins') if x.name==plugin_id),None)
            if not entry:raise ValueError('没有发现已安装的插件包。')
            factory=entry.load();register(plugin_id,factory);self.plugins[plugin_id]=factory()
        state=self.store.setting('plugins',{});state[plugin_id]=bool(enabled)
        self.store.put_object('settings','plugins',state)
        return next(x for x in self.manifests() if x['id']==plugin_id)

    def choose(self,operation,preferred='auto'):
        if preferred and preferred!='auto':
            plugin=self.get(preferred)
            if operation not in plugin.status().get('operations',[]):raise ValueError('插件不支持此操作。')
            return plugin
        choices=list(self.plugins.values())
        choices.sort(key=lambda p:0 if p.id==self.store.setting('preferred_plugins',{}).get(operation,'qgis' if operation!='execute_code' else 'python') else 1)
        for plugin in choices:
            if self.enabled(plugin.id):
                status=plugin.status()
                if status.get('available') and operation in status.get('operations',[]):return plugin
        raise ValueError('没有可用的执行插件：'+operation)

    def algorithms(self,query=''):
        found=[]
        for name,plugin in self.plugins.items():
            if not self.enabled(name) or not plugin.status().get('available'):continue
            for spec in plugin.algorithms():
                if not query or query.lower() in (spec['id']+spec['name']+spec.get('category','')+spec.get('description','')).lower():found.append(spec)
        return found

    def spec(self,algorithm_id):
        name=algorithm_id.split(':',1)[0]
        return next((x for x in self.get(name).algorithms() if x['id']==algorithm_id),None) or self._missing()

    @staticmethod
    def _missing():raise ValueError('插件算法不存在，请先检索能力目录。')

    def input_ids(self,algorithm_id,arguments):
        spec=self.spec(algorithm_id);ids=[]
        for key,p in spec['parameters'].items():
            if p['type']=='layer' and arguments.get(key):ids.append(arguments[key])
            if p['type']=='layers':ids.extend(arguments.get(key,[]))
        return ids

    def execute(self,algorithm_id,arguments,run_id,cancel):
        return self.get(algorithm_id.split(':',1)[0]).execute(self.store,algorithm_id,arguments,run_id,cancel)
