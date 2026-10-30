"""One validated layout specification for preview and PNG/JPEG/TIFF/SVG/PDF export."""
from __future__ import annotations
import io
import math
import os
import tempfile
import threading
import uuid
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'geoagent-matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap,Normalize
from matplotlib.patches import Patch
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from pyproj import Transformer
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from .formats import frame,raster_path,raster_preview
from .store import now

LOCK=threading.RLock()
for f in ['/System/Library/Fonts/Supplemental/Arial Unicode.ttf','/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc']:
    if Path(f).exists():
        font_manager.fontManager.addfont(f);matplotlib.rcParams['font.family']=font_manager.FontProperties(fname=f).get_name();break
matplotlib.rcParams['axes.unicode_minus']=False
matplotlib.rcParams['svg.fonttype']='path'
matplotlib.rcParams['pdf.fonttype']=42

class Layout(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title: str=Field(default='空间分析成果图',max_length=120)
    subtitle: str=Field(default='GeoAgent Studio',max_length=200)
    paper: Literal['A4','A3']='A4'
    orientation: Literal['landscape','portrait']='landscape'
    north_arrow: bool=True
    north_position: Literal['top-left','top-right','bottom-left','bottom-right']='top-right'
    legend: bool=True
    legend_position: Literal['top-left','top-right','bottom-left','bottom-right']='bottom-right'
    scale_bar: bool=True
    scale_position: Literal['top-left','top-right','bottom-left','bottom-right']='bottom-left'
    grid: bool=False
    source_note: str=Field(default='数据与处理记录保存在本地项目中',max_length=300)
    extent: list[float] | None=Field(default=None,min_length=4,max_length=4)


def get_layout(store):
    return Layout.model_validate(store.setting('layout',{})).model_dump()


def update_layout(store,changes):
    layout=Layout.model_validate({**get_layout(store),**changes})
    if layout.extent:
        x0,y0,x1,y1=layout.extent
        if not(-180<=x0<x1<=180 and -85<=y0<y1<=85):raise ValueError('出图范围必须是有效 WGS84 边界。')
    return store.put_object('settings','layout',layout.model_dump())


def position(value):
    return {'top-left':(.07,.9),'top-right':(.93,.9),'bottom-left':(.07,.09),'bottom-right':(.93,.09)}[value]


def render_map(store,fmt='svg',dpi=150,layer_ids=None,overrides=None):
    if fmt not in ('png','jpeg','jpg','tiff','tif','svg','pdf'):raise ValueError('支持 PNG、JPEG、TIFF、SVG 和 PDF。')
    if dpi not in (100,150,200,300):raise ValueError('DPI 支持 100、150、200、300。')
    config=Layout.model_validate({**get_layout(store),**(overrides or {})})
    layers=[x for x in store.layers() if (not layer_ids or x['id'] in layer_ids) and x['style'].get('visible',True)]
    if not layers:raise ValueError('请先导入或生成可见图层。')
    def draw_order(layer):
        if layer.get('kind')=='raster':return 0
        types=' '.join(layer.get('geometry_types',[]))
        return 3 if 'Point' in types else 2 if 'Line' in types else 1
    layers.sort(key=draw_order)
    dimensions={'A4':(11.69,8.27),'A3':(16.54,11.69)}[config.paper]
    if config.orientation=='portrait':dimensions=dimensions[::-1]
    with LOCK:
        fig=plt.figure(figsize=dimensions,facecolor='white');ax=fig.add_axes([.07,.12,.86,.73]);ax.set_facecolor('#f5f8fa')
        patches=[];colorbar=None
        try:
            for layer in layers:
                if layer.get('kind')=='raster':
                    with rasterio.open(raster_path(store,layer['id'])) as src,WarpedVRT(src,crs='EPSG:3857') as vrt:
                        from PIL import Image
                        rgba=np.asarray(Image.open(io.BytesIO(raster_preview(store,layer['id'],1600))))
                        ax.imshow(rgba,extent=[vrt.bounds.left,vrt.bounds.right,vrt.bounds.bottom,vrt.bounds.top],origin='upper',alpha=layer['style'].get('opacity',.85))
                else:
                    gdf=frame(store,layer['id']).to_crs(3857)
                    if gdf.empty:continue
                    style=layer['style'];color=style.get('color','#397eab');field=style.get('field')
                    options={'ax':ax,'edgecolor':color,'linewidth':.7,'alpha':style.get('opacity',.25 if gdf.geom_type.str.contains('Polygon').all() else 1),'markersize':38}
                    if gdf.geom_type.str.contains('Point').all():options.update(alpha=style.get('opacity',1),edgecolor='white',linewidth=.8)
                    if field and field in gdf and np.issubdtype(gdf[field].dtype,np.number):
                        cmap=LinearSegmentedColormap.from_list('layer',['#d8e8f2',color]);gdf.plot(column=field,cmap=cmap,**options)
                        colorbar=(cmap,Normalize(float(gdf[field].min()),max(float(gdf[field].max()),float(gdf[field].min())+1)),field)
                    else:gdf.plot(color=color,**options)
                    if style.get('labels','站' in layer['name']) and 'name' in gdf.columns and len(gdf)<=50:
                        for _,r in gdf.iterrows():
                            p=r.geometry.representative_point();ax.annotate(str(r['name']),[p.x,p.y],xytext=(4,5),textcoords='offset points',fontsize=7,color='#213b51')
                patches.append(Patch(facecolor=layer['style'].get('color','#397eab'),label=layer['name']))
            if config.extent:
                x0,y0,x1,y1=Transformer.from_crs(4326,3857,always_xy=True).transform_bounds(*config.extent)
                ax.set_xlim(x0,x1);ax.set_ylim(y0,y1)
            ax.margins(.07);ax.set_aspect('equal',adjustable='box')
            if config.grid:ax.grid(alpha=.2,linewidth=.5)
            else:ax.set_xticks([]);ax.set_yticks([])
            ax.set_xlabel('Easting (m)' if config.grid else '');ax.set_ylabel('Northing (m)' if config.grid else '')
            for spine in ax.spines.values():spine.set_color('#b9c9d5');spine.set_linewidth(.8)
            fig.text(.07,.92,config.title,fontsize=20,color='#18364d',weight='bold')
            fig.text(.07,.877,config.subtitle,fontsize=9,color='#718595')
            if config.north_arrow:
                x,y=position(config.north_position);ax.annotate('',xy=(x,y+.035),xytext=(x,y-.055),xycoords='axes fraction',arrowprops={'facecolor':'#17364c','edgecolor':'#17364c','width':3,'headwidth':10});ax.text(x,y+.055,'N',transform=ax.transAxes,ha='center',fontsize=12,weight='bold',color='#17364c')
            if config.scale_bar:
                x0,x1=ax.get_xlim();y0,y1=ax.get_ylim();_,lat=Transformer.from_crs(3857,4326,always_xy=True).transform((x0+x1)/2,(y0+y1)/2)
                ground=(x1-x0)*math.cos(math.radians(lat));rough=ground*.18;power=10**math.floor(math.log10(max(rough,1e-6)));length=max(v*power for v in (1,2,5) if v*power<=rough) if rough>=power else power
                span=length/ground;x,y=position(config.scale_position);left=x if x<.5 else x-span
                ax.plot([left,left+span],[y,y],transform=ax.transAxes,color='#17364c',lw=2.5);ax.plot([left,left],[y-.01,y+.01],transform=ax.transAxes,color='#17364c',lw=1);ax.plot([left+span,left+span],[y-.01,y+.01],transform=ax.transAxes,color='#17364c',lw=1)
                ax.text(left+span/2,y+.025,f'{length/1000:g} km' if length>=1000 else f'{length:g} m',transform=ax.transAxes,ha='center',fontsize=8,color='#17364c')
            if config.legend:
                if colorbar:
                    cmap,norm,label=colorbar;cbax=fig.add_axes([.72,.055,.20,.012]);fig.colorbar(matplotlib.cm.ScalarMappable(norm=norm,cmap=cmap),cax=cbax,orientation='horizontal',label=label);cbax.tick_params(labelsize=7)
                loc={'top-left':'upper left','top-right':'upper right','bottom-left':'lower left','bottom-right':'lower right'}[config.legend_position]
                ax.legend(handles=patches,loc=loc,fontsize=6,framealpha=.9,edgecolor='#dce5eb')
            fig.text(.07,.065,config.source_note,fontsize=7,color='#7b8a96')
            fig.text(.07,.041,'显示投影 EPSG:3857 · 比例尺按地图中心纬度换算 · 指北针为真北',fontsize=6,color='#99a6af')
            output=io.BytesIO();fig.savefig(output,format=fmt,dpi=dpi,facecolor='white');return output.getvalue()
        finally:plt.close(fig)


def export_map(store,fmt='pdf',dpi=150,layer_ids=None,run_id=None):
    content=render_map(store,fmt,dpi,layer_ids)
    export_id=uuid.uuid4().hex;folder=store.root/'exports';folder.mkdir(exist_ok=True);path=folder/f'{export_id}.{fmt}';path.write_bytes(content)
    result={'id':export_id,'name':get_layout(store)['title']+'.'+fmt,'format':fmt,'dpi':dpi,'created_at':now(),'run_id':run_id,'url':f'/api/exports/{export_id}/download','layout':get_layout(store),'path':str(path.relative_to(store.root))}
    return store.put_object('exports',export_id,result)
