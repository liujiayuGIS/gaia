"""Isolated layer-order browser fixture; run with scripts/layer-order-ui-test.cjs."""
import os,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
os.environ.setdefault('GEOAGENT_WORKSPACE','/private/tmp/gaia-order-browser-workspace')
from geoagent.app import app
from shapely.geometry import box,mapping
import rasterio,numpy as np
s=app.state.store
if not s.layers():
 ids=[]
 for name,color in [('地块 · 红色','#e63636'),('地块 · 蓝色','#2463db')]:
  l=s.add_layer(name,{'type':'FeatureCollection','features':[{'type':'Feature','geometry':mapping(box(116,39,117,40)),'properties':{'name':name}}]},style={'color':color,'opacity':1,'visible':True,'labels':False});ids.append(l['id'])
 p=s.root/'fixture.tif'
 with rasterio.open(p,'w',driver='GTiff',height=10,width=10,count=1,dtype='float32',crs='EPSG:4326',transform=rasterio.transform.from_bounds(116,39,117,40,10,10)) as dst:dst.write(np.arange(100,dtype='float32').reshape(10,10),1)
 l=s.add_raster('高程栅格',p);ids.append(l['id']);s.reorder_layers([ids[1],ids[0],ids[2]])
import uvicorn
uvicorn.run(app,host='127.0.0.1',port=8767)
