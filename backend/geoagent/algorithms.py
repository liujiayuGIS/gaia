"""Discoverable deterministic spatial algorithms with explicit contracts and provenance."""
from __future__ import annotations
import ast
import math
import uuid
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio import features
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform,reproject,Resampling
from shapely import make_valid
from shapely.geometry import box,shape,mapping
from shapely.ops import unary_union
from scipy.spatial import cKDTree
from .formats import frame,add_frame,raster_path

CATALOG=[]

def spec(id,name,category,description,params=None):
    base={'layer_id':{'type':'layer','required':True,'label':'输入图层'}}
    base.update(params or {})
    CATALOG.append({'id':id,'name':name,'category':category,'description':description,'parameters':base,'output':'new_layer','status':'available'})

NUM=lambda label,default:dict(type='number',label=label,default=default)
STR=lambda label,default='':dict(type='string',label=label,default=default)
OTHER={'other_id':{'type':'layer','required':True,'label':'叠加图层'}}
spec('buffer','缓冲区','矢量','在适用的局部投影中按米生成点、线或面的缓冲区。',{'distance_m':NUM('距离（米）',800)})
for id,name in [('clip','裁剪'),('intersection','相交'),('union','联合'),('difference','擦除'),('symmetric_difference','对称差')]:
    spec(id,name,'叠加','按两个图层的几何关系生成新的要素。',OTHER)
for id,name in [('centroid','质心'),('point_on_surface','面内点'),('convex_hull','凸包'),('envelope','包络'),('explode','多部件转单部件'),('boundary','边界转线'),('repair','修复几何'),('measure','计算面积与长度')]:
    spec(id,name,'几何','保留输入，生成新的几何或带面积、长度属性的图层。')
spec('dissolve','融合','矢量','按字段融合；字段留空时全部融合。',{'field':STR('融合字段（可空）')})
spec('simplify','简化','几何','以米为容差简化几何，保留拓扑。',{'tolerance_m':NUM('容差（米）',20)})
spec('filter','属性筛选','属性','按字段与比较条件生成新的数据子集。',{'field':STR('字段'),'operator':STR('运算符（eq/ne/gt/ge/lt/le/contains）','eq'),'value':STR('比较值')})
spec('calculate_field','字段计算','属性','使用 value 代表输入字段，支持安全算术表达式，生成新字段。',{'field':STR('输入数值字段'),'expression':STR('表达式','value * 2'),'output_field':STR('输出字段','calculated')})
spec('spatial_join','空间连接','叠加','以 intersects 关系附加另一图层属性；可能生成多行。',OTHER)
spec('nearest','最近邻距离','距离','在局部投影中计算到最近要素的距离（米）。',OTHER)
spec('count_points','面内点统计','统计','为每个面添加 poi_count；包含边界，重叠范围分别计数。',OTHER)
spec('grid','创建鱼网','矢量','按米生成研究范围内的规则方格网。',{'cell_size_m':NUM('网格边长（米）',500)})
spec('reproject','重投影','坐标','生成目标坐标系的 GeoPackage 原生数据，同时保持 WGS84 显示副本。',{'target_crs':STR('目标坐标系','EPSG:3857')})
spec('dbscan','密度聚类','统计','对点做 DBSCAN 密度聚类，cluster=-1 表示噪声。',{'distance_m':NUM('邻域半径（米）',500),'min_points':NUM('最少点数',3)})
spec('idw','反距离权重插值','插值','根据点数值字段生成 IDW 栅格；最多邻近 8 点。',{'field':STR('数值字段'),'cell_size_m':NUM('像元尺寸（米）',100)})
spec('heatmap','点密度热力栅格','插值','规则网格计数后高斯平滑；单位为每像元的平滑点数。',{'cell_size_m':NUM('像元尺寸（米）',100),'sigma':NUM('高斯标准差（像元）',2)})
spec('raster_calculator','栅格计算器','栅格','b1、b2 等表示波段；支持安全算术、sqrt、log、abs。',{'expression':STR('表达式','b1 * 2')})
spec('ndvi','NDVI','栅格','按指定红光、近红外波段计算归一化植被指数。',{'red_band':NUM('红光波段',1),'nir_band':NUM('近红外波段',2)})
spec('raster_clip','栅格掩膜裁剪','栅格','按矢量范围裁剪栅格，正确转换掩膜坐标系。',OTHER)
spec('raster_reproject','栅格重投影','栅格','用双线性重采样生成新的 GeoTIFF。',{'target_crs':STR('目标坐标系','EPSG:3857')})
for id,name in [('slope','坡度'),('aspect','坡向'),('hillshade','山体阴影')]:
    spec(id,name,'地形','需要以米为水平单位的投影 DEM；高程单位必须为米。')
