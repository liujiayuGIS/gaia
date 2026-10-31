import io
import geopandas as gpd
import numpy as np
import pytest
import rasterio
from PIL import Image
from pyproj import Geod, Transformer
from shapely.geometry import box
from geoagent.store import Store
from geoagent import formats, cartography, professional


@pytest.mark.parametrize('epsg',[3857,32610,5070])
def test_scale_bar_distance_is_ground_distance_at_placement(epsg):
    import matplotlib.pyplot as plt
    forward=Transformer.from_crs(4326,epsg,always_xy=True)
    inverse=Transformer.from_crs(epsg,4326,always_xy=True)
    x,y=forward.transform(-121.7,46.85)
    fig,ax=plt.subplots();ax.set_xlim(x-15000,x+15000);ax.set_ylim(y-15000,y+15000)
    try:
        start,y,positions,label=professional.scale_geometry(ax,epsg,(.08,.1))
        for offset,expected in zip(positions[1:],[label/2,label]):
            distance=Geod(ellps='WGS84').inv(*inverse.transform(start,y),*inverse.transform(start+offset,y))[2]
            assert distance==pytest.approx(expected,abs=.001)
    finally:plt.close(fig)


@pytest.mark.parametrize('template',['terrain','choropleth'])
@pytest.mark.parametrize('fmt',['png','pdf'])
def test_projected_templates_export_with_focus_and_real_units(tmp_path,template,fmt):
    store=Store(tmp_path/'project')
    frame=gpd.GeoDataFrame({'name':['A','B','C'],'area_km2':[1.,2.,3.]},geometry=[box(-122+i*.03,46.8,-121.98+i*.03,46.82) for i in range(3)],crs=4326)
    vector=formats.add_frame(store,'regions',frame,{},style={'visible':True,'field':'area_km2','labels':True})
    path=tmp_path/'dem.tif'
    with rasterio.open(path,'w',driver='GTiff',width=30,height=30,count=1,dtype='float32',crs=32610,
         transform=rasterio.transform.from_origin(590000,5200000,100,100),nodata=-9999) as dst:
        data=(100+np.arange(900).reshape(30,30)).astype('float32');data[0,0]=-9999;dst.write(data,1)
    raster=store.add_raster('DEM',path,{'vertical_units':'m'})
    cartography.update_layout(store,{'template':template,'focus_layer_id':raster['id'] if template=='terrain' else vector['id'],
        'map_crs':'EPSG:32610','title':'专业模板测试','legend_position':'outside-right',
        'legend_title':'高程 / m' if template=='terrain' else '面积 / km²','grid':True})
    result=cartography.export_map(store,fmt,100)
    content=(store.root/result['path']).read_bytes()
    if fmt=='pdf':assert content.startswith(b'%PDF-')
    else:
        # QGIS and Matplotlib quantize millimetres to pixels differently.
        assert Image.open(io.BytesIO(content)).size==pytest.approx((1169,827),abs=1)
    assert result['layout']['map_crs']=='EPSG:32610'


def test_quantile_breaks_handle_ties_and_missing_values():
    result=professional.class_breaks([1,1,1,2,3,np.nan])
    assert np.all(np.diff(result)>0)
    assert professional.class_breaks([7,7]).tolist()==[7,8]
    with pytest.raises(ValueError):professional.class_breaks([np.nan])
