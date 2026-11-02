"""Explicit offline cartography commands. Model mode uses the same validated tools."""
import re

FONT_ALIASES={'苹方':'PingFang SC','冬青':'Hiragino Sans GB','微软雅黑 UI':'Microsoft YaHei UI',
              '微软雅黑':'Microsoft YaHei','宋体':'Songti SC','思源黑体':'Noto Sans CJK SC','思源宋体':'Noto Serif CJK SC'}

def parse_style_commands(text,fonts=()):
    changes={};items={};target=None
    available={f['family'] for f in fonts}
    for clause in re.split(r'[，,。；;\n]',text):
        match=re.search(r'副标题|标题|来源说明|图例|比例尺|指北针|全图字体|地图字体|所有文字',clause)
        if match:
            target={'副标题':'subtitle','标题':'title','来源说明':'source','图例':'legend','比例尺':'scale_bar','指北针':'north_arrow'}.get(match.group())
        element={}
        if '指北针' in clause:
            for words,value in [('罗盘|玫瑰','rose'),('双色|三角','triangle'),('极简|线形','minimal'),('经典|箭头','arrow')]:
                if re.search(words,clause):element['north_style']=value;break
        if target=='scale_bar':
            for words,value in [('双线框','Double Box'),('单线框','Single Box'),('中线刻度','Line Ticks Middle'),('下方刻度','Line Ticks Down'),('上方刻度','Line Ticks Up'),('阶梯','stepped'),('空心','hollow'),('数字比例','Numeric')]:
                if re.search(words,clause):element['scale_style']=value;break
            units=re.search(r'(?:单位|显示为|使用|用)\s*(千米|公里|km|米|m)(?![a-z])',clause,re.I)
            if units:element['scale_units']='km' if units.group(1).lower() in ('千米','公里','km') else 'm'
            segments=re.search(r'(?:分成|分段数|分段|分)\s*(\d+)\s*段?',clause)
            if segments:element['scale_segments']=int(segments.group(1))
        if re.search(r'高程|色带|地形',clause):
            for words,value in [('蓝绿','bluegreen'),('柔和|绿棕','earth'),('viridis','viridis'),('灰度','gray'),('经典','terrain')]:
                if re.search(words,clause,re.I):changes['terrain_palette']=value;break
            if '反转' in clause:changes['terrain_reverse']=not bool(re.search(r'不反转|取消反转',clause))
        for label,key in [('山体阴影','terrain_hillshade'),('等高线','terrain_contours')]:
            if label in clause and re.search(r'隐藏|关闭|取消|不显示|显示|开启|打开',clause):changes[key]=not bool(re.search(r'隐藏|关闭|取消|不显示',clause))
        interval=re.search(r'等高距\s*(?:改为|改成|设为|为|用)?\s*(\d+(?:\.\d+)?)',clause)
        if interval:changes['contour_interval']=float(interval.group(1))
        precision=re.search(r'(?:图例|高程).*?(?:保留|小数位)\s*(\d+)\s*位?',clause)
        if precision:changes['legend_precision']=int(precision.group(1))
        font=None
        for alias,family in sorted(FONT_ALIASES.items(),key=lambda p:-len(p[0])):
            if alias in clause:
                # Use the installed cross-platform equivalent for Chinese serif/sans aliases.
                choices=([family,'SimSun','Noto Serif CJK SC','Noto Serif SC','Source Han Serif SC'] if alias=='宋体' else
                         [family,'Noto Sans SC','Source Han Sans SC'] if alias=='思源黑体' else [family])
                font=next((f for f in choices if f in available),None)
                if not font:raise ValueError('本机未安装'+alias+'，请从布局字体目录选择可用字体。')
                break
        if font is None:
            font=next((f for f in sorted(available,key=len,reverse=True) if f.lower() in clause.lower()),None)
        if '自动字体' in clause:font='auto'
        if font:
            if target in ('title','subtitle','source','legend','scale_bar'):element['font_family']=font
            else:changes['font_family']=font
        if target in ('title','subtitle','source','legend','scale_bar'):
            size=re.search(r'字号\s*(?:改为|改成|设为|为)?\s*(\d+(?:\.\d+)?)',clause)
            if size:element['font_size']=float(size.group(1))
            if '加粗' in clause or '粗体' in clause:element['font_weight']=400 if re.search(r'不加粗|取消加粗|取消粗体',clause) else 700
            if '半粗' in clause:element['font_weight']=600
            if re.search(r'常规字重|正常字重',clause):element['font_weight']=400
            if target in ('title','subtitle','source') and '斜体' in clause:element['italic']=not bool(re.search(r'不斜体|取消斜体',clause))
        color=re.search(r'#[0-9a-fA-F]{6}',clause)
        if color and target:element['north_color' if target=='north_arrow' else 'color']=color.group()
        if element and target:items.setdefault(target,{}).update(element)
    return changes,items