spec('polygonize','栅格转面','栅格','将整数分类栅格转换为面要素。')
spec('zonal_statistics','分区统计','统计','对多边形内栅格有效像元计算 count、mean、min、max。',OTHER)


def get_spec(algorithm_id):
    if ':' in algorithm_id:
        from .plugins.qgis_plugin import QGISPlugin
        if algorithm_id.startswith('qgis:'):
            return next((x for x in QGISPlugin().algorithms() if x['id']==algorithm_id),None) or (_ for _ in ()).throw(ValueError('插件算法不存在。'))
        if algorithm_id.startswith('python:'):return get_spec(algorithm_id.split(':',1)[1])
    for item in CATALOG:
        if item['id']==algorithm_id:
            return item
    raise ValueError('算法不存在，请先检索算法目录。')


def validate_args(algorithm_id,arguments):
    if ':' in algorithm_id:
        spec=get_spec(algorithm_id)
        unknown=set(arguments)-set(spec['parameters'])
        if unknown:raise ValueError('未知参数：'+', '.join(unknown))
        return arguments
    definition=get_spec(algorithm_id)
    unknown=set(arguments)-set(definition['parameters'])
    if unknown:
        raise ValueError('未知参数：'+', '.join(sorted(unknown)))
    args=dict(arguments)
    for key,p in definition['parameters'].items():
        if key not in args:
            if p.get('required'):
                raise ValueError(f'缺少参数 {key}。')
            args[key]=p.get('default')
        if p['type']=='number':
            try: args[key]=float(args[key])
            except (ValueError,TypeError): raise ValueError(f'{key} 必须是数值。') from None
            if not math.isfinite(args[key]) or args[key]<=0:
                raise ValueError(f'{key} 必须是有限正数。')
        elif not isinstance(args[key],str):
            raise ValueError(f'{key} 必须是字符串。')
    return args


def metric(gdf):
    if gdf.empty:
        raise ValueError('输入图层为空。')
    w=gdf.to_crs(4326).total_bounds
    if w[2]-w[0]>6 or w[3]-w[1]>6 or max(abs(w[1]),abs(w[3]))>80:
        raise ValueError('本算法使用局部投影，要求城市尺度范围（经纬跨度 ≤6°、纬度 ±80°）。请先裁剪。')
    return gdf.to_crs(gdf.estimate_utm_crs())


def evaluate(expression,names):
    """Tiny arithmetic interpreter. No Python eval, attribute access, indexing or imports."""
    if len(expression)>300:
        raise ValueError('表达式过长。')
    tree=ast.parse(expression,mode='eval')
    binary={ast.Add:np.add,ast.Sub:np.subtract,ast.Mult:np.multiply,ast.Div:np.divide,ast.Pow:np.power}
    funcs={'sqrt':np.sqrt,'log':np.log,'abs':np.abs}
    def visit(node):
        if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)) and math.isfinite(node.value):return node.value
        if isinstance(node,ast.Name) and node.id in names:return names[node.id]
        if isinstance(node,ast.BinOp) and type(node.op) in binary:return binary[type(node.op)](visit(node.left),visit(node.right))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd)):return -visit(node.operand) if isinstance(node.op,ast.USub) else visit(node.operand)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in funcs and len(node.args)==1 and not node.keywords:return funcs[node.func.id](visit(node.args[0]))
        raise ValueError('表达式只支持数值、波段/字段名称和安全算术函数。')
    with np.errstate(all='ignore'):
        return visit(tree.body)


def provenance(store,args,run_id,algorithm_id):
    inputs=[value for key,value in args.items() if key.endswith('_id')]
    return {'run_id':run_id,'tool':'run_algorithm','algorithm':algorithm_id,'parameters':args,'inputs':inputs,
            'input_sha256':[store.get_layer(x)['sha256'] for x in inputs]}


