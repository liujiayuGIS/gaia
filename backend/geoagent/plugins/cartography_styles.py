"""Shared style catalog for the API, language tools and native print worker."""
import re

TERRAIN_PALETTES={
 'terrain':{'label':'经典地形','colors':['#536d50','#829e69','#bacb92','#e3d5a3','#c1a781','#aa8978','#d3c6bb','#f8f6f0']},
 'earth':{'label':'柔和绿棕','colors':['#edf4e3','#b8d5a3','#7ea574','#b8b184','#c5aa80','#a58269','#ede5d8']},
 'bluegreen':{'label':'蓝绿高程','colors':['#173f5f','#237c93','#55aaa4','#a6d3b7','#e5edcb','#fff4d3']},
 'viridis':{'label':'Viridis','colors':['#440154','#414487','#2a788e','#22a884','#7ad151','#fde725']},
 'gray':{'label':'灰度','colors':['#313841','#68737d','#a3adb4','#d7dde0','#fafafa']},
}
NORTH_STYLES={'arrow':'经典箭头','triangle':'双色三角','rose':'罗盘玫瑰','minimal':'极简线形'}
SCALE_STYLES={'Single Box':'单线框','Double Box':'双线框','Line Ticks Middle':'中线刻度','Line Ticks Down':'下方刻度','Line Ticks Up':'上方刻度','stepped':'阶梯线','hollow':'空心分段','Numeric':'数字比例'}
FONT_LABELS={'PingFang SC':'苹方（简体）','Songti SC':'宋体（简体）','Hiragino Sans GB':'冬青黑体','Microsoft YaHei UI':'微软雅黑 UI','Microsoft YaHei':'微软雅黑','SimSun':'宋体','Noto Sans CJK SC':'思源黑体 / Noto Sans CJK','Noto Sans SC':'Noto Sans SC','Noto Serif CJK SC':'思源宋体 / Noto Serif CJK','Noto Serif SC':'Noto Serif SC','Source Han Sans SC':'思源黑体','Source Han Serif SC':'思源宋体','Arial Unicode MS':'Arial Unicode'}
PREFERRED_FONTS=['PingFang SC','Microsoft YaHei UI','Microsoft YaHei','Noto Sans CJK SC','Noto Sans SC','Source Han Sans SC','Hiragino Sans GB','Arial Unicode MS','DejaVu Sans']

def catalog():
 return {'north_styles':[{'id':k,'label':v,'svg':north_svg(k)} for k,v in NORTH_STYLES.items()],
         'scale_styles':[{'id':k,'label':v} for k,v in SCALE_STYLES.items()],
         'terrain_palettes':[{'id':k,**v} for k,v in TERRAIN_PALETTES.items()],
         'scale_units':[{'id':'km','label':'千米'},{'id':'m','label':'米'}],
         'font_weights':[400,500,600,700],'renderer':'qgis','fonts':[]}

def validate_item_style(item):
 for key,choices in [('north_style',NORTH_STYLES),('scale_style',SCALE_STYLES),('scale_units',{'km','m'})]:
  if key in item and item[key] not in choices:raise ValueError('不支持的样式参数：'+key)
 for key,lo,hi in [('scale_segments',1,10),('legend_columns',1,4)]:
  if key in item and (isinstance(item[key],bool) or not isinstance(item[key],int) or not lo<=item[key]<=hi):raise ValueError(key+' 超出范围。')
 if 'font_weight' in item and item['font_weight'] not in (400,500,600,700):raise ValueError('字体字重支持400/500/600/700。')
 if 'font_family' in item and (not isinstance(item['font_family'],str) or not 1<=len(item['font_family'])<=100 or re.search(r'[\x00-\x1f<>/\\]',item['font_family'])):raise ValueError('字体名称无效。')
 for key in ('color','north_color'):
  if key in item and not re.fullmatch(r'#[0-9a-fA-F]{6}',str(item[key])):raise ValueError('颜色必须使用 #RRGGBB。')
 if 'italic' in item and not isinstance(item['italic'],bool):raise ValueError('italic 必须为布尔值。')

def north_svg(style='arrow',color='#263b43'):
 validate_item_style({'north_style':style,'north_color':color})
 bodies={
  'arrow':'<path d="M20 21L8 48L17 43V68H23V43L32 48Z" fill="{c}"/>',
  'triangle':'<path d="M20 22L6 68L20 59Z" fill="{c}"/><path d="M20 22L34 68L20 59Z" fill="white" stroke="{c}" stroke-width="1.4"/>',
  'minimal':'<path d="M20 67V24M10 40L20 24L30 40" fill="none" stroke="{c}" stroke-width="2.4"/>',
  'rose':'<path d="M20 21L24 43L37 48L24 52L20 73L16 52L3 48L16 43Z" fill="white" stroke="{c}" stroke-width="1.1"/><path d="M20 21V48L16 43ZM37 48H20L24 43ZM20 73V48L24 52ZM3 48H20L16 52Z" fill="{c}"/><circle cx="20" cy="48" r="2" fill="{c}"/>',
 }
 return '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="78" viewBox="0 0 40 78"><text x="20" y="15" text-anchor="middle" font-family="sans-serif" font-size="14" fill="'+color+'">N</text>'+bodies[style].format(c=color)+'</svg>'
