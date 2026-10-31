"""Collect actual native layout and labeling evidence, inside the QGIS worker."""
from pathlib import Path
from qgis.core import (QgsLayoutItemMap,QgsLayoutItemLabel,QgsLayoutItemLegend,
                       QgsLayoutItemScaleBar,QgsLayoutItemPicture,QgsLayoutExporter)


def capture(layout,items,exporter,out,dpi):
    page=layout.pageCollection().pages()[0].pageSize()
    result={'width':page.width(),'height':page.height(),'units':'mm','elements':[],
            'label_maps':[],'labeling_available':False,'labeling_dpi':dpi,'preview_dpi':120}
    # Request a real raster export so labelingResults is populated, including project previews.
    settings=QgsLayoutExporter.ImageExportSettings();settings.dpi=120
    preview=Path(out)/'audit-preview.png'
    if exporter.exportToImage(str(preview),settings)!=QgsLayoutExporter.Success:
        raise ValueError('审图预览生成失败。')
    result['preview_path']=str(preview);result['labeling_dpi']=120
    for id,item in items.items():
        rect=item.sceneBoundingRect()
        kind='map' if isinstance(item,QgsLayoutItemMap) else 'label' if isinstance(item,QgsLayoutItemLabel) else 'legend' if isinstance(item,QgsLayoutItemLegend) else 'scale' if isinstance(item,QgsLayoutItemScaleBar) else 'picture' if isinstance(item,QgsLayoutItemPicture) else 'shape'
        value={'id':id,'uuid':item.uuid(),'kind':kind,'visible':item.isVisible(),
               'bounds':[rect.left(),rect.top(),rect.right(),rect.bottom()],'rotation':item.itemRotation()}
        if kind=='label':
            required=item.sizeForText()
            value.update(text=item.currentText(),font_size=item.font().pointSizeF(),required_size=[required.width(),required.height()],
                         size=[item.sizeWithUnits().width(),item.sizeWithUnits().height()])
        if kind=='map':
            value.update(map_layers=[x.id() for x in item.layers()],layer_names=[x.name() for x in item.layers()],crs=item.crs().authid(),scale=item.scale(),map_rotation=item.mapRotation())
            value['legend_exemptions']=[{'layer_id':x.id(),'reason':str(x.customProperty('gaia/legend_exempt_reason'))}
                                       for x in item.layers() if x.customProperty('gaia/legend_exempt_reason','')]
        if kind in ('legend','scale','picture'):
            linked=item.linkedMap();value['linked_map']=linked.uuid() if linked else None
        if kind=='legend':value['legend_layers']=[x.layerId() for x in item.model().rootGroup().findLayers()]
        if kind=='scale':value.update(units_per_segment=item.unitsPerSegment(),segments=item.numberOfSegments(),unit_label=item.unitLabel())
        if kind=='picture' and id=='north_arrow':value.update(north_mode=int(item.northMode()),picture_rotation=item.pictureRotation())
        result['elements'].append(value)
    try:
        for uuid,labels in exporter.labelingResults().items():
            positions=labels.allLabels()
            result['label_maps'].append({'map_uuid':uuid,'total':len(positions),'truncated':len(positions)>1500,
                'labels':[{'text':p.labelText,'layer':p.layerID,'feature':int(p.featureId),'unplaced':p.isUnplaced,
                           'corners':[[x.x(),x.y()] for x in p.cornerPoints]} for p in positions[:1500]]})
        result['labeling_available']=True
    except Exception as exc:result['labeling_error']=str(exc)
    return result
