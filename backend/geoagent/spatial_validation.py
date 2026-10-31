"""Independent, bounded GIS checks over physical inputs and published outputs."""
import math
import numpy as np
from pyproj import CRS
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
from .formats import frame, raster_path
from .spatial_contracts import report, check, family, SpatialContext

MAX_FEATURES=100000
MAX_PAIRS=2000000


def incomplete(r, message):
    r['coverage']='partial'
    r['unverified'].append(message)


def vectors(store,id,crs=None):
    # The web GeoJSON is WGS84; analysis/verification must retain native coordinates.
    path=store.root/'layers'/(id+'.gpkg')
    if path.is_file():
        import geopandas as gpd
        value=gpd.read_file(path,engine='pyogrio')
    else:value=frame(store,id)
    if len(value)>MAX_FEATURES:raise ValueError('独立核验超出 100000 要素预算，需分区核验。')
    return value.to_crs(crs) if crs else value


def metric_crs(value):
    bounds=value.to_crs(4326).total_bounds
    if not np.isfinite(bounds).all() or bounds[2]-bounds[0]>6 or bounds[3]-bounds[1]>6 or max(abs(bounds[1]),abs(bounds[3]))>80:
        raise ValueError('独立几何核验当前限定城市/区域尺度（跨度 ≤6°、纬度 ±80°）。')
    return value.estimate_utm_crs()


def validate_overlay(store,op,a,b,output,r):
    source=vectors(store,a);out=vectors(store,output);compute_crs=out.crs
    crs=metric_crs(source);left=source.to_crs(compute_crs);right=vectors(store,b,compute_crs)
    if not all('Polygon' in t for df in (left,right,out) for t in df.geom_type):
        incomplete(r,'叠加集合与面积核验只适用于面输入/面输出，线点结果未核验。');return
    x=unary_union(left.geometry);y=unary_union(right.geometry);z=unary_union(out.geometry)
    expected={'clip':lambda:x.intersection(y),'intersection':lambda:x.intersection(y),'union':lambda:x.union(y),
              'difference':lambda:x.difference(y),'symmetric_difference':lambda:x.symmetric_difference(y),
              'symmetricaldifference':lambda:x.symmetric_difference(y)}[op]()
    import geopandas as gpd
    measured=gpd.GeoSeries([expected,z,z.symmetric_difference(expected)],crs=compute_crs).to_crs(crs)
    expected_area,actual_area,error=measured.area.tolist();tol=max(.05,expected_area*1e-7)
    check(r,'overlay_coverage',error<=tol,'叠加结果的集合覆盖范围与输入集合运算不一致。',
          evidence={'computation_crs':str(compute_crs),'measurement_crs':str(crs),'expected_area_m2':expected_area,'actual_union_area_m2':actual_area,'symmetric_difference_m2':error,'tolerance_m2':tol})
    r['unverified'].append('不验证叠加属性分配；输入内部重叠时不把逐行面积总和当作并集面积。')


