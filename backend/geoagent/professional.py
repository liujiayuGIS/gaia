"""Projected print templates: classified polygons and shaded elevation.

These are deterministic Matplotlib layouts, not a QGIS or ArcGIS engine.
Scale bars are checked on the ellipsoid at their actual placement.
"""
from __future__ import annotations

import io
import math
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patheffects as effects
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap, ListedColormap, LightSource, Normalize
from matplotlib.patches import Rectangle
from matplotlib.cm import ScalarMappable
from pandas.api.types import is_numeric_dtype
from pyproj import CRS, Geod, Transformer
import rasterio
from rasterio.vrt import WarpedVRT
from shapely.geometry import LineString, box

from .formats import frame, raster_path

INK = '#243c46'
MUTED = '#687c83'
GEOD = Geod(ellps='WGS84')
TERRAIN = LinearSegmentedColormap.from_list('elevation',
    ['#536d50', '#829e69', '#bacb92', '#e3d5a3', '#c1a781', '#aa8978', '#d3c6bb', '#f8f6f0'])
COUNTY = ['#f0f4df', '#c8ddd3', '#8db7a7', '#507f75', '#245247']


def nice_step(value):
    power = 10 ** math.floor(math.log10(max(value, 1e-12)))
    return next(x * power for x in (1, 2, 5, 10) if x * power >= value)


def class_breaks(values, classes=5):
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if not len(values):
        raise ValueError('分级字段没有有效数值。')
    edges = np.unique(np.quantile(values, np.linspace(0, 1, classes + 1)))
    if len(edges) == 1:
        edges = np.array([edges[0], edges[0] + 1])
    return edges


def scale_geometry(ax, crs, anchor, target_fraction=.2):
    """Horizontal projected positions with prescribed ellipsoidal distances."""
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    inverse = Transformer.from_crs(crs, 4326, always_xy=True)
    x = x0 + anchor[0] * (x1 - x0); y = y0 + anchor[1] * (y1 - y0)
    lon, lat = inverse.transform(x, y)
    lon1, lat1 = inverse.transform(x + target_fraction * (x1 - x0), y)
    rough = GEOD.inv(lon, lat, lon1, lat1)[2]
    power = 10 ** math.floor(math.log10(rough))
    distance = max(v * power for v in (1, 2, 5) if v * power <= rough)
    def offset(metres):
        low, high = 0., (x1 - x0) * .5
        for _ in range(45):
            middle = (low + high) / 2
            ll = inverse.transform(x + middle, y)
            if GEOD.inv(lon, lat, *ll)[2] < metres:low = middle
            else:high = middle
        return (low + high) / 2
    return x, y, [0., offset(distance / 2), offset(distance)], distance


def decorations(ax, crs, cfg):
    locations = {'top-left':(.08,.87), 'top-right':(.9,.87),
                 'bottom-left':(.08,.10), 'bottom-right':(.9,.10)}
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    if cfg.north_arrow:
        x, y = locations[cfg.north_position]
        inverse = Transformer.from_crs(crs, 4326, always_xy=True)
        project = Transformer.from_crs(4326, crs, always_xy=True)
        cx, cy = (x0+x1)/2, (y0+y1)/2
        lon, lat = inverse.transform(cx, cy)
        nx, ny = project.transform(lon, lat + .001)
        vx, vy = (nx-cx)/(x1-x0), (ny-cy)/(y1-y0)
        length = math.hypot(vx*ax.bbox.width, vy*ax.bbox.height)
        vx *= .075*ax.bbox.height/length; vy *= .075*ax.bbox.height/length
        ax.add_patch(Rectangle((x-.04,y-.04),.09,.17,transform=ax.transAxes,facecolor='white',alpha=.78,edgecolor='none',zorder=20))
        ax.annotate('', xy=(x+vx,y+vy), xytext=(x,y), xycoords='axes fraction',
                    arrowprops={'facecolor':INK,'edgecolor':INK,'width':2,'headwidth':8},zorder=21)
        ax.text(x+vx,y+vy+.02,'N',transform=ax.transAxes,ha='center',color=INK,fontsize=10,zorder=21)
    if cfg.scale_bar:
        anchor = locations[cfg.scale_position]
        if 'right' in cfg.scale_position:anchor=(.72,anchor[1])
        x,y,offsets,distance = scale_geometry(ax,crs,anchor)
        height = .008*(y1-y0)
        ax.add_patch(Rectangle((x-.015*(x1-x0),y-.04*(y1-y0)),offsets[-1]+.04*(x1-x0),.085*(y1-y0),facecolor='white',alpha=.86,edgecolor='none',zorder=20))
        for i in range(2):
            ax.add_patch(Rectangle((x+offsets[i],y),offsets[i+1]-offsets[i],height,
                         facecolor=INK if i==0 else 'white',edgecolor=INK,lw=.6,zorder=21))
        for offset,value in zip(offsets,[0,distance/2,distance]):
            label = f'{value/1000:g}' if distance>=1000 else f'{value:g}'
            ax.text(x+offset,y-height*1.2,label,ha='center',va='top',fontsize=7,color=INK,zorder=22)
        ax.text(x+offsets[-1]+.015*(x1-x0),y,'km' if distance>=1000 else 'm',fontsize=7,color=INK,zorder=22)


