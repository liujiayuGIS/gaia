"""Synthetic, fixed-seed city-scale fixtures. Names and positions are illustrative."""
import random


def seed(store):
    existing = [x for x in store.layers() if x['source'] == 'demo']
    if existing:
        ensure_studio_samples(store)
        return [x for x in store.layers() if x["source"]=="demo"]
    def feature(geometry, **props):
        return {'type':'Feature', 'geometry':geometry, 'properties':props}
    def fc(fs):
        return {'type':'FeatureCollection', 'features':fs}
    stations = [('西城站',116.374,39.908),('中央站',116.389,39.915),('东园站',116.405,39.908),('北湖站',116.399,39.929)]
    layers = []
    layers.append(store.add_layer('示例 · 地铁站',fc([feature({'type':'Point','coordinates':[x,y]},name=n,kind='station') for n,x,y in stations]),source='demo',style={'color':'#174e45','visible':True}))
    rng=random.Random(42)
    layers.append(store.add_layer('示例 · 公园 POI',fc([feature({'type':'Point','coordinates':[rng.uniform(116.36,116.42),rng.uniform(39.898,39.938)]},name=f'示例公园 {i+1}',category='公园') for i in range(68)]),source='demo',style={'color':'#d68a46','visible':True}))
    roads=[feature({'type':'LineString','coordinates':[[116.354,y],[116.427,y]]},name='示意道路') for y in [39.9,39.908,39.916,39.924,39.932,39.94]]
    roads += [feature({'type':'LineString','coordinates':[[x,39.894],[x,39.944]]},name='示意道路') for x in [116.36,116.374,116.389,116.405,116.42]]
    layers.append(store.add_layer('示例 · 道路网格',fc(roads),source='demo',style={'color':'#bac8c1','visible':True}))
    layers.append(store.add_layer('示例 · 研究范围',fc([feature({'type':'Polygon','coordinates':[[[116.354,39.894],[116.427,39.894],[116.427,39.944],[116.354,39.944],[116.354,39.894]]]},name='合成研究范围')]),source='demo',style={'color':'#8dac9f','visible':True,'opacity':0.06}))
    ensure_studio_samples(store)
    return [x for x in store.layers() if x["source"]=="demo"]


def ensure_studio_samples(store):
    """Add optional, clearly synthetic district and elevation fixtures once."""
    existing={x['name'] for x in store.layers()}
    if '示例 · 统计分区' not in existing:
        from shapely.geometry import box,mapping
        fs=[]
        for i,(x0,x1) in enumerate([(116.354,116.38),(116.38,116.403),(116.403,116.427)]):
            fs.append({'type':'Feature','geometry':mapping(box(x0,39.894,x1,39.944)),'properties':{'name':['西部分区','中部分区','东部分区'][i],'population':[3200,5100,2800][i]}})
        store.add_layer('示例 · 统计分区',{'type':'FeatureCollection','features':fs},source='demo',style={'color':'#769eb8','opacity':.07,'visible':False})
    if '示例 · 合成高程 DEM' not in existing:
        import numpy as np
        import rasterio
        from pyproj import Transformer
        path=store.root/'synthetic-dem.tif'
        x0,y0,x1,y1=Transformer.from_crs(4326,3857,always_xy=True).transform_bounds(116.354,39.894,116.427,39.944)
        xx,yy=np.meshgrid(np.linspace(-2,2,150),np.linspace(-2,2,120))
        z=(80+90*np.exp(-((xx-.8)**2+(yy+.3)**2))+25*np.sin(xx*2)*np.cos(yy)).astype('float32')
        with rasterio.open(path,'w',driver='GTiff',width=150,height=120,count=1,dtype='float32',crs='EPSG:3857',transform=rasterio.transform.from_bounds(x0,y0,x1,y1,150,120),nodata=-9999) as dst:dst.write(z,1)
        meta=store.add_raster('示例 · 合成高程 DEM',path,{'synthetic':True,'vertical_units':'m','note':'数学函数生成的合成高程，不代表真实地形。'})
        store.patch_layer(meta['id'],{'source':'demo','style':{'visible':False,'color':'#779e9c','opacity':.6}})

    if not store.objects('workflows'):
        from .workflows import save
        layers=store.layers();stations=next(x for x in layers if x['name']=='示例 · 地铁站');pois=next(x for x in layers if x['name']=='示例 · 公园 POI')
        save(store,'示例 · 站点缓冲与 POI 统计',[{'id':'buffer','algorithm_id':'buffer','arguments':{'layer_id':stations['id'],'distance_m':800}}, {'id':'count','algorithm_id':'count_points','arguments':{'layer_id':'$buffer.layer_id','other_id':pois['id']}}])
