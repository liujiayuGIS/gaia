"""Publish real native-QGIS print examples without removing existing workspace data."""
import json,shutil
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/public-cartography'
client=httpx.Client(base_url='http://127.0.0.1:8765/api',timeout=240)
def request(method,path,body=None):
 r=client.request(method,path,json=body);r.raise_for_status();return r.json()
def main():
 assert request('GET','/health')['version']=='0.3.0'
 published=json.loads((OUT/'published.json').read_text())
 layers=request('GET','/layers')
 v=next(x for x in layers if 'Census' in x['name'] or '县界' in x['name'])
 r=next(x for x in layers if x.get('kind')=='raster' and ('USGS' in x['name'] or 'DEM' in x['name']))
 area=next(x for x in layers if 'land_km2' in x.get('fields',[]))
 # These sample polygons otherwise cover the DEM in the web preview. Preserve all source data.
 for item in [v,area]:request('PATCH','/layers/'+item['id']+'/style',{'visible':False})
 receipts=[]
 for filename,spec in [('qgis-washington',{'template':'choropleth','focus_layer_id':area['id'],'context_layer_id':None,'map_crs':'EPSG:5070','title':'华盛顿州 · 县域陆地面积','subtitle':'Census 2024 / 39 counties / Quantile classification','legend_title':'陆地面积 / km²','source_note':'U.S. Census Bureau · 2024 Cartographic Boundary Files · 1:500,000\nALAND（m²）÷ 1,000,000；表示县域陆地面积，不表示人口或人口密度。'}),('qgis-rainier',{'template':'terrain','focus_layer_id':r['id'],'context_layer_id':v['id'],'map_crs':'EPSG:32610','title':'雷尼尔山 · 地形与高程','subtitle':'Mount Rainier, Washington / USGS 3DEP / 等高距 200 m','legend_title':'高程 / m','source_note':'USGS 3DEP 高程服务 · AOI 双线性重采样约 33.84 m · 非原生分辨率瓦片\nCensus 2024 县界 · 位置插图仅作区域参考'})]:
  # Focus layers must be visible for export; reset only our public demo layers.
  request('PATCH','/layers/'+area['id']+'/style',{'visible':filename=='qgis-washington'})
  request('PATCH','/layout',{**spec,'plugin_id':'qgis','items':{},'template_id':None,'legend_position':'outside-right','grid':True})
  artifacts=[]
  for fmt in ['png','pdf']:
   item=request('POST','/layout/export',{'format':fmt,'dpi':300});artifacts.append(item)
  project=request('POST','/projects',{'name':spec['title'],'plugin_id':'qgis'})
  template=request('POST','/layout-templates',{'name':spec['title'],'plugin_id':'qgis'})
  receipts.append({'name':filename,'artifacts':artifacts,'project':project,'template':template})
  print(filename,'published',flush=True)
 (OUT/'published-native.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2))
 print('Native samples ready at localhost:8765',flush=True)
if __name__=='__main__':main()