def graticule(ax, crs):
    inverse = Transformer.from_crs(crs,4326,always_xy=True)
    project = Transformer.from_crs(4326,crs,always_xy=True)
    x0,x1 = ax.get_xlim(); y0,y1 = ax.get_ylim()
    west,south,east,north = inverse.transform_bounds(x0,y0,x1,y1,densify_pts=21)
    boundary = box(x0,y0,x1,y1).boundary
    for meridian in (True,False):
        lower,upper = (west,east) if meridian else (south,north)
        step = nice_step((upper-lower)/5)
        for value in np.arange(math.ceil(lower/step)*step,upper,step):
            a = np.linspace(south,north,160) if meridian else np.linspace(west,east,160)
            xx,yy = project.transform(np.full_like(a,value),a) if meridian else project.transform(a,np.full_like(a,value))
            ax.plot(xx,yy,color='#a7b8b6',lw=.45,alpha=.45,zorder=8)
            intersections = LineString(zip(xx,yy)).intersection(boundary)
            points = list(intersections.geoms) if hasattr(intersections,'geoms') else [intersections]
            for p in points:
                if p.is_empty or p.geom_type!='Point':continue
                side = abs(p.y-y0)<(y1-y0)*1e-5 if meridian else abs(p.x-x0)<(x1-x0)*1e-5
                if side:
                    suffix = ('E' if value>=0 else 'W') if meridian else ('N' if value>=0 else 'S')
                    label = f'{abs(value):g}°{suffix}'
                    ax.annotate(label,(p.x,p.y),xytext=(0,-10) if meridian else (-8,0),
                                textcoords='offset points',ha='center' if meridian else 'right',
                                va='top' if meridian else 'center',fontsize=7,color=MUTED,annotation_clip=False)


def label_polygons(ax, gdf):
    key = next((x for x in ('name','NAME','Name') if x in gdf),None)
    if not key:return
    occupied=[]
    for _,row in gdf.assign(_area=gdf.geometry.area).sort_values('_area',ascending=False).head(80).iterrows():
        p=row.geometry.representative_point()
        text=ax.text(p.x,p.y,str(row[key]),ha='center',va='center',fontsize=7.2,color='#173c35',zorder=12,clip_on=True,
                     path_effects=[effects.withStroke(linewidth=2.4,foreground='white',alpha=.85)])
        bbox=text.get_window_extent(ax.figure.canvas.get_renderer()).expanded(1.12,1.25)
        if any(bbox.overlaps(old) for old in occupied):text.remove()
        else:occupied.append(bbox)


def sidebar(fig, x, y, title, text):
    fig.text(x,y,title,fontsize=10,color=INK)
    fig.text(x,y-.035,text,fontsize=8,color=MUTED,va='top',linespacing=1.8)


