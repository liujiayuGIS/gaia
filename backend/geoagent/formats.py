"""GDAL vector/raster ingress, asset inbox, immutable artifacts and real exports."""
from __future__ import annotations
import hashlib
import io
import json
import shutil
import uuid
import zipfile
from pathlib import Path
import geopandas as gpd
import numpy as np
import pyogrio
import rasterio
from PIL import Image
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from .store import now
from .gis import import_bytes

VECTOR_SUFFIXES={'.geojson','.json','.csv','.gpkg','.shp','.kml','.gml','.fgb','.parquet','.geojsonl','.dxf','.gpx','.tab','.mif'}
RASTER_SUFFIXES={'.tif','.tiff','.img','.asc','.jp2','.png','.jpg','.jpeg','.bil','.dem','.grd'}
PICTURE_SUFFIXES={'.svg'}
MAX_UPLOAD=250*1024*1024


def format_catalog():
    drivers=pyogrio.list_drivers()
    with rasterio.Env() as env:
        raster_drivers=dict(env.drivers())
    return {'vector':drivers,'raster':raster_drivers,'vector_upload':sorted(VECTOR_SUFFIXES),
            'raster_upload':sorted(RASTER_SUFFIXES),'containers':['.zip (Shapefile / FileGDB / multipart datasets)'],
            'limits':{'upload_mb':250,'vector_features':100000,'raster_analysis_pixels':16000000},
            'qgis_process_available':bool(shutil.which('qgis_process'))}


def stage_files(store, files):
    asset_id=uuid.uuid4().hex
    folder=store.root/'inbox'/asset_id
    folder.mkdir(parents=True)
    total=0
    for name,content in files:
        name=Path(name.replace('\\','/')).name
        if not name or name in ('.','..'):
            raise ValueError('无效文件名。')
        total+=len(content)
        if total>MAX_UPLOAD:
            raise ValueError('本次上传超过 250 MB。')
        (folder/name).write_bytes(content)
    for path in [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ('.zip','.kmz')]:
        with zipfile.ZipFile(path) as z:
            if len(z.infolist())>2000 or sum(x.file_size for x in z.infolist())>MAX_UPLOAD:
                raise ValueError('压缩包解压后超过文件数量或 250 MB 限制。')
            for item in z.infolist():
                dest=(folder/item.filename).resolve()
                if not dest.is_relative_to(folder.resolve()) or (item.external_attr>>16)&0o170000==0o120000:
                    raise ValueError('压缩包含不安全路径或符号链接。')
            z.extractall(folder)
    candidates=[]
    gdbs=[x for x in folder.rglob('*') if x.is_dir() and x.suffix.lower()=='.gdb']
    candidates.extend(gdbs)
    for path in folder.rglob('*'):
        if path.is_file() and not path.name.startswith('._') and '__MACOSX' not in path.parts and path.suffix.lower() in VECTOR_SUFFIXES|RASTER_SUFFIXES|PICTURE_SUFFIXES and not any(x in path.parents for x in gdbs):
            if path.suffix.lower()=='.json':
                try:
                    if json.loads(path.read_text(encoding='utf-8-sig')).get('type')!='FeatureCollection':continue
                except (ValueError,AttributeError):continue
            candidates.append(path)
    resources=[]
    for p in candidates:
        relative=str(p.relative_to(folder))
        kind='picture' if p.suffix.lower() in PICTURE_SUFFIXES else 'raster' if p.suffix.lower() in RASTER_SUFFIXES else 'vector'
        info={'path':relative,'kind':kind}
        try:
            if kind=='raster':
                with rasterio.open(p) as src:
                    info.update(crs=str(src.crs) if src.crs else None,width=src.width,height=src.height,bands=src.count)
            elif kind=='vector' and p.suffix.lower() not in ('.json','.csv','.parquet','.geojsonl'):
                info['sublayers']=[str(x[0]) for x in pyogrio.list_layers(p)]
        except Exception:
            info['note']='需在导入时检查坐标系及驱动。'
        resources.append(info)
    asset={'id':asset_id,'name':', '.join(Path(n).name for n,_ in files)[:180],'created_at':now(),'bytes':total,'resources':resources,'status':'pending'}
    store.put_object('assets',asset_id,asset)
    if not resources:
        raise ValueError('没有发现可导入的数据。SHP 请连同 .shx/.dbf/.prj 上传，或打包为 ZIP。')
    return asset


