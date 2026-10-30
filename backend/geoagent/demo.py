"""Synthetic, fixed-seed city-scale fixtures. Names and positions are illustrative."""
import random


def seed(store):
    existing = [x for x in store.layers() if x['source'] == 'demo']
    if existing:
        return existing
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
    return layers