def validate_counts(store,a,b,output,args,ctx,r):
    out=vectors(store,output);areas=vectors(store,a,out.crs);points=vectors(store,b,out.crs)
    field=args.get('FIELD') or 'poi_count'
    if args.get('WEIGHT') or args.get('CLASSFIELD'):
        incomplete(r,'加权/分类计数不适用普通点数核验。');return
    check(r,'count_rows',len(out)==len(areas),'计数输出区域数量改变。')
    from shapely.strtree import STRtree
    area_tree=STRtree(areas.geometry.array);matched=set();changed=0;tol=1e-8
    for geom in out.geometry:
        match=next((int(i) for i in area_tree.query(geom.buffer(tol)) if i not in matched and
                    (geom.equals(areas.geometry.iloc[i]) or
                     (geom.hausdorff_distance(areas.geometry.iloc[i])<=tol and geom.symmetric_difference(areas.geometry.iloc[i]).area<=tol*max(1,geom.length)))),None)
        if match is None:changed+=1
        else:matched.add(match)
    check(r,'count_regions',changed==0 and len(matched)==len(areas),'计数结果改变、重复或丢失了输入区域。',evidence={'unmatched_regions':changed,'matched_regions':len(matched)})
    check(r,'count_field',field in out.columns,'计数字段不存在。',evidence={'field':field})
    if field not in out:return
    # Independent vectorized predicates instead of the execution tool's spatial-index query.
    n=min(len(out),max(1,MAX_PAIRS//max(1,len(points))))
    indices=np.unique(np.linspace(0,max(0,len(out)-1),n,dtype=int)) if n else []
    import shapely
    mismatches=[];counts=[]
    for i in indices:
        g=out.geometry.iloc[i]
        expected=int(np.count_nonzero(getattr(shapely,ctx.boundary)(g,points.geometry.array)))
        actual=out.iloc[i][field];counts.append(expected)
        if not isinstance(actual,(int,float,np.number)) or not math.isfinite(float(actual)) or actual!=expected:
            mismatches.append({'row':int(i),'expected':expected,'actual':str(actual)})
    check(r,'independent_point_count',not mismatches,'独立空间谓词复算与输出计数不一致。',
          evidence={'predicate':ctx.boundary,'regions_checked':len(indices),'regions_total':len(out),'mismatches':mismatches[:10],'overlap':'per_region'})
    if n<len(out):incomplete(r,f'计数核验抽查 {n}/{len(out)} 个区域，未逐区域全量核验。')
    if len(points)*max(1,len(areas))<=MAX_PAIRS:
        unique=int(np.count_nonzero(getattr(shapely,ctx.boundary)(unary_union(areas.geometry),points.geometry.array)))
        r['metrics']={'unique_points_in_union':unique,'per_region_sum':sum(counts),'sum_is_unique_total':False}


def validate_buffer(store,source,output,distance,r,op):
    src=vectors(store,source);out=vectors(store,output)
    if op not in ('buffer','buffer_points') or not src.geom_type.eq('Point').all():
        incomplete(r,'距离独立抽查目前覆盖点缓冲；线/面缓冲、简化未作边界距离证明。');return
    if len(src)!=len(out):
        incomplete(r,'融合缓冲区无法逐点配对，本版未执行独立距离核验。');return
    indices=np.unique(np.linspace(0,len(src)-1,min(len(src),50),dtype=int)) if len(src) else []
    max_error=0.;checked=0
    from pyproj import Geod
    geod=Geod(ellps='WGS84')
    # Native projected buffers are checked in their own metric, not compared to a different projection.
    use_geodesic=op=='buffer_points'
    target=4326 if use_geodesic else out.crs
    a=src.to_crs(target);b=out.to_crs(target)
    if not use_geodesic and not CRS(target).is_projected:
        incomplete(r,'角度缓冲未作米制距离核验。');return
    for i in indices:
        geom=b.geometry.iloc[i]
        if geom.geom_type!='Polygon':continue
        coords=np.asarray(geom.exterior.coords);p=a.geometry.iloc[i]
        errors=[abs((geod.inv(p.x,p.y,x,y)[2] if use_geodesic else math.hypot(x-p.x,y-p.y))-abs(distance)) for x,y in coords]
        max_error=max(max_error,max(errors,default=0));checked+=1
    tolerance=max(.05,abs(distance)*1e-5)
    check(r,'buffer_distance',checked>0 and max_error<=tolerance,'点缓冲边界顶点距离与请求半径不一致。',
          evidence={'checked':checked,'total':len(src),'max_vertex_error':max_error,'tolerance':tolerance,'metric':'ellipsoid_m' if use_geodesic else CRS(target).axis_info[0].unit_name})
    if checked<len(src):incomplete(r,f'点缓冲仅核验 {checked}/{len(src)} 个要素。')
    r['unverified'].append('仅检验边界顶点；曲线由多边形近似，未证明任意边界点误差。')


def validate_raster_math(store,inputs,output,args,ctx,r):
    import rasterio
    from contextlib import ExitStack
    with ExitStack() as stack:
        sources=[stack.enter_context(rasterio.open(raster_path(store,id))) for id in inputs.values()]
        dst=stack.enter_context(rasterio.open(raster_path(store,output)));base=sources[0]
        same=all(x.crs==dst.crs and x.shape==dst.shape and x.transform.almost_equals(dst.transform,precision=1e-9) for x in sources)
        check(r,'output_grid',same,'逐像元运算改变了输入网格，无法按原像元核验。')
        if not same:return
        if dst.width*dst.height>16000000:
            incomplete(r,'栅格超过 1600 万像元核验预算；需要分块任务。');return
        import re
        bands=[]
        for key,src in zip(inputs,sources):
            if key.startswith('INPUT_'):selected=[int(args.get('BAND_'+key[-1],1))]
            elif 'expression' in args:selected=sorted({int(n) for n in re.findall(r'\bb(\d+)\b',args['expression'])})
            elif 'red_band' in args:selected=[int(args['red_band']),int(args['nir_band'])]
            else:
                selected=list(range(1,src.count+1));r['unverified'].append('未解析该表达式的波段依赖，NoData 按全部输入波段保守检查。')
            bands.append(selected or [1])
        invalid_leaks=0;nonfinite=0;total=0
        for _,window in dst.block_windows(1):
            masks=[]
            for src,selected in zip(sources,bands):masks.append(np.logical_and.reduce(src.read_masks(indexes=selected,window=window)>0,axis=0))
            valid=np.logical_and.reduce(masks);actual=dst.read(1,window=window,masked=True)
            out_valid=~np.ma.getmaskarray(actual)
            invalid_leaks+=int(np.count_nonzero(~valid & out_valid))
            nonfinite+=int(np.count_nonzero(out_valid & ~np.isfinite(actual.data)));total+=actual.size
        check(r,'raster_finite',nonfinite==0,'输出有效像元中出现 NaN/Infinity。',evidence={'invalid_values':nonfinite,'pixels_checked':total})
        if ctx.nodata=='propagate':check(r,'nodata_propagation',invalid_leaks==0,'输入 NoData 被当作有效值传播到了输出。',evidence={'leaked_pixels':invalid_leaks})
        r['unverified'].append('未证明任意栅格表达式的科学含义。')


def validate_route(store,network,output,args,ctx,r):
    """Rebuild a directed graph with SciPy; compare route continuity, direction and cost.

    Scope: pre-noded linear networks, exact vertices, no turn restrictions. Endpoints
    inserted mid-edge by QGIS are deliberately marked unverified, never snapped silently.
    """
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import dijkstra
    net=vectors(store,network);out=vectors(store,output,net.crs)
    if float(args.get('TOLERANCE',0))!=0:
        incomplete(r,'非零拓扑容差的路网需专用核验；未独立复现吸附。');return
    fastest=int(args.get('STRATEGY',0))==1
    nodes={};edges={};speed_field=args.get('SPEED_FIELD');direction_field=args.get('DIRECTION_FIELD')
    def key(p):return (round(float(p[0]),7),round(float(p[1]),7))
    def index(p):
        p=key(p)
        if p not in nodes:nodes[p]=len(nodes)
        return nodes[p]
    invalid_speed=0
    for _,row in net.iterrows():
        speed=float(row[speed_field]) if speed_field else float(args.get('DEFAULT_SPEED',50))
        if fastest and (not math.isfinite(speed) or speed<=0):invalid_speed+=1;continue
        direction=int(args.get('DEFAULT_DIRECTION',2))
        if direction_field:
            v=str(row[direction_field]);mapping={str(args.get('VALUE_FORWARD','')):0,str(args.get('VALUE_BACKWARD','')):1,str(args.get('VALUE_BOTH','')):2}
            direction=mapping.get(v,direction)
        parts=list(row.geometry.geoms) if row.geometry.geom_type=='MultiLineString' else [row.geometry]
        for part in parts:
            coords=list(part.coords)
            for a,b in zip(coords,coords[1:]):
                u,v=index(a),index(b);length=math.dist(a[:2],b[:2]);cost=length/(speed*1000) if fastest else length
                for start,end in ([(u,v)] if direction==0 else [(v,u)] if direction==1 else [(u,v),(v,u)]):
                    edges[(start,end)]=min(edges.get((start,end),float('inf')),cost)
                if len(edges)>500000:
                    incomplete(r,'图超过 50 万有向边核验预算。');return
    check(r,'network_positive_cost',invalid_speed==0,'速度字段包含无效或非正值。',evidence={'invalid_edges':invalid_speed})
    if not edges or len(edges)>500000:
        incomplete(r,'图为空或超过 50 万有向边核验预算。');return
    rows,cols=zip(*edges);graph=csr_matrix((list(edges.values()),(rows,cols)),shape=(len(nodes),len(nodes)))
    requested={}
    import re
    from pyproj import Transformer
    for name in ('START_POINT','END_POINT'):
        if not args.get(name):continue
        match=re.fullmatch(r'\s*([^,]+),\s*([^\[]+?)(?:\s*\[([^\]]+)\])?\s*',str(args[name]))
        if not match:
            incomplete(r,'未解析路线请求端点，无法核对请求与结果端点。');continue
        x,y=float(match[1]),float(match[2])
        if match[3]:x,y=Transformer.from_crs(match[3],net.crs,always_xy=True).transform(x,y)
        p=key((x,y))
        if p in nodes:requested[name]=p
        else:incomplete(r,'请求端点需要吸附；本版未独立证明吸附位置符合用户目标。')
    if args.get('START_POINTS') or args.get('END_POINTS'):
        incomplete(r,'多点路线的输入与输出端点逐条对应关系尚未核验。')
    failures=[];costs=[];unsupported=0
    if len(out)>20:incomplete(r,f'路线核验仅抽查前 20/{len(out)} 条。')
    for i,row in out.head(20).iterrows():
        if row.geometry.geom_type!='LineString':unsupported+=1;continue
        points=[key(p) for p in row.geometry.coords]
        if not points:
            failures.append({'row':str(i),'reason':'路径为空'});continue
        if (requested.get('START_POINT',points[0])!=points[0] or requested.get('END_POINT',points[-1])!=points[-1]):
            failures.append({'row':str(i),'reason':'结果起终点与请求的路网端点不一致'})
        if any(p not in nodes for p in points):unsupported+=1;continue
        route=[nodes[p] for p in points];pairs=list(zip(route,route[1:]));missing=[p for p in pairs if p not in edges]
        if missing:failures.append({'row':str(i),'reason':'路径中存在不连通或逆行边'});continue
        cost=sum(edges[p] for p in pairs);best=float(dijkstra(graph,directed=True,indices=route[0])[route[-1]])
        tolerance=max(1e-6,abs(best)*.01)
        if not math.isfinite(best) or abs(cost-best)>tolerance:failures.append({'row':str(i),'reason':'路径不是此成本定义下的最短路径','cost':cost,'shortest':best})
        if 'cost' in out and (not math.isfinite(float(row['cost'])) or abs(float(row['cost'])-cost)>max(1e-6,abs(cost)*.01)):failures.append({'row':str(i),'reason':'输出成本与独立复算不一致'})
        costs.append(cost)
    if costs or failures:check(r,'route_connectivity_cost',not failures,'路线连通性、方向或成本复算未通过。',evidence={'cost_unit':'h' if fastest else 'm','routes_checked':len(costs),'failures':failures[:10],'costs':costs[:20],'distance_model':'projected_planar','relative_tolerance':.01})
    if unsupported:incomplete(r,f'{unsupported} 条路线含边中吸附点或复杂几何，未作图最短路证明。')
    r['unverified'].append('仅验证预先打断的顶点路网；不包含转向限制或真实道路通行事实。')


def validate_spatial(store,algorithm_id,args,data,preflight):
    args=preflight.get('arguments',args)
    r=report('独立领域核验');ctx=SpatialContext.model_validate(preflight['context']);bound=preflight['inputs'];op=algorithm_id.split(':')[-1];f=family(algorithm_id)
    output=data.get('layer_id')
    if not output:
        candidates=[x['layer_id'] for x in data.get('layers',[]) if x.get('layer_id')]
        output=next((id for id in candidates if store.get_layer(id).get('kind')!='raster' and 'LineString' in store.get_layer(id).get('geometry_types',[])),None)
    r.update(algorithm_id=algorithm_id,input_hashes=preflight['input_hashes'],context=preflight['context'],coverage='complete_within_scope')
    if not output:
        incomplete(r,'没有可按本契约核验的空间输出。')
        if ctx.verification=='strict':check(r,'strict_coverage',False,'严格验收缺少可核验的空间输出。')
        return r
    r['output_layer_id']=output
    a=bound.get('INPUT') or bound.get('POLYGONS') or bound.get('layer_id');b=bound.get('OVERLAY') or bound.get('POINTS') or bound.get('other_id')
    try:
        if f=='overlay' and a and b:validate_overlay(store,op,a,b,output,r)
        elif f=='count' and a and b:validate_counts(store,a,b,output,args,ctx,r)
        elif f=='distance' and a:validate_buffer(store,a,output,float(args.get('DISTANCE',args.get('distance_m',0))),r,op)
        elif f=='raster_math':validate_raster_math(store,{key:id for key,id in bound.items() if store.get_layer(id).get('kind')=='raster'},output,args,ctx,r)
        elif f=='network' and op.startswith('shortestpath') and a:validate_route(store,a,output,args,ctx,r)
        else:incomplete(r,'本算法尚无适用的独立领域核验器；仅完成通用数据校验。')
    except Exception as exc:
        # Failure to run a checker must not masquerade as successful validation.
        check(r,'validator_execution',False,'独立核验未能完成：'+str(exc))
    from .memory import Memory
    memory=Memory(store)
    for id,expected in preflight['input_hashes'].items():check(r,'input_version',memory.fingerprint(id)[0]==expected,'执行或核验期间输入文件发生了变化。',evidence={'layer_id':id})
    r['output_hash']=memory.fingerprint(output)[0]
    if ctx.verification=='strict' and (r['coverage']=='partial' or not any(x['code']!='input_version' for x in r['checks'])):
        check(r,'strict_coverage',False,'严格验收要求的领域核验未完整覆盖，请缩小任务或补充专用核验器。')
    return r