def run_algorithm(store,algorithm_id,arguments,run_id):
    if ':' in algorithm_id:
        from .plugins import PluginManager
        return PluginManager(store).execute(algorithm_id,arguments,run_id,__import__('threading').Event())
    a=validate_args(algorithm_id,arguments);definition=get_spec(algorithm_id);prov=provenance(store,a,run_id,algorithm_id)
    meta=store.get_layer(a['layer_id']);name=meta['name']+' · '+definition['name']
    if meta.get('kind')=='raster' or algorithm_id=='zonal_statistics':
        return raster_algorithm(store,algorithm_id,a,run_id,prov,name)
    gdf=frame(store,a['layer_id']);other=frame(store,a['other_id']) if a.get('other_id') else None
    op=algorithm_id
    if op in ('buffer','simplify','nearest','grid','dbscan','idw','heatmap'):
        gdf=metric(gdf)
        if other is not None:other=other.to_crs(gdf.crs)
    if op=='buffer':gdf.geometry=gdf.geometry.buffer(a['distance_m'])
    elif op in ('clip','intersection','union','difference','symmetric_difference'):
        if op=='clip':gdf=gpd.clip(gdf,other)
        else:gdf=gpd.overlay(gdf,other,how=op,keep_geom_type=False)
    elif op in ('centroid','convex_hull','envelope','boundary'):
        if op=='centroid':gdf=metric(gdf)
        gdf.geometry=getattr(gdf.geometry,op)
    elif op=='point_on_surface':gdf.geometry=gdf.geometry.representative_point()
    elif op=='explode':gdf=gdf.explode(index_parts=False,ignore_index=True)
    elif op=='repair':gdf.geometry=gdf.geometry.map(make_valid)
    elif op=='measure':
        from pyproj import Geod
        geod=Geod(ellps='WGS84')
        gdf['area_m2']=[abs(geod.geometry_area_perimeter(g)[0]) if 'Polygon' in g.geom_type else 0.0 for g in gdf.geometry]
        gdf['length_m']=[geod.geometry_length(g) for g in gdf.geometry]
    elif op=='dissolve':
        if a['field'] and a['field'] not in gdf.columns:raise ValueError('融合字段不存在。')
        gdf=gdf.dissolve(by=a['field'] or None,as_index=False)
    elif op=='simplify':gdf.geometry=gdf.geometry.simplify(a['tolerance_m'],preserve_topology=True)
    elif op=='filter':
        if a['field'] not in gdf.columns:raise ValueError('筛选字段不存在。')
        col=gdf[a['field']];value=a['value']
        if pd.api.types.is_numeric_dtype(col):value=float(value)
        methods={'eq':lambda:col==value,'ne':lambda:col!=value,'gt':lambda:col>value,'ge':lambda:col>=value,'lt':lambda:col<value,'le':lambda:col<=value,'contains':lambda:col.astype(str).str.contains(str(value),regex=False,na=False)}
        if a['operator'] not in methods:raise ValueError('不支持此比较运算符。')
        gdf=gdf[methods[a['operator']]()].copy()
    elif op=='calculate_field':
        if a['field'] not in gdf.columns:raise ValueError('数值字段不存在。')
        if not a['output_field'] or a['output_field']=='geometry':raise ValueError('输出字段名无效。')
        values=evaluate(a['expression'],{'value':pd.to_numeric(gdf[a['field']]).to_numpy()})
        if not np.isfinite(values).all():raise ValueError('字段计算产生非有限值，请检查除零和缺失值。')
        gdf[a['output_field']]=values
    elif op=='spatial_join':gdf=gpd.sjoin(gdf,other,how='left',predicate='intersects').drop(columns='index_right',errors='ignore')
    elif op=='nearest':gdf=gpd.sjoin_nearest(gdf,other,how='left',distance_col='distance_m').drop(columns='index_right',errors='ignore')
    elif op=='count_points':
        if not gdf.geom_type.isin(['Polygon','MultiPolygon']).all() or not other.geom_type.eq('Point').all():raise ValueError('需要面输入和点叠加图层。')
        from shapely.strtree import STRtree
        tree=STRtree(other.geometry.to_list());gdf['poi_count']=[len(tree.query(g,predicate='covers')) for g in gdf.geometry]
    elif op=='grid':
        x0,y0,x1,y1=gdf.total_bounds;s=a['cell_size_m'];n=math.ceil((x1-x0)/s)*math.ceil((y1-y0)/s)
        if n>50000:raise ValueError('网格超过 50,000 个，请增大边长。')
        cells=[box(x,y,x+s,y+s) for x in np.arange(x0,x1,s) for y in np.arange(y0,y1,s)]
        gdf=gpd.GeoDataFrame({'cell_id':range(len(cells))},geometry=cells,crs=gdf.crs)
    elif op in ('idw','heatmap'):return interpolate(store,gdf,op,a,prov,name)
    elif op=='dbscan':
        if not gdf.geom_type.eq('Point').all() or len(gdf)>10000:raise ValueError('聚类需要最多 10,000 个点。')
        xy=np.column_stack([gdf.geometry.x,gdf.geometry.y]);tree=cKDTree(xy);labels=np.full(len(xy),-1);visited=set();cluster=0
        for i in range(len(xy)):
            if i in visited:continue
            visited.add(i);near=tree.query_ball_point(xy[i],a['distance_m'])
            if len(near)<int(a['min_points']):continue
            labels[i]=cluster;queue=list(near);queued=set(near)
            for j in queue:
                if j not in visited:
                    visited.add(j);neighbors=tree.query_ball_point(xy[j],a['distance_m'])
                    if len(neighbors)>=int(a['min_points']):
                        for k in neighbors:
                            if k not in queued:queue.append(k);queued.add(k)
                if labels[j]<0:labels[j]=cluster
            cluster+=1
        gdf['cluster']=labels
    elif op=='reproject':gdf=gdf.to_crs(a['target_crs'])
    else:raise ValueError('不支持此矢量算法。')
    result=add_frame(store,name,gdf,prov,style={'color':'#5b9bc7','visible':True,'field':'poi_count' if op=='count_points' else None,'opacity':.35})
    return {'layer_id':result['id'],'name':result['name'],'count':result['count'],'validation':result['provenance']['validation'],'method':definition['description']}


