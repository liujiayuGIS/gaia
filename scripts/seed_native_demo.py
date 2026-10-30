"""Populate an isolated workspace with the downloaded Census / USGS samples."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from geoagent.store import Store
from geoagent import formats,cartography

def seed(root):
 s=Store(root);out=ROOT/'outputs/public-cartography'
 if s.layers():return s
 v,r=[formats.import_asset(s,formats.stage_files(s,[(f,(out/'raw'/f).read_bytes())])['id']) for f in ('washington-counties-shp.zip','rainier-usgs-3dep.tif')]
 s.patch_layer(v['id'],{'name':'华盛顿州县界 · Census 2024'})
 s.patch_layer(r['id'],{'name':'雷尼尔山 DEM · USGS 3DEP'})
 s.style_layer(v['id'],visible=False,labels=False)
 cartography.update_layout(s,{'plugin_id':'qgis','template':'terrain','focus_layer_id':r['id'],'context_layer_id':v['id'],'map_crs':'EPSG:32610','title':'雷尼尔山 · 地形与高程','subtitle':'Mount Rainier, Washington / USGS 3DEP / 等高距 200 m','legend_title':'高程 / m','legend_position':'outside-right','source_note':'USGS 3DEP 高程服务 · AOI 双线性重采样约 33.84 m · 非原生分辨率瓦片\nCensus 2024 县界 · 位置插图仅作区域参考','grid':True})
 return s
if __name__=='__main__':
 s=seed(Path(sys.argv[1]));print(json.dumps({'root':str(s.root),'layers':len(s.layers())}))
