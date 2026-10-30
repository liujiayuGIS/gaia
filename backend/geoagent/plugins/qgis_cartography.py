"""Native QGIS project, style, print-layout and editable-scene operations."""
import json
import math
from pathlib import Path
import shutil
import zipfile
from qgis.core import *
from qgis.PyQt.QtCore import Qt, QRectF, QSize
from qgis.PyQt.QtGui import QColor, QFont, QFontDatabase, QPainter
from qgis.PyQt.QtXml import QDomDocument

FONT='Arial Unicode MS'
INK='#293941'
COLORS=['#edf3db','#c5d9ce','#8db3a4','#527e73','#265047']
TERRAIN=['#536d50','#829e69','#bacb92','#e3d5a3','#c1a781','#aa8978','#d3c6bb','#f8f6f0']


def font(size):
    value=QFont(FONT);value.setPointSizeF(float(size));return value


def labels(layer,key,size=8,line=False):
    settings=QgsPalLayerSettings();settings.fieldName=key
    if line:
        settings.isExpression=True;settings.fieldName='CASE WHEN "ELEV" % 1000 = 0 THEN format_number("ELEV",0) END'
        settings.placement=Qgis.LabelPlacement.Line
    fmt=QgsTextFormat();fmt.setFont(font(size));fmt.setSize(size);fmt.setColor(QColor(INK))
    buffer=QgsTextBufferSettings();buffer.setEnabled(True);buffer.setSize(.6);buffer.setColor(QColor('#fffefa'))
    fmt.setBuffer(buffer);settings.setFormat(fmt)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings));layer.setLabelsEnabled(True)


def vector_style(layer,meta):
    style=meta.get('style',{});field=style.get('field');color=style.get('color','#467e74')
    if meta.get('qml'):
        layer.loadNamedStyle(meta['qml'])
    elif field and field in layer.fields().names() and layer.geometryType()==Qgis.GeometryType.Polygon:
        renderer=QgsGraduatedSymbolRenderer();renderer.setClassAttribute(field)
        renderer.setClassificationMethod(QgsClassificationQuantile());renderer.updateClasses(layer,5)
        renderer.setLabelFormat(QgsRendererRangeLabelFormat('%1 - %2',0))
        for i,r in enumerate(renderer.ranges()):
            symbol=QgsFillSymbol.createSimple({'color':COLORS[min(i,4)],'outline_color':'#fffefa','outline_width':'.18'})
            renderer.updateRangeSymbol(i,symbol)
            renderer.updateRangeLabel(i,f'{r.lowerValue():,.0f} - {r.upperValue():,.0f}')
        layer.setRenderer(renderer)
    else:
        if layer.geometryType()==Qgis.GeometryType.Polygon:
            symbol=QgsFillSymbol.createSimple({'color':color,'outline_color':'#fffefa','outline_width':'.18'})
        elif layer.geometryType()==Qgis.GeometryType.Line:
            symbol=QgsLineSymbol.createSimple({'line_color':color,'line_width':'.25'})
        else:symbol=QgsMarkerSymbol.createSimple({'color':color,'outline_color':'white','size':'2.0'})
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.setOpacity(float(style.get('opacity',1)))
    key=next((x for x in ('name','NAME','Name') if x in layer.fields().names()),None)
    if key and style.get('labels',False):labels(layer,key)


def raster_style(layer,meta):
    stats=layer.dataProvider().bandStatistics(1,QgsRasterBandStats.All,layer.extent(),1000000)
    lo,hi=stats.minimumValue,stats.maximumValue
    if not math.isfinite(lo) or not math.isfinite(hi):raise ValueError('栅格缺少有效数值。')
    if hi<=lo:hi=lo+1
    ramp=QgsColorRampShader(lo,hi);ramp.setColorRampType(QgsColorRampShader.Interpolated)
    ramp.setColorRampItemList([QgsColorRampShader.ColorRampItem(lo+(hi-lo)*i/(len(TERRAIN)-1),QColor(c),f'{lo+(hi-lo)*i/(len(TERRAIN)-1):.0f}') for i,c in enumerate(TERRAIN)])
    legend_settings=QgsColorRampLegendNodeSettings();numeric=QgsBasicNumericFormat();numeric.setNumberDecimalPlaces(0)
    legend_settings.setNumericFormat(numeric);legend_settings.setMinimumLabel(f'{lo:,.0f}');legend_settings.setMaximumLabel(f'{hi:,.0f}')
    ramp.setLegendSettings(legend_settings)
    shader=QgsRasterShader(lo,hi);shader.setRasterShaderFunction(ramp)
    renderer=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),1,shader)
    renderer.setClassificationMin(lo);renderer.setClassificationMax(hi);layer.setRenderer(renderer)
    return lo,hi