def write_raster(store,data,profile,name,prov):
    if data.ndim==2:data=data[np.newaxis,...]
    profile=profile.copy();profile.update(driver='GTiff',height=data.shape[1],width=data.shape[2],count=data.shape[0],dtype='float32',nodata=-9999,compress='deflate')
    path=store.root/'exports'/f'{uuid.uuid4().hex}.tif';path.parent.mkdir(exist_ok=True)
    arr=np.asarray(data,dtype='float32')
    if not np.isfinite(arr).any():raise ValueError('计算结果全部为无效值，未发布。请检查波段、表达式和输入 NoData。')
    arr=np.where(np.isfinite(arr),arr,-9999)
    with rasterio.open(path,'w',**profile) as dst:dst.write(arr)
    result=store.add_raster(name,path,{**prov,'validation':{'crs_known':True,'dimensions_positive':True,'nodata_preserved':True}})
    return {'layer_id':result['id'],'name':name,'count':result['count'],'width':result['width'],'height':result['height'],'validation':result['provenance']['validation']}


def interpolate(store,gdf,op,a,prov,name):
    if not gdf.geom_type.eq('Point').all():raise ValueError('插值需要点图层。')
    x0,y0,x1,y1=gdf.total_bounds;cell=a['cell_size_m'];width=max(1,math.ceil((x1-x0)/cell)+1);height=max(1,math.ceil((y1-y0)/cell)+1)
    if width*height>250000:raise ValueError('插值网格超过 250,000 像元，请增大像元尺寸。')
    xy=np.column_stack([gdf.geometry.x,gdf.geometry.y]);xx,yy=np.meshgrid(x0+(np.arange(width)+.5)*cell,y1-(np.arange(height)+.5)*cell)
    if op=='heatmap':
        from scipy.ndimage import gaussian_filter
        arr=np.zeros((height,width));ix=np.clip(((xy[:,0]-x0)/cell).astype(int),0,width-1);iy=np.clip(((y1-xy[:,1])/cell).astype(int),0,height-1);np.add.at(arr,(iy,ix),1);arr=gaussian_filter(arr,a['sigma'])
    else:
        values=pd.to_numeric(gdf[a['field']]).to_numpy();distance,indices=cKDTree(xy).query(np.column_stack([xx.ravel(),yy.ravel()]),k=min(8,len(xy)))
        if distance.ndim==1:distance=distance[:,None];indices=indices[:,None]
        weights=1/np.maximum(distance,1e-9)**2;arr=((values[indices]*weights).sum(axis=1)/weights.sum(axis=1)).reshape(height,width)
    return write_raster(store,arr,{'crs':gdf.crs,'transform':rasterio.transform.from_origin(x0,y1,cell,cell)},name,prov)