def render(store,cfg,layers,fmt,dpi):
    from .cartography import LOCK
    from pandas.api.types import is_numeric_dtype
    if cfg.orientation!='landscape':
        raise ValueError('专业模板当前使用横向纸张，请选择 landscape。')
    if not layers:raise ValueError('没有可见的制图数据。')
    if cfg.focus_layer_id:
        layers=[x for x in layers if x['id']==cfg.focus_layer_id]
        if not layers:raise ValueError('指定的主图层不存在或不可见。')
    rasters=[x for x in layers if x.get('kind')=='raster']
    polygons=[x for x in layers if x.get('kind')!='raster' and any('Polygon' in t for t in x['geometry_types'])]
    if cfg.template=='terrain' and len(rasters)!=1:
        raise ValueError('地形模板需要唯一的可见 DEM；请用 layer_ids 指定。')
    if cfg.template=='choropleth' and len(polygons)!=1:
        raise ValueError('专题模板需要唯一的可见面图层；请用 layer_ids 指定。')
    focus=rasters[0] if cfg.template=='terrain' else polygons[0]
    crs=CRS.from_user_input(cfg.map_crs or (focus['crs'] if focus.get('kind')=='raster' else frame(store,focus['id']).estimate_utm_crs()))
    if not crs.is_projected or not all(abs(a.unit_conversion_factor-1)<1e-8 for a in crs.axis_info):
        raise ValueError('专业模板需要以米为单位的投影坐标系。')
    dimensions={'A4':(11.69,8.27),'A3':(16.54,11.69)}[cfg.paper]
    with LOCK:
        fig=plt.figure(figsize=dimensions,facecolor='#fffefa')
        ax=fig.add_axes([.075,.16,.655,.65]);ax.set_facecolor('#e4edf2' if cfg.template=='choropleth' else '#edf3f1')
        fig.text(.055,.951,'GEOAGENT  /  PUBLIC DATA ATLAS',fontsize=8,color='#5a8179')
        fig.text(.055,.895,cfg.title,fontsize=23,color=INK)
        fig.text(.055,.855,cfg.subtitle,fontsize=9,color=MUTED)
        fig.add_artist(plt.Line2D([.055,.955],[.831,.831],transform=fig.transFigure,color='#becfc8',lw=.75))
        try:
            if cfg.template=='terrain':
                with rasterio.open(raster_path(store,focus['id'])) as src,WarpedVRT(src,crs=crs) as vrt:
                    if src.count!=1:raise ValueError('地形模板需要单波段高程 DEM，不能把多波段影像当作高程。')
                    ratio=min(1,1800/max(vrt.width,vrt.height));h=max(2,int(vrt.height*ratio));w=max(2,int(vrt.width*ratio))
                    data=vrt.read(1,out_shape=(h,w),masked=True).astype(float)
                    values=data.compressed();values=values[np.isfinite(values)]
                    if not len(values):raise ValueError('DEM 没有有效高程。')
                    lo,hi=float(values.min()),float(values.max())
                    bounds=vrt.bounds
                    xx=np.linspace(bounds.left,bounds.right,w,endpoint=False)+(bounds.right-bounds.left)/w/2
                    yy=np.linspace(bounds.top,bounds.bottom,h,endpoint=False)-(bounds.top-bounds.bottom)/h/2
                    z=data.filled(np.nan);filled=np.where(np.isfinite(z),z,np.median(values))
                    rgba=LightSource(azdeg=315,altdeg=45).shade(filled,cmap=TERRAIN,norm=Normalize(lo,hi),
                          dx=(bounds.right-bounds.left)/w,dy=(bounds.top-bounds.bottom)/h,vert_exag=1,blend_mode='soft')
                    rgba[:,:,3]=np.where(np.ma.getmaskarray(data)|~np.isfinite(z),0,1)
                    ax.imshow(rgba,extent=[bounds.left,bounds.right,bounds.bottom,bounds.top],origin='upper',zorder=1)
                    interval=cfg.contour_interval
                    levels=np.arange(math.ceil(lo/interval)*interval,hi,interval)
                    if len(levels)>100:raise ValueError('等高线超过100级，请增大间距。')
                    if len(levels):
                        contours=ax.contour(xx,yy,data,levels=levels,colors='#4e4d3c',linewidths=.35,alpha=.48,zorder=5)
                        major=levels[np.isclose(np.mod(levels,interval*5),0)]
                        major_contours=ax.contour(xx,yy,data,levels=major,colors='#4e4d3c',linewidths=.6,alpha=.6,zorder=6) if len(major) else contours
                        labels=ax.clabel(major_contours,major if len(major) else levels[::5],fmt='%d',fontsize=6,inline=True)
                        for text in labels:text.set_path_effects([effects.withStroke(linewidth=1.6,foreground='#ffffef',alpha=.8)])
                    ax.set_xlim(bounds.left,bounds.right);ax.set_ylim(bounds.bottom,bounds.top)
                    pixel_size=(bounds.right-bounds.left)/w
                if cfg.legend:
                    if cfg.legend_position=='outside-right':
                        color_axis=fig.add_axes([.78,.48,.025,.255])
                        fig.text(.775,.775,cfg.legend_title or '高程 / m',fontsize=10,color=INK)
                    else:
                        right='right' in cfg.legend_position;top='top' in cfg.legend_position
                        color_axis=ax.inset_axes([.86 if right else .09,.60 if top else .20,.025,.22])
                    bar=fig.colorbar(ScalarMappable(norm=Normalize(lo,hi),cmap=TERRAIN),cax=color_axis)
                    bar.ax.tick_params(labelsize=8,colors=MUTED);bar.outline.set_linewidth(.4)
                    if cfg.legend_position!='outside-right':bar.set_label(cfg.legend_title or '高程 / m',fontsize=8)
                sidebar(fig,.775,.435,'地形表达',f'等高距 {interval:g} m\n光照方位 315° / 高度 45°\n垂直夸张 1×\n显示像元约 {pixel_size:.1f} m')
            else:
                gdf=frame(store,focus['id']).to_crs(crs)
                field=focus['style'].get('field')
                if not field or field not in gdf or not is_numeric_dtype(gdf[field]):
                    raise ValueError('专题模板需先用 style_layer 指定数值 field。')
                edges=class_breaks(gdf[field],5);colors=COUNTY[:len(edges)-1]
                cmap=ListedColormap(colors);norm=BoundaryNorm(edges,len(colors))
                gdf.plot(ax=ax,column=field,cmap=cmap,norm=norm,edgecolor='#fffdf7',linewidth=.75,zorder=2)
                gpd.GeoSeries([gdf.geometry.union_all()],crs=crs).boundary.plot(ax=ax,color='#3a6056',linewidth=.9,zorder=3)
                x0,y0,x1,y1=gdf.total_bounds;ax.set_xlim(x0-(x1-x0)*.035,x1+(x1-x0)*.035);ax.set_ylim(y0-(y1-y0)*.06,y1+(y1-y0)*.06)
                if cfg.legend:
                    if cfg.legend_position=='outside-right':
                        fig.text(.775,.775,cfg.legend_title or field,fontsize=10,color=INK)
                        fig.text(.775,.74,'分位数分级 · '+str(len(colors))+' 级',fontsize=8,color=MUTED)
                        for i,color in enumerate(colors):
                            y=.68-i*.052
                            fig.add_artist(Rectangle((.775,y),.026,.025,transform=fig.transFigure,facecolor=color,edgecolor='#a4b8b0',lw=.4))
                            label=f'{edges[i]:,.0f} - {edges[i+1]:,.0f}'
                            fig.text(.813,y+.007,label,fontsize=8,color=INK)
                    else:
                        from matplotlib.patches import Patch
                        handles=[Patch(facecolor=c,label=f'{edges[i]:,.0f} - {edges[i+1]:,.0f}') for i,c in enumerate(colors)]
                        loc={'top-left':'upper left','top-right':'upper right','bottom-left':'lower left','bottom-right':'lower right'}[cfg.legend_position]
                        ax.legend(handles=handles,title=cfg.legend_title or field,loc=loc,fontsize=7,title_fontsize=8,framealpha=.92)
                sidebar(fig,.775,.36,'阅读说明',f'{len(gdf)} 个面要素\n按原始数值分位数分级\n地名按空间位置避让')
            if cfg.extent:
                extent=Transformer.from_crs(4326,crs,always_xy=True).transform_bounds(*cfg.extent,densify_pts=21)
                ax.set_xlim(extent[0],extent[2]);ax.set_ylim(extent[1],extent[3])
            ax.set_aspect('equal',adjustable='box');ax.set_xticks([]);ax.set_yticks([]);ax.set_xlabel('');ax.set_ylabel('')
            for spine in ax.spines.values():spine.set_color('#bacbc4');spine.set_linewidth(.6)
            if cfg.grid:graticule(ax,crs)
            fig.canvas.draw()
            if cfg.template=='choropleth' and focus['style'].get('labels',True):label_polygons(ax,gdf)
            decorations(ax,crs,cfg)
            if cfg.context_layer_id:
                context=frame(store,cfg.context_layer_id).to_crs(4326)
                inset=fig.add_axes([.775,.15,.17,.115]);inset.set_facecolor('#eef3f0')
                context.plot(ax=inset,facecolor='#cbdad2',edgecolor='#7a9589',linewidth=.25)
                west,south,east,north=focus['bounds']
                inset.add_patch(Rectangle((west,south),east-west,north-south,facecolor='#c18156',edgecolor='#995f3a',alpha=.85,lw=.8))
                inset.set_xticks([]);inset.set_yticks([]);inset.set_xlabel('');inset.set_ylabel('');inset.set_title('区域位置 / Washington',fontsize=8,color=MUTED,loc='left',pad=7)
                for spine in inset.spines.values():spine.set_color('#cbd8d0');spine.set_linewidth(.5)
            inverse=Transformer.from_crs(crs,4326,always_xy=True)
            x0,x1=ax.get_xlim();y0,y1=ax.get_ylim()
            ground=GEOD.inv(*inverse.transform(x0,(y0+y1)/2),*inverse.transform(x1,(y0+y1)/2))[2]
            physical_width=fig.get_figwidth()*ax.get_position().width*.0254
            fig.add_artist(plt.Line2D([.055,.955],[.108,.108],transform=fig.transFigure,color='#becfc8',lw=.75))
            fig.text(.055,.076,cfg.source_note,fontsize=7.5,color=MUTED)
            fig.text(.055,.043,f'{crs.to_authority()[0]+":"+crs.to_authority()[1] if crs.to_authority() else crs.name}  |  地图中心参考比例 1:{ground/physical_width:,.0f}  |  {cfg.paper} 原尺寸打印',fontsize=7,color=MUTED)
            fig.text(.955,.043,'真实公开数据 · GeoAgent Studio',fontsize=7,color=MUTED,ha='right')
            out=io.BytesIO();fig.savefig(out,format=fmt,dpi=dpi,facecolor=fig.get_facecolor())
            return out.getvalue()
        finally:plt.close(fig)
