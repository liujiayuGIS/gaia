# GeoAgent v0.1

本地 GIS Agent 原型。React + MapLibre 前端，FastAPI + Shapely + PyProj 后端。
前端交互参考 OpenGIS 的地图、图层和对话工作台；代码为本项目独立实现。

## 启动

需要 Python 3.12+、Node.js 20.19+ / 22.12+。

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock.txt
cd frontend
npm ci --ignore-scripts
npm run build
cd ..
./start.sh
```

打开 <http://127.0.0.1:8765>。已安装依赖的目录可直接运行 `./start.sh`。
只监听本机回环地址；第一版是单用户本地工作台。

## 试用完整流程

1. 点击“载入示例”。站点、公园和道路都是固定种子生成的合成数据，不代表真实设施。
2. 输入“统计地铁站 800 米直线范围内的公园数量”。
3. 查看生成的缓冲区、按 `poi_count` 设色的统计图层和属性表。
4. 展开对话中的工具记录；导出 GeoJSON、属性 CSV 或运行 JSON。
5. 刷新页面后数据和运行历史仍在本地；点击“运行记录”可查看历史。

可以导入 UTF-8 GeoJSON FeatureCollection 或带 lon/lat、longitude/latitude、经度/纬度、x/y 的 CSV。
上传时填写真实输入 EPSG 坐标系，后台转换为 EPSG:4326。GeoJSON 默认按 RFC 7946 / WGS84 经度、纬度解释。
文件限 12 MB / 20,000 要素。拒绝无效、空、非二维或超出地图范围的几何；不自动猜测坐标系或修复几何。
GCJ-02 / BD-09 需预先纠偏。缓冲只支持 2000 个以内 Point、城市尺度（经纬度跨度各 ≤ 6°、纬度 ±80°），半径 0–20 km（不含 0）。

## 两种运行模式

- **离线指令模式**：基于规则的有限命令解析，无模型调用。支持列图层、检查选中图层、明确距离的点缓冲和 POI 统计。遇到歧义会要求明确图层或距离。
- **模型模式**：在“模型设置”中填写兼容 Chat Completions、支持 tool calling 的 API 根地址、模型名和密钥。可用 DeepSeek 或兼容服务。

密钥只保留在页面内存，通过同源请求发送给后端；或在启动前设置 `GIS_LLM_API_KEY`。
密钥不写入运行记录或浏览器存储。模型收到任务、图层摘要、检查工具的属性样本和工具结果；完整空间文件不发给模型。
模型循环最多 10 轮、每轮最多 8 个调用；时间预算在轮间检查，网络调用有独立超时。
“停止”在当前工具 / HTTP 调用结束后生效；保留已完成产物，不回滚。
真实供应商连通性需要你提供有效凭据后验证；“测试连接”会显式发起一次短请求，验证所填模型与工具参数。此请求可能产生少量 API 用量，不读取地理数据。
OpenAI 使用 max_completion_tokens；推理模型不强制温度。GPT-5.6 Sol 在当前 Chat Completions 工具路径使用 reasoning_effort=none（非推理模式）；保留推理能力需要后续接入 Responses API。
错误诊断会显示服务商错误码、参数与说明，密钥先脱敏再展示和记录。

## Harness

- `backend/geoagent/harness.py`：类型化工具注册、执行前检查钩子、权限事件、错误反馈、工具结果、有限模型循环、取消。
- `provider.py`：模型参数适配、连接测试和密钥脱敏的服务错误诊断。
- `gis.py`：确定性空间处理与结果检查；分析输入必须先在同次运行中检查。
- `store.py`：SQLite 元数据与追加事件；GeoJSON 产物不可变，以 SHA-256 标识。
- `app.py`：上传、图层、导出、任务和静态前端 API。
- `frontend/src/main.jsx`：图层列表、MapLibre 地图、属性表、对话、模型设置与历史。

第一版使用独立轻量循环，未引入 LangGraph 或 DeepSeek Harness 依赖。工具 / 模型 / 存储边界独立，方便后续替换运行时。
只允许已注册的工作区工具，无任意 Python / Shell 执行。支持工作区级单运行，避免多个模型任务并发写入。
重启会把未完成任务标记为 interrupted；不自动重试，不宣称精确断点续算。

## 空间方法与校验

- 缓冲：以每个输入点为中心建立 WGS84 AEQD 投影，按米生成 256 段多边形，再转换到 WGS84。
- 独立校验：使用 `Geod.inv` 检查中心到边界顶点的椭球距离，误差上限 0.05 m；这是顶点误差，边之间仍有多边形近似误差。
- 统计：Shapely STRtree + `covers`，包含多边形边界上的点；每个范围单独计数，重叠范围会重复统计同一点。
- 检查几何有效、数量约束与非负整数统计；这些规则不等价于证明用户的研究方法正确。
- 每次产物保留输入哈希、输入图层 ID、工具、方法、参数、运行 ID 和局限。
- 地图显示本地几何，无在线底图和瓦片依赖。样式与分析来源可在“数据详情”查看。

## 验证与开发

```bash
.venv/bin/python -m pytest -q
cd frontend && npm run build
```

开发时可在两个终端运行：

```bash
PYTHONPATH=backend .venv/bin/python -m uvicorn geoagent.app:app --host 127.0.0.1 --port 8765
cd frontend && npm run dev
```

开发页面在 Vite 输出的地址，`/api` 代理到 8765。
本次验证：27 项后端测试通过；浏览器端到端覆盖示例加载、统计上图、CSV 导出、密钥不落盘、刷新恢复、历史查看、上传和手机宽度。

浏览器端到端检查脚本见 `scripts/browser-test.cjs`，需要可用的 Playwright 和 Chromium。

## 后续范围

GeoPackage / Shapefile、栅格、路网服务区、QGIS Processing、可恢复作业执行、独立基准测试和多用户部署均待实现。
图层只能追加；本版没有删除 / 撤销、地图布局导出、自动数据下载和跨进程作业调度。
研究用制图需另行完善出版级图例、地图布局与导出排版。

## 架构参考

- [OpenGIS](https://github.com/ATFfang/OpenGIS)：地图 / 图层 / 对话的工作台交互。
- [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)：插件边界、执行流水线和事件记录理念。
- [LangGraph](https://github.com/langchain-ai/langgraph)：后续检查点和状态编排的候选。

本项目未复制上述项目的源码、图标或截图。依赖许可由对应上游包提供。
