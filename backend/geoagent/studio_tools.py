"""Studio capability plugins bound to the common typed tool runtime."""
from __future__ import annotations
from typing import Any
from pydantic import Field
from . import formats,algorithms,cartography,workflows


def install(registry,Tool,Args):
    store=registry.store
    class Search(Args):
        query: str=''
    class Algorithm(Args):
        algorithm_id: str
    class RunAlgorithm(Algorithm):
        arguments: dict[str,Any]
    class Asset(Args):
        asset_id: str
    class Import(Asset):
        resource: str | None=None
        sublayer: str | None=None
        source_crs: str | None=None
    class Layout(Args):
        changes: dict[str,Any]
    class ExportMap(Args):
        format: str='pdf'
        dpi: int=150
        layer_ids: list[str] | None=None
    class ExportData(Args):
        layer_id: str
        format: str='gpkg'
        target_crs: str | None=None
    class Plan(Args):
        steps: list[str]=Field(min_length=1,max_length=20)
    class MapView(Args):
        layer_id: str
    class SaveWorkflow(Args):
        name: str
        nodes: list[dict[str,Any]]
    class RunWorkflow(Args):
        workflow_id: str
    class Query(Args):
        layer_id: str
        limit: int=Field(default=20,ge=1,le=100)
    def search(a,r):
        return [x for x in algorithms.CATALOG if not a.query or a.query.lower() in (x['id']+x['name']+x['category']+x['description']).lower()]
    def export_data(a,r):
        import uuid
        from .store import now
        meta=store.get_layer(a.layer_id)
        if meta.get('kind')=='raster':
            if a.format not in ('tif','tiff','geotiff'):raise ValueError('原始栅格导出请使用 tif。')
            path=formats.raster_path(store,a.layer_id)
        elif a.format in ('geojson','csv'):
            return {'name':meta['name']+'.'+a.format,'url':f'/api/layers/{a.layer_id}/export?format={a.format}'}
        else:path=formats.export_vector(store,a.layer_id,a.format,a.target_crs)
        export_id=uuid.uuid4().hex
        relative=str(path.relative_to(store.root))
        return store.put_object('exports',export_id,{'id':export_id,'name':meta['name']+path.suffix,'path':relative,'url':f'/api/exports/{export_id}/download','run_id':r,'created_at':now()})
    def plan(a,r):
        steps=[{'title':x,'status':'pending'} for x in a.steps]
        store.event(r,'plan_updated',{'steps':steps})
        return {'steps':steps}
    def map_view(a,r):
        meta=store.get_layer(a.layer_id)
        return store.put_object('settings','map_command',{'id':__import__('uuid').uuid4().hex,'bounds':meta['bounds']})
    def query(a,r):
        if store.get_layer(a.layer_id).get('kind')=='raster':return store.get_layer(a.layer_id)
        features=store.data(a.layer_id)['features']
        return {'total':len(features),'features':features[:a.limit]}
    registry.register(Tool('search_algorithms','检索可用 GIS 算法目录；返回真实输入参数与输出契约。',Search,search))
    registry.register(Tool('get_algorithm','读取算法的完整参数和适用条件。',Algorithm,lambda a,r:algorithms.get_spec(a.algorithm_id)))
    registry.register(Tool('run_algorithm','执行已注册算法。先检查输入；严格按 get_algorithm 参数传入。结果保存为新图层并附加血缘。',RunAlgorithm,lambda a,r:algorithms.run_algorithm(store,a.algorithm_id,a.arguments,r),True))
    registry.register(Tool('list_imports','列出用户已上传到数据收件箱的资产与可导入子资源；不读取宿主机任意目录。',Args,lambda a,r:store.objects('assets')))
    registry.register(Tool('inspect_import','检查待导入数据的文件、驱动、坐标系和子图层。',Asset,lambda a,r:store.object('assets',a.asset_id)))
    registry.register(Tool('import_data','导入用户已上传的资产；遇到多资源必须指定 resource，多图层必须指定 sublayer；缺少 CRS 需用户明确。',Import,lambda a,r:formats.import_asset(store,a.asset_id,a.resource,a.source_crs,a.sublayer,r),True))
    registry.register(Tool('get_layout','读取当前出图布局和指北针、图例、比例尺位置。',Args,lambda a,r:cartography.get_layout(store)))
    registry.register(Tool('update_layout','设置制图布局。支持 title/subtitle/paper(A4/A3)/orientation/north_arrow/north_position/legend/legend_position/scale_bar/scale_position/grid/source_note/extent。位置使用 top-left/top-right/bottom-left/bottom-right。',Layout,lambda a,r:cartography.update_layout(store,a.changes),True))
    registry.register(Tool('export_map','按当前布局导出真实 PNG/JPEG/TIFF/SVG/PDF，返回可下载成果；dpi 可选 100/150/200/300。',ExportMap,lambda a,r:cartography.export_map(store,a.format,a.dpi,a.layer_ids,r),True))
    registry.register(Tool('export_data','导出矢量为 geojson/csv/gpkg/shp/fgb/parquet/kml/gml，栅格为 tif；实际支持以 GDAL 驱动为准。',ExportData,export_data,True))
    registry.register(Tool('update_task_plan','在复杂处理前给出可见执行步骤，不写隐藏思维过程。',Plan,plan))
    registry.register(Tool('zoom_to_layer','定位地图到图层范围。',MapView,map_view,True))
    registry.register(Tool('query_features','按限制读取属性与少量几何样本；最多100条。',Query,query))

    registry.register(Tool('save_workflow','保存同项目可重放GIS工作流。nodes 每项包含 id、algorithm_id、arguments；下游可用 $node_id.layer_id 引用上游图层。最多12节点，拒绝循环依赖。',SaveWorkflow,lambda a,r:workflows.save(store,a.name,a.nodes),True))
    registry.register(Tool('list_workflows','列出已保存的同项目GIS工作流。',Args,lambda a,r:store.objects('workflows')))
    registry.register(Tool('run_workflow','重放已保存的确定性GIS工作流，每个节点独立校验并发布新图层。',RunWorkflow,lambda a,r:workflows.execute(store,registry,a.workflow_id,r,registry._local.cancel),True))

    registry.register(Tool('get_map_state','读取前端当前地图范围、中心和缩放级别；导出当前范围时将 bounds 传给 update_layout.extent。',Args,lambda a,r:store.setting('map_state',{})))