def import_asset(store, asset_id, resource=None, source_crs=None, sublayer=None, run_id=None):
    asset=store.object('assets',asset_id)
    choices=asset['resources']
    if resource:
        choices=[x for x in choices if x['path']==resource]
    if len(choices)!=1:
        raise ValueError('资源不唯一，请指定 resource：'+', '.join(x['path'] for x in asset['resources']))
    item=choices[0]
    path=store.root/'inbox'/asset_id/item['path']
    prov={'run_id':run_id,'asset_id':asset_id,'resource':item['path'],'sublayer':sublayer}
    if item['kind']=='picture':raise ValueError('图片资源请通过布局插入。')
    if item['kind']=='raster':
        with rasterio.open(path) as src:
            if not src.crs and not source_crs:
                raise ValueError('栅格缺少坐标系，请明确提供 source_crs。')
            if source_crs and str(src.crs)!=source_crs:
                # Explicitly declared CRS only when missing; never silently relabel known data.
                if src.crs:
                    from pyproj import CRS
                    if CRS(src.crs)!=CRS(source_crs):
                        raise ValueError('栅格已声明其他坐标系，请先按原坐标系导入，再重投影。')
                else:
                    assigned=path.with_name(path.stem+'-assigned.tif')
                    profile=src.profile.copy();profile.update(driver='GTiff',crs=source_crs)
                    with rasterio.open(assigned,'w',**profile) as dst:
                        dst.write(src.read())
                    path=assigned
        meta=store.add_raster(path.stem,path,prov)
    else:
        ext=path.suffix.lower()
        if ext in ('.csv','.json','.geojson'):
            data=import_bytes(path.name,path.read_bytes(),source_crs or 'EPSG:4326')
            meta=store.add_layer(path.stem,data,provenance={**prov,'source_crs':source_crs or 'EPSG:4326','native_crs':source_crs or 'EPSG:4326'})
        else:
            if ext=='.shp' and not any(p.name.lower()==path.stem.lower()+'.dbf' for p in path.parent.iterdir()):
                raise ValueError('Shapefile 缺少 .dbf 属性文件，请连同配套文件重新上传。')
            options={}
            if sublayer:
                options['layer']=sublayer
            elif len(item.get('sublayers',[]))>1:
                raise ValueError('此数据包含多个图层，请指定 sublayer：'+', '.join(item['sublayers']))
            frame=gpd.read_parquet(path) if ext=='.parquet' else gpd.read_file(path,engine='pyogrio',**options)
            if len(frame)>100000:
                raise ValueError('本版单图层最多支持 100,000 个要素。')
            if frame.crs is None:
                if not source_crs:
                    raise ValueError('文件缺少坐标系，请在 source_crs 中明确指定 EPSG 编码。')
                frame=frame.set_crs(source_crs)
            elif source_crs:
                from pyproj import CRS
                if CRS(frame.crs)!=CRS(source_crs):
                    raise ValueError('文件原有坐标系与声明不一致，请按原坐标系导入。')
            meta=add_frame(store,path.stem,frame,prov,source='upload')
    asset['status']='imported';asset['layer_id']=meta['id'];store.put_object('assets',asset_id,asset)
    return meta