def add_label(layout,id,text,x,y,w,h,size=9,color=INK):
    item=QgsLayoutItemLabel(layout);item.setId(id);item.setText(text);item.setFont(font(size));item.setFontColor(QColor(color))
    layout.addLayoutItem(item);item.attemptMove(QgsLayoutPoint(x,y));item.attemptResize(QgsLayoutSize(w,h))
    return item


def position(value,width=10,height=20):
    return {'top-left':(7,7),'top-right':(100-width-7,7),'bottom-left':(7,100-height-7),'bottom-right':(100-width-7,100-height-7)}.get(value,(7,7))


def execute(request):
    import processing
    job=Path(request['job']);out=job/'outputs';out.mkdir(exist_ok=True)
    project=QgsProject.instance();project.clear()
    for path in ['/System/Library/Fonts/Supplemental/Arial Unicode.ttf']:
        if Path(path).exists():QFontDatabase.addApplicationFont(path)
    if request['operation']=='open_project':
        if not project.read(request['path']):raise ValueError('QGIS 无法重新打开工程。')
        reverse={v:k for k,v in json.loads(project.customVariables().get('geoagent_layer_map','{}')).items()}
        outputs=[];metadata=[]
        for layer in project.mapLayers().values():
            if layer.id() not in reverse:continue
            if not layer.isValid():raise ValueError('工程图层失效：'+layer.name())
            path=Path(layer.source().split('|')[0]).resolve()
            if not path.is_relative_to(job):raise ValueError('工程引用了包外数据。')
            if isinstance(layer,QgsVectorLayer) or isinstance(layer,QgsRasterLayer):
                style=out/(layer.id()+'.qml');layer.saveNamedStyle(str(style))
                outputs.append({'name':layer.name(),'path':str(path),'allow_file_only':True})
                metadata.append({'backend_id':reverse.get(layer.id(),layer.id()),'style_path':str(style)})
        return {'outputs':outputs,'layer_metadata':metadata,'qgis_version':Qgis.QGIS_VERSION}
    config=request['layout'];paper=config.get('paper','A4');landscape=config.get('orientation','landscape')=='landscape'
    folder=out/'project';data=folder/'data';styles=folder/'styles'
    data.mkdir(parents=True,exist_ok=True);styles.mkdir(exist_ok=True)
    loaded={};original={};bindings={}
    for meta in request.get('layers',[]):
        source=Path(meta['path']);target=data/source.name;shutil.copy2(source,target)
        layer=QgsRasterLayer(str(target),meta['name']) if meta.get('kind')=='raster' else QgsVectorLayer(str(target),meta['name'],'ogr')
        if not layer.isValid():raise ValueError('QGIS 图层失效：'+meta['name'])
        if isinstance(layer,QgsVectorLayer):vector_style(layer,meta)
        project.addMapLayer(layer);loaded[meta['id']]=layer;original[meta['id']]=meta;bindings[meta['id']]=layer.id()
    focus_id=config.get('focus_layer_id')
    candidates=[loaded[x] for x in request.get('map_layers',[]) if x in loaded]
    if focus_id and focus_id in loaded:candidates=[loaded[focus_id]]
    if not candidates:raise ValueError('请先选择有效的制图图层。')
    focus=candidates[0]
    crs=QgsCoordinateReferenceSystem(config.get('map_crs') or focus.crs().authid() or 'EPSG:3857')
    if not crs.isValid():raise ValueError('无效出图投影。')
    project.setCrs(crs);project.setEllipsoid('WGS84')
    main_layers=candidates.copy()
    if config.get('template')=='terrain':
        if not isinstance(focus,QgsRasterLayer) or focus.bandCount()!=1:raise ValueError('地形模板需要单波段 DEM。')
        raster_style(focus,original.get(focus_id,{}))
        shade=QgsRasterLayer(focus.source(),'Hillshade')
        shade.setRenderer(QgsHillshadeRenderer(shade.dataProvider(),1,315,45));shade.setBlendMode(QPainter.CompositionMode_Multiply);shade.setOpacity(.4)
        project.addMapLayer(shade)
        contour_path=data/'contours.gpkg'
        processing.run('gdal:contour',{'INPUT':focus.source(),'BAND':1,'INTERVAL':float(config.get('contour_interval',200)),
              'FIELD_NAME':'ELEV','CREATE_3D':False,'IGNORE_NODATA':False,'OFFSET':0,'OUTPUT':str(contour_path)})
        contour=QgsVectorLayer(str(contour_path),'Contours','ogr')
        if not contour.isValid():raise ValueError('QGIS 等高线生成失败。')
        contour.setRenderer(QgsSingleSymbolRenderer(QgsLineSymbol.createSimple({'line_color':'91,85,66,150','line_width':'.10'})))
        labels(contour,'ELEV',6,True);project.addMapLayer(contour)
        main_layers=[contour,shade,focus]
    layout=QgsPrintLayout(project);layout.initializeDefaults();layout.setName(config.get('title','Map'))
    layout.pageCollection().pages()[0].setPageSize(paper,QgsLayoutItemPage.Landscape if landscape else QgsLayoutItemPage.Portrait)
    width=layout.pageCollection().pages()[0].pageSize().width();height=layout.pageCollection().pages()[0].pageSize().height()
    sx,sy=width/297,height/210
    main=QgsLayoutItemMap(layout);main.setId('main_map');layout.addLayoutItem(main)
    main.attemptMove(QgsLayoutPoint((32 if config.get('template')=='terrain' else 15)*sx,43*sy))
    main.attemptResize(QgsLayoutSize((150 if config.get('template')=='terrain' else 202)*sx,145*sy))
    main.setCrs(crs);main.setLayers(main_layers);main.setKeepLayerSet(True)
    extent=QgsRectangle()
    for layer in candidates:
        rectangle=QgsCoordinateTransform(layer.crs(),crs,project).transformBoundingBox(layer.extent())
        extent.combineExtentWith(rectangle)
    if config.get('extent'):
        extent=QgsCoordinateTransform(QgsCoordinateReferenceSystem(4326),crs,project).transformBoundingBox(QgsRectangle(*config['extent']))
    extent.scale(1.04);main.zoomToExtent(extent);main.setFrameEnabled(True);main.setFrameStrokeColor(QColor('#b5c4c7'))
    main.setBackgroundColor(QColor('#e5edf1'))
    add_label(layout,'title',config.get('title','地图'),14*sx,12*sy,269*sx,14*sy,20)
    add_label(layout,'subtitle',config.get('subtitle',''),14*sx,28*sy,269*sx,10*sy,9,'#64757c')
    add_label(layout,'source',config.get('source_note',''),14*sx,194*sy,269*sx,12*sy,7,'#64757c')
    if config.get('legend',True):
        legend=QgsLayoutItemLegend(layout);legend.setId('legend');legend.setTitle(config.get('legend_title') or focus.name())
        legend.setLinkedMap(main);legend.setAutoUpdateModel(False);legend.model().rootGroup().clear();legend.model().rootGroup().addLayer(focus)
        QgsLegendRenderer.setNodeLegendStyle(legend.model().rootGroup().findLayer(focus.id()),QgsLegendStyle.Hidden)
        legend.setStyleFont(QgsLegendStyle.Title,font(10));legend.setStyleFont(QgsLegendStyle.SymbolLabel,font(8));legend.setStyleFont(QgsLegendStyle.Subgroup,font(8))
        layout.addLayoutItem(legend)
        if config.get('legend_position')=='outside-right':legend.attemptMove(QgsLayoutPoint(229*sx,47*sy))
        else:
            px,py=position(config.get('legend_position','bottom-right'),28,32)
            legend.attemptMove(QgsLayoutPoint(main.pos().x()+main.sizeWithUnits().width()*px/100,main.pos().y()+main.sizeWithUnits().height()*py/100))
    if config.get('north_arrow',True):
        svg=folder/'north.svg';svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="30" height="70" viewBox="0 0 30 70"><text x="15" y="13" text-anchor="middle" font-size="13" font-family="Arial">N</text><path d="M15 20 L5 44 L13 40 L13 66 L17 66 L17 40 L25 44Z" fill="#263b43"/></svg>')
        arrow=QgsLayoutItemPicture(layout);arrow.setId('north_arrow');layout.addLayoutItem(arrow)
        arrow.attemptResize(QgsLayoutSize(8*sx,19*sy));arrow.setPicturePath(str(svg));arrow.setLinkedMap(main);arrow.setNorthMode(QgsLayoutItemPicture.TrueNorth)
        px,py=position(config.get('north_position','top-right'),8,20)
        arrow.attemptMove(QgsLayoutPoint(main.pos().x()+main.sizeWithUnits().width()*px/100,main.pos().y()+main.sizeWithUnits().height()*py/100))
    if config.get('scale_bar',True):
        scale=QgsLayoutItemScaleBar(layout);scale.setId('scale_bar');scale.setStyle('Single Box');scale.setLinkedMap(main);scale.applyDefaultSize()
        scale.setUnits(Qgis.DistanceUnit.Kilometers);scale.setUnitLabel('km');scale.setNumberOfSegments(2);scale.setNumberOfSegmentsLeft(0);scale.setFont(font(7))
        km=extent.width()/1000*.10;power=10**math.floor(math.log10(max(km,.001)));segment=max(x*power for x in [1,2,5] if x*power<=km)
        scale.setUnitsPerSegment(segment);layout.addLayoutItem(scale)
        px,py=position(config.get('scale_position','bottom-left'),25,10)
        scale.attemptMove(QgsLayoutPoint(main.pos().x()+main.sizeWithUnits().width()*px/100,main.pos().y()+main.sizeWithUnits().height()*py/100))
    if config.get('grid',False):
        grid=main.grid();grid.setEnabled(True);grid.setCrs(QgsCoordinateReferenceSystem(4326))
        geo=QgsCoordinateTransform(crs,QgsCoordinateReferenceSystem(4326),project).transformBoundingBox(extent)
        grid.setIntervalX(.1 if geo.width()<1 else 2);grid.setIntervalY(.1 if geo.height()<1 else 1)
        grid.setAnnotationEnabled(True);grid.setAnnotationFormat(QgsLayoutItemMapGrid.DecimalWithSuffix);grid.setAnnotationPrecision(1);grid.setAnnotationFont(font(7))
        grid.setLineSymbol(QgsLineSymbol.createSimple({'line_color':'130,150,155,80','line_width':'.08'}))
        grid.setAnnotationFontColor(QColor('#64757c'))
        grid.setAnnotationDisplay(QgsLayoutItemMapGrid.LongitudeOnly,QgsLayoutItemMapGrid.Bottom)
        grid.setAnnotationDisplay(QgsLayoutItemMapGrid.LatitudeOnly,QgsLayoutItemMapGrid.Left)
        grid.setAnnotationDisplay(QgsLayoutItemMapGrid.HideAll,QgsLayoutItemMapGrid.Top)
        grid.setAnnotationDisplay(QgsLayoutItemMapGrid.HideAll,QgsLayoutItemMapGrid.Right)
    context_id=config.get('context_layer_id')
    if context_id in loaded:
        inset=QgsLayoutItemMap(layout);inset.setId('overview_map');layout.addLayoutItem(inset);inset.setCrs(QgsCoordinateReferenceSystem(4326))
        context=loaded[context_id].clone();context.setName('Overview context');context.setLabelsEnabled(False)
        context.setRenderer(QgsSingleSymbolRenderer(QgsFillSymbol.createSimple({'color':'#e7ede7','outline_color':'#a7b7af','outline_width':'.10'})))
        project.addMapLayer(context)
        inset.setLayers([context]);inset.setKeepLayerSet(True);inset.attemptMove(QgsLayoutPoint(228*sx,143*sy));inset.attemptResize(QgsLayoutSize(52*sx,37*sy))
        context_extent=QgsCoordinateTransform(context.crs(),inset.crs(),project).transformBoundingBox(context.extent());context_extent.scale(1.12);inset.zoomToExtent(context_extent)
        overview=inset.overviews().addOverview(QgsLayoutItemMapOverview('AOI',inset));inset.overviews().overview(0).setLinkedMap(main)
        add_label(layout,'overview_title','区域位置',228*sx,134*sy,52*sx,8*sy,8)
    items={x.id():x for x in layout.items() if isinstance(x,QgsLayoutItem) and x.id()}
    if request.get('template'):
        document=QDomDocument();document.setContent(Path(request['template']['path']).read_text())
        xml=document.toString()
        for backend_id,old_id in request['template'].get('bindings',{}).items():
            if backend_id in bindings:xml=xml.replace(old_id,bindings[backend_id])
        document.setContent(xml);rw=QgsReadWriteContext();rw.setPathResolver(QgsPathResolver(str(Path(request['template']['path']).parent/'project.qgz')))
        layout.loadFromTemplate(document,rw,True)
        items={x.id():x for x in layout.items() if isinstance(x,QgsLayoutItem) and x.id()}
        if isinstance(items.get('main_map'),QgsLayoutItemMap):items['main_map'].setLayers(main_layers)
    for id,spec in config.get('items',{}).items():
        item=items.get(id)
        if not item:
            if spec.get('kind')=='label':item=add_label(layout,id,spec.get('text','文本'),10,10,50,10,10)
            elif spec.get('kind')=='shape':
                item=QgsLayoutItemShape(layout);item.setId(id);layout.addLayoutItem(item)
            elif spec.get('kind')=='map':
                item=QgsLayoutItemMap(layout);item.setId(id);layout.addLayoutItem(item);item.setCrs(crs)
                item.setLayers(main_layers);item.setKeepLayerSet(True);item.zoomToExtent(extent)
            elif spec.get('kind')=='legend':
                item=QgsLayoutItemLegend(layout);item.setId(id);layout.addLayoutItem(item)
                item.setLinkedMap(main);item.setTitle(spec.get('title',config.get('legend_title') or '图例'))
                item.setAutoUpdateModel(False);item.model().rootGroup().clear();item.model().rootGroup().addLayer(focus)
            elif spec.get('kind')=='scale':
                item=QgsLayoutItemScaleBar(layout);item.setId(id);layout.addLayoutItem(item)
                item.setLinkedMap(main);item.setStyle('Single Box');item.applyDefaultSize();item.setFont(font(7))
            elif spec.get('kind')=='picture':
                item=QgsLayoutItemPicture(layout);item.setId(id);layout.addLayoutItem(item)
                if spec.get('picture_path'):
                    picture=Path(spec['picture_path']);assets=folder/'assets';assets.mkdir(exist_ok=True)
                    target=assets/picture.name;shutil.copy2(picture,target);item.setPicturePath(str(target))
                else:
                    svg=folder/'north.svg'
                    if not svg.exists():svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="30" height="70"><text x="15" y="14" text-anchor="middle">N</text><path d="M15 20L5 42L13 38L13 65L17 65L17 38L25 42Z"/></svg>')
                    item.setPicturePath(str(svg));item.setLinkedMap(main);item.setNorthMode(QgsLayoutItemPicture.TrueNorth)
            else:continue
            items[id]=item
        if 'x' in spec or 'y' in spec:item.attemptMove(QgsLayoutPoint(float(spec.get('x',item.pos().x())),float(spec.get('y',item.pos().y()))))
        if 'width' in spec or 'height' in spec:
            if isinstance(item,QgsLayoutItemLegend):item.setResizeToContents(False)
            item.attemptResize(QgsLayoutSize(float(spec.get('width',item.sizeWithUnits().width())),float(spec.get('height',item.sizeWithUnits().height()))))
        if 'rotation' in spec:item.setItemRotation(float(spec['rotation']))
        if 'visible' in spec:item.setVisibility(bool(spec['visible']))
        if 'locked' in spec:item.setLocked(bool(spec['locked']))
        if 'z' in spec:item.setZValue(float(spec['z']))
        if isinstance(item,QgsLayoutItemMap):
            if spec.get('layer_ids'):item.setLayers([loaded[x] for x in spec['layer_ids'] if x in loaded])
            if spec.get('map_extent'):item.zoomToExtent(QgsRectangle(*spec['map_extent']))
        if isinstance(item,QgsLayoutItemLegend) and 'title' in spec:item.setTitle(spec['title'])
        if isinstance(item,QgsLayoutItemShape):
            item.setSymbol(QgsFillSymbol.createSimple({'color':spec.get('fill','#ffffff'),'outline_color':spec.get('color',INK),'outline_width':'.25'}))
        if isinstance(item,QgsLayoutItemLabel):
            if 'text' in spec:item.setText(spec['text'])
            if 'font_size' in spec:item.setFont(font(float(spec['font_size'])))
            if 'color' in spec:item.setFontColor(QColor(spec['color']))
    layout.refresh()
    # Native legends and scale bars calculate their final bounds during the first paint.
    QgsLayoutExporter(layout).renderPageToImage(0,QSize(),40)
    project.layoutManager().addLayout(layout)
    project.setFilePathStorage(Qgis.FilePathType.Relative)
    project.setCustomVariables({'geoagent_layer_map':json.dumps(bindings),'geoagent_layout':json.dumps(config)})
    project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(extent,crs))
    for backend_id,layer in loaded.items():layer.saveNamedStyle(str(styles/(backend_id+'.qml')))
    project_path=folder/'project.qgz';project.setFileName(str(project_path))
    if not project.write():raise ValueError('QGIS 工程保存失败。')
    template=folder/'layout.qpt';layout.saveAsTemplate(str(template),QgsReadWriteContext())
    bundle=out/'qgis-project.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in folder.rglob('*'):
            if path.is_file():archive.write(path,str(path.relative_to(folder)))
    answer={'project':str(project_path),'template':str(template),'bundle':str(bundle),'bindings':bindings,'qgis_version':Qgis.QGIS_VERSION}
    exporter=QgsLayoutExporter(layout)
    if request['operation']=='render':
        fmt=request.get('format','pdf');destination=out/('map.'+fmt)
        if fmt=='pdf':
            settings=QgsLayoutExporter.PdfExportSettings();settings.dpi=request.get('dpi',150);result=exporter.exportToPdf(str(destination),settings)
        elif fmt=='svg':
            settings=QgsLayoutExporter.SvgExportSettings();settings.dpi=request.get('dpi',150);result=exporter.exportToSvg(str(destination),settings)
        else:
            settings=QgsLayoutExporter.ImageExportSettings();settings.dpi=request.get('dpi',150);result=exporter.exportToImage(str(destination),settings)
        if result!=QgsLayoutExporter.Success:raise ValueError('QGIS 导出失败：'+str(result))
        answer['rendered_path']=str(destination)
    scene=[]
    page=layout.pageCollection().pages()[0]
    page.setVisibility(False)
    visible={id:item.isVisible() for id,item in items.items()}
    for item in items.values():item.setVisibility(False)
    tiles=out/'elements';tiles.mkdir(exist_ok=True)
    for id,item in items.items():
        item.setVisibility(True)
        rotation=item.itemRotation();item.setItemRotation(0)
        rect=item.sceneBoundingRect();image=exporter.renderRegionToImage(rect,QSize(),130)
        target=tiles/(id+'.png');image.save(str(target),'PNG');item.setVisibility(False)
        kind='map' if isinstance(item,QgsLayoutItemMap) else 'label' if isinstance(item,QgsLayoutItemLabel) else 'legend' if isinstance(item,QgsLayoutItemLegend) else 'scale' if isinstance(item,QgsLayoutItemScaleBar) else 'picture' if isinstance(item,QgsLayoutItemPicture) else 'shape'
        entry={'id':id,'kind':kind,'label':id,'x':item.pos().x(),'y':item.pos().y(),'width':item.sizeWithUnits().width(),'height':item.sizeWithUnits().height(),
               'rotation':rotation,'z':item.zValue(),'visible':visible[id],'locked':item.isLocked(),'image_path':str(target)}
        item.setItemRotation(rotation)
        if kind=='label':entry.update(text=item.text(),font_size=item.font().pointSizeF(),color=item.fontColor().name())
        if kind=='map':
            e=item.extent();entry.update(map_extent=[e.xMinimum(),e.yMinimum(),e.xMaximum(),e.yMaximum()],map_crs=item.crs().authid())
        scene.append(entry)
    for id,item in items.items():item.setVisibility(visible[id])
    page.setVisibility(True)
    answer['scene']={'width':width,'height':height,'units':'mm','elements':scene}
    return answer