def raster_algorithm(store,op,a,run_id,prov,name):
    if op=='zonal_statistics':
        polygons=frame(store,a['layer_id']);raster_id=a['other_id']
        with rasterio.open(raster_path(store,raster_id)) as src:
            projected=polygons.to_crs(src.crs)
            rows=[]
            for g in projected.geometry:
                try:
                    arr,_=mask(src,[mapping(g)],crop=True,filled=False);v=arr[0].compressed();v=v[np.isfinite(v)]
                except ValueError:v=np.array([])
                rows.append({'pixel_count':len(v),'mean':float(v.mean()) if len(v) else None,'min':float(v.min()) if len(v) else None,'max':float(v.max()) if len(v) else None})
            for key in ('pixel_count','mean','min','max'):polygons[key]=[x[key] for x in rows]
        result=add_frame(store,name,polygons,prov);return {'layer_id':result['id'],'name':name,'count':len(polygons),'validation':result['provenance']['validation']}
    with rasterio.open(raster_path(store,a['layer_id'])) as src:
        if src.width*src.height>16000000:raise ValueError('本版单次栅格分析最多 1600 万像元。')
        profile=src.profile.copy();data=src.read(masked=True).astype('float32').filled(np.nan)
        if op=='raster_calculator':out=evaluate(a['expression'],{f'b{i+1}':x for i,x in enumerate(data)})
        elif op=='ndvi':
            red,nir=int(a['red_band']),int(a['nir_band'])
            if min(red,nir)<1 or max(red,nir)>src.count:raise ValueError('指定波段不在栅格波段范围内。')
            with np.errstate(all='ignore'):out=(data[nir-1]-data[red-1])/(data[nir-1]+data[red-1])
        elif op=='raster_clip':
            clip=frame(store,a['other_id']).to_crs(src.crs)
            clipped,transform=mask(src,[mapping(g) for g in clip.geometry],crop=True,filled=False);out=clipped.astype('float32').filled(np.nan);profile.update(transform=transform)
        elif op=='raster_reproject':
            target=a['target_crs'];transform,width,height=calculate_default_transform(src.crs,target,src.width,src.height,*src.bounds)
            if width*height>16000000:raise ValueError('目标栅格超出像元上限。')
            out=np.full((src.count,height,width),np.nan,dtype='float32')
            for i in range(src.count):reproject(data[i],out[i],src_transform=src.transform,src_crs=src.crs,dst_transform=transform,dst_crs=target,src_nodata=np.nan,dst_nodata=np.nan,resampling=Resampling.bilinear)
            profile.update(crs=target,transform=transform)
        elif op in ('slope','aspect','hillshade'):
            if not src.crs.is_projected or src.crs.linear_units not in ('metre','meter'):raise ValueError('地形分析需要水平单位为米的投影 DEM，请先重投影。')
            dy,dx=np.gradient(data[0],abs(src.transform.e),abs(src.transform.a));slope=np.arctan(np.hypot(dx,dy));aspect=np.arctan2(-dx,dy)
            out=np.degrees(slope) if op=='slope' else (np.degrees(aspect)+360)%360 if op=='aspect' else np.clip(np.cos(np.pi/4)*np.cos(slope)+np.sin(np.pi/4)*np.sin(slope)*np.cos(np.radians(315)-aspect),0,1)*255
        elif op=='polygonize':
            values=data[0]
            if not np.allclose(values[np.isfinite(values)],np.round(values[np.isfinite(values)])):raise ValueError('栅格转面仅支持整数分类值。')
            fs=[]
            for geom,value in features.shapes(np.nan_to_num(values,nan=-9999).astype('int32'),mask=np.isfinite(values),transform=src.transform):
                if len(fs)>=100000:raise ValueError('栅格转面结果超过要素上限。')
                fs.append({'geometry':shape(geom),'value':int(value)})
            result=add_frame(store,name,gpd.GeoDataFrame(fs,geometry='geometry',crs=src.crs),prov)
            return {'layer_id':result['id'],'name':name,'count':result['count'],'validation':result['provenance']['validation']}
        else:raise ValueError('此算法不支持栅格输入。')
        if np.isscalar(out):out=np.full((src.height,src.width),out)
        return write_raster(store,np.asarray(out),profile,name,prov)