def add_frame(store, name, frame, provenance, source='analysis',style=None):
    if source=='upload' and (frame.geometry.isna() | frame.geometry.is_empty).any():
        raise ValueError('输入包含空几何，请先清理数据，避免静默丢失记录。')
    frame=frame[frame.geometry.notna() & ~frame.geometry.is_empty].copy()
    if len(frame)>100000:
        raise ValueError('结果超出 100,000 个要素限制。')
    if frame.crs is None:
        raise ValueError('计算结果缺少坐标系。')
    if len(frame) and not frame.geometry.is_valid.all():
        raise ValueError('结果含无效几何，未发布。请先修复输入几何。')
    native=str(frame.crs)
    display=frame.to_crs(4326)
    if len(display):
        b=display.total_bounds
        if not np.isfinite(b).all() or b[0]<-180 or b[2]>180 or b[1]<-85 or b[3]>85:
            raise ValueError('坐标超出 WGS84 地图范围，请检查输入坐标系。')
        if display.geometry.has_z.any():raise ValueError('当前二维地图不支持三维几何，请先转为二维数据。')
    data=json.loads(display.to_json(drop_id=True,na='null'))
    native_temp=None
    if len(frame) and native not in ('EPSG:4326','epsg:4326'):
        native_temp=store.root/'layers'/f'native-{uuid.uuid4().hex}.gpkg'
        frame.to_file(native_temp,driver='GPKG',engine='pyogrio')
    meta=store.add_layer(name,data,source=source,provenance={**provenance,'native_crs':native,
             'validation':{'geometry_valid':True,'feature_count':len(frame),'crs_known':True}},style=style)
    if native_temp:
        target=store.root/'layers'/f"{meta['id']}.gpkg"
        native_temp.replace(target)
    return meta


def frame(store, layer_id):
    meta=store.get_layer(layer_id)
    if meta.get('kind')=='raster':
        raise ValueError('此算法需要矢量图层。')
    data=store.data(layer_id)
    if not data['features']:
        return gpd.GeoDataFrame(geometry=[],crs=4326)
    return gpd.GeoDataFrame.from_features(data['features'],crs=4326)


