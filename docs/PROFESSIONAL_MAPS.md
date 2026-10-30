# 真实公开数据与专业制图模板

2026-10-30 实际下载、导入、计算、出图并以 Poppler 复核 PDF。样例由本项目的 Python 制图模板生成，当时尚未调用 QGIS；2026-10-31 已追加下方的原生 QGIS 版本。

## 数据来源

| 数据 | 来源 | 交付样例 |
| --- | --- | --- |
| 华盛顿州 39 个县 | [Census 2024 Cartographic Boundary Files](https://www.census.gov/geographies/mapping-files/2024/geo/carto-boundary-file.html) · 从全国 1:500,000 县界中按 STATEFP=53 提取 | SHP 配套文件 ZIP，227,980 字节，EPSG:4269 |
| 雷尼尔山高程 | [USGS 3DEP 高程服务](https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer) · 以 None 栅格函数导出实际高程 | GeoTIFF，4,195,937 字节，1000×1000，EPSG:32610 |

SHP 保留 Census 原始属性。专题值为 ALAND / 1,000,000，单位 km²；没有生成虚构人口。
DEM 是动态多分辨率高程服务按研究区裁切并双线性重采样的结果，像元约 33.84 m，不是原生 1 m / 10 m DEM 瓦片，也不代表新的高程调查或精确峰顶高程。
下载参数、时间、文件 SHA-256、源服务响应在 `outputs/public-cartography/sources.json` 和 `raw/` 中保留。

## 实际地图

- `washington-counties.pdf / .png`：39 县陆地面积五级分位数设色，EPSG:5070，县名标注避让、坐标格网、真北方向指示、地面距离比例尺、数据源与指标口径。
- `rainier-terrain.pdf / .png`：EPSG:32610，分层设色、315° / 45° 山体阴影、200 m 等高线、1000 m 计曲线、连续高程图例和区域定位插图；垂直夸张为 1。
- 纸张 A4 横向，PNG 为 300 DPI；PDF 保留矢量线、文字和版面，地形以影像嵌入。已将 PDF 独立渲染为 PNG 检查字形、遮挡、图例和留白。

## 使用与复现

```bash
.venv/bin/python scripts/fetch_public_samples.py
.venv/bin/python scripts/render_public_maps.py
# 可选：把样例与成果加入当前本地工作台；会追加3层并改变当前制图布局
.venv/bin/python scripts/publish_public_demo.py
```

第一次下载全国县界约 11.6 MB；提供给用户的州级子集只有约 223 KiB。运行后文件在 `outputs/public-cartography/`，原始样例、导出成果和临时工作区不进入 Git。

在工作台“制图布局”选择“专业分级专题图”或“专业地形图”，指定主图层与出图投影。专题图需要先给图层指定数值设色字段；地形模板需要单波段、米制高程 DEM。当前专业模板支持 A4 / A3 横向。
`update_layout` 工具新增 `template`、`focus_layer_id`、`map_crs`、`legend_title`、`contour_interval`、`context_layer_id`。图例可放 `outside-right`；指北针与比例尺支持四角。复杂自然语言交互仍需要连接模型。
例如已有地形布局时，离线明确命令“把指北针放到左上角，导出 PDF”也会使用同一专业渲染器。

## 达到 ArcGIS 专业制图深度的路线

建议主路线是 [QGIS / PyQGIS 原生印刷布局](https://docs.qgis.org/3.44/en/docs/pyqgis_developer_cookbook/composer.html)：以 QPT 保存布局，复用图层样式和注记规则，通过 QgsPrintLayout / QgsLayoutExporter 出图，并利用 Atlas 批量制图。
已有 ArcGIS Pro 运行环境和许可时，可通过 [arcpy.mp Layout](https://doc.esri.com/en/arcgis-pro/latest/arcpy/mapping/layout-class.html) 自动化现有工程和布局；独立脚本也需要满足 [ArcGIS Pro 的授权条件](https://doc.esri.com/en/arcgis-pro/latest/arcpy/get-started/installing-python-for-arcgis-pro.html)。

Agent 应把语言转换成有约束的制图规格：投影、主图层、字段与单位、分级方法、色带、标注规则、毫米位置、纸张、比例尺和输出格式。渲染应交给确定性引擎；随后检查投影与范围、比例尺地面误差、图例与实际字段、缺失字体、注记遮挡和裁切。
早期 Python 模板不包含完整符号和 PAL 注记。新增 QGIS 插件现使用原生渲染/PAL、可编辑多地图框及工程保存重开；地图集、完整色彩管理和桌面级工程编辑仍未实现。不能用两张样例证明已经等同于 ArcGIS。

## 原生 QGIS 版本

本轮已实际安装 QGIS 3.44.14 并通过插件调用。`scripts/render_native_public_maps.py` 生成 `qgis-washington` 和 `qgis-rainier` 的 PNG/PDF/SVG，以及含相对路径数据、QGZ、QPT、QML 的工程 ZIP；前面的 Python 版本保留作对照。当前原生输出已用 Poppler 独立渲染检查。
