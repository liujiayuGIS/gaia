"""Export official sample data with the installed native QGIS plugin."""
import json,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'));sys.path.insert(0,str(ROOT/'scripts'))
from seed_native_demo import seed
from geoagent import formats,cartography
from geoagent.plugins import PluginManager

def main():
 out=ROOT/'outputs/public-cartography';s=seed(ROOT/'.runtime/native-delivery');p=PluginManager(s).get('qgis')
 v=next(x for x in s.layers() if x['kind']!='raster');r=next(x for x in s.layers() if x['kind']=='raster')
 frame=formats.frame(s,v['id']);frame['land_km2']=frame['ALAND']/1e6
 derived=formats.add_frame(s,'华盛顿州县域陆地面积',frame,{'source':'Census ALAND / 1e6'},style={'visible':True,'field':'land_km2','labels':True,'color':'#265047','opacity':1})
 specs=[('qgis-washington',{'template':'choropleth','focus_layer_id':derived['id'],'context_layer_id':None,'map_crs':'EPSG:5070','title':'华盛顿州 · 县域陆地面积','subtitle':'Census 2024 / 39 counties / Quantile classification','legend_title':'陆地面积 / km²','source_note':'U.S. Census Bureau · 2024 Cartographic Boundary Files · 1:500,000\nALAND（m²）÷ 1,000,000 · 本图表示陆地面积，不表示人口或人口密度。'}),('qgis-rainier',{'template':'terrain','focus_layer_id':r['id'],'context_layer_id':v['id'],'map_crs':'EPSG:32610','title':'雷尼尔山 · 地形与高程','subtitle':'Mount Rainier, Washington / USGS 3DEP / 等高距 200 m','legend_title':'高程 / m','source_note':'USGS 3DEP 高程服务 · AOI 双线性重采样约 33.84 m · 非原生分辨率瓦片\nCensus 2024 县界 · 位置插图仅作区域参考'})]
 receipts=[]
 for filename,spec in specs:
  cartography.update_layout(s,{**spec,'plugin_id':'qgis','legend_position':'outside-right','grid':True,'template_id':None,'items':{}})
  for fmt in ['png','pdf','svg']:
   (out/(filename+'.'+fmt)).write_bytes(cartography.render_map(s,fmt,300))
  project=s.setting('last_qgis_project');shutil.copy2(s.root/project['bundle'],out/(filename+'-project.zip'))
  receipts.append({'name':filename,'project':project})
 (out/'native-maps.json').write_text(json.dumps({'engine':p.status(),'maps':receipts},ensure_ascii=False,indent=2));print(json.dumps([x['name'] for x in receipts]))
if __name__=='__main__':main()