def register_raster(store,name,path,provenance):
    raster_id=uuid.uuid4().hex
    target=store.root/'layers'/f'{raster_id}.tif'
    with rasterio.open(path) as src:
        if not src.crs:
            raise ValueError('栅格缺少坐标系。')
        if src.transform.is_identity:
            raise ValueError('栅格没有有效地理参考，请提供地理配准后的 TIFF 或配套世界文件。')
        if src.width*src.height>100000000:
            raise ValueError('栅格超过 1 亿像元的导入上限。')
        profile=src.profile.copy();profile.update(driver='GTiff',compress='deflate')
        with rasterio.open(target,'w',**profile) as dst:
            for _,window in src.block_windows(1):
                dst.write(src.read(window=window),window=window)
            dst.colorinterp=src.colorinterp
        bounds=list(transform_bounds(src.crs,4326,*src.bounds,densify_pts=21))
        if not all(np.isfinite(bounds)) or bounds[0]<-180 or bounds[2]>180 or bounds[1]<-85 or bounds[3]>85:
            target.unlink(missing_ok=True)
            raise ValueError('栅格范围超出当前二维地图支持范围，请检查坐标系或先裁剪。')
        stats=[]
        for b in range(1,src.count+1):
            arr=src.read(b,out_shape=(min(src.height,512),min(src.width,512)),masked=True)
            values=arr.compressed();values=values[np.isfinite(values)]
            stats.append({'band':b,'sampled':True,'min':float(values.min()) if values.size else None,'max':float(values.max()) if values.size else None,'mean':float(values.mean()) if values.size else None})
        meta={'id':raster_id,'kind':'raster','name':name[:100],'count':src.width*src.height,'bounds':bounds,
              'fields':[],'geometry_types':['Raster'],'crs':str(src.crs),'source':'analysis' if provenance.get('run_id') else 'upload',
              'colorinterp':[c.name for c in src.colorinterp],'width':src.width,'height':src.height,'bands':src.count,'dtype':src.dtypes[0],'nodata':src.nodata if src.nodata is None or np.isfinite(src.nodata) else None,'statistics':stats,
              'created_at':now(),'provenance':provenance,'style':{'color':'#3c83b7','visible':True,'opacity':.85},
              'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    with store.db() as db:
        db.execute('INSERT INTO layers VALUES(?,?)',(raster_id,json.dumps(meta,ensure_ascii=False,allow_nan=False)))
    return meta


def raster_path(store,layer_id):
    if store.get_layer(layer_id).get('kind')!='raster':
        raise ValueError('需要栅格图层。')
    return store.root/'layers'/f'{layer_id}.tif'


def raster_preview(store,layer_id,max_size=1200):
    with rasterio.open(raster_path(store,layer_id)) as src, WarpedVRT(src,crs='EPSG:3857') as vrt:
        ratio=min(1,max_size/max(vrt.width,vrt.height));h=max(1,int(vrt.height*ratio));w=max(1,int(vrt.width*ratio))
        arr=vrt.read(1,out_shape=(h,w),masked=True).astype('float32')
        v=arr.compressed();v=v[np.isfinite(v)]
        lo,hi=np.percentile(v,[2,98]) if v.size else (0,1)
        scaled=np.clip((arr.filled(lo)-lo)/max(hi-lo,1e-12),0,1)
        from matplotlib.colors import LinearSegmentedColormap
        color=store.get_layer(layer_id)['style'].get('color','#3c83b7')
        cmap=LinearSegmentedColormap.from_list('raster',['#f0f6fa',color])
        rgba=(cmap(scaled)*255).astype('uint8');rgba[:,:,3]=np.where(np.ma.getmaskarray(arr),0,255)
        color_names=[x.name for x in src.colorinterp]
        if all(x in color_names for x in ('red','green','blue')):
            rgb=vrt.read([color_names.index(x)+1 for x in ('red','green','blue')],out_shape=(3,h,w),masked=True).astype('float32')
            for i,band in enumerate(rgb):
                valid=band.compressed();valid=valid[np.isfinite(valid)]
                low,high=(0,255) if src.dtypes[0]=='uint8' else np.percentile(valid,[2,98]) if valid.size else (0,1)
                if high==low:low,high=0,max(float(high),1)
                rgba[:,:,i]=(np.clip((band.filled(low)-low)/max(high-low,1e-12),0,1)*255).astype('uint8')

        buf=io.BytesIO();Image.fromarray(rgba).save(buf,format='PNG');return buf.getvalue()


def export_vector(store,layer_id,fmt,target_crs=None):
    formats={'gpkg':('GPKG','.gpkg'),'shp':('ESRI Shapefile','.shp'),'kml':('KML','.kml'),'gml':('GML','.gml'),'fgb':('FlatGeobuf','.fgb'),'parquet':(None,'.parquet'),'dxf':('DXF','.dxf')}
    if fmt not in formats:
        raise ValueError('不支持该矢量导出格式。')
    gdf=frame(store,layer_id)
    native=store.root/'layers'/f'{layer_id}.gpkg'
    if fmt=='gpkg' and not target_crs and native.exists():return native
    target_crs=target_crs or store.get_layer(layer_id).get('provenance',{}).get('native_crs')
    if target_crs:
        gdf=gdf.to_crs(target_crs)
    driver,ext=formats[fmt]
    if driver and 'w' not in pyogrio.list_drivers().get(driver,''):
        raise ValueError(f'当前 GDAL 不支持写入 {driver}。')
    folder=store.root/'exports'/uuid.uuid4().hex;folder.mkdir(parents=True)
    path=folder/('result'+ext)
    if fmt=='parquet':
        gdf.to_parquet(path)
    else:
        gdf.to_file(path,driver=driver,engine='pyogrio',encoding='UTF-8')
    if fmt=='shp':
        written=pyogrio.read_info(path)['fields'].tolist()
        original=[x for x in gdf.columns if x!=gdf.geometry.name]
        (folder/'field-map.json').write_text(json.dumps(dict(zip(original,written)),ensure_ascii=False,indent=2))
    if fmt in ('shp','gml'):
        zipped=folder/'result.zip'
        with zipfile.ZipFile(zipped,'w',zipfile.ZIP_DEFLATED) as z:
            for p in folder.iterdir():
                if p!=zipped:
                    z.write(p,p.name)
        return zipped
    return path
