# GAIA · 桌面预览版 v0.5.0-beta.5

**Geospatial Artificial Intelligence Assistant · 地理空间人工智能助手盖亚**

自然语言驱动的本地 GIS 工作台：导入矢量与栅格、执行空间分析、把结果发布为新图层，并按语言要求制作地图。

当前分支包含 2026-11-02 的 **Atlas / Folio 界面升级**：地图上的浮动数据面板、独立助手、真实任务流程抽屉与原生出图工作区，0.5.0-beta.3 补齐中文 Shapefile 编码 / 截断字段名处理、可配置模型输出预算及 DeepSeek 推理工具链兼容；beta.4 继续补齐图层删除 / 恢复与可持久保存的助手拖动调宽，beta.5 增加消息复制、引用、编辑、只读重新回答、反馈与 Markdown 排版，正在同步桌面安装包。操作和验证见 [新版工作台说明](docs/ATLAS_WORKSPACE.md)，各平台安装验收记录见 [交付状态](docs/DESKTOP_STATUS.md)。

![GAIA workspace](screenshots/gaia-workspace.png)

这是可运行的插件与原生 QGIS 验收实现。目标是逐步覆盖桌面 GIS 工作流；**目前还不等同于 QGIS / ArcGIS 全量能力，也没有经过与其他 Agent 的同条件性能评测。**

## 桌面安装

[GitHub Releases 下载安装包](https://github.com/liujiayuGIS/gaia/releases)：面向 macOS Apple Silicon（macOS 15+）和 Windows x64；各版本可下载的包以 Release 实际文件为准；见 [交付状态](docs/DESKTOP_STATUS.md)。内置 Python 和 QGIS，首次启动在本机初始化环境，工作区独立保存。

**第一次使用请看 [GAIA 用户手册](docs/USER_GUIDE.md)**（[离线 HTML 版](https://github.com/liujiayuGIS/gaia/releases)）：从十分钟完成第一张地图开始，逐步学习模型配置、SHP / TIFF 导入、算法参数、图层排序、布局编辑、出图导出、审批恢复、记忆与代码工具。系统要求、签名状态、源码构建见 [桌面版说明](docs/DESKTOP.md)。

## 从源码启动

需要 Python 3.12、Node.js 22，以及支持 WebGL 的浏览器。

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.lock.txt
cd frontend
npm ci --ignore-scripts
npm run build
cd ..
./start.sh
```

打开 [本地工作台](http://127.0.0.1:8765)。已有依赖可直接运行 `./start.sh`。
应用只监听本机回环地址；工作区默认保存在 `.geoagent/`，不进入 Git。
可通过 `GEOAGENT_WORKSPACE` 指定独立工作区，通过 `PORT` 修改端口。
制图随附 Noto Sans CJK SC 中文字体，也可从实际字体目录选择系统已安装字体。

## 可以验收什么

- **持久 Harness**：LangGraph + SQLite 检查点、会话连续、工具回执复用、跨重启审批、恢复前输入/成果版本核对和统一验收。
- **五层记忆与工具沉淀**：工作上下文、执行状态、资产目录、显式偏好、FTS5 方法知识；代码配方经过执行验证和人工审核后成为类型化工具。详见 [v0.4 架构与边界](docs/HARNESS_V04.md)。
- **空间质量闭环**：执行前检查单位、几何、数据时间、人口含义与路网成本；执行后独立复算适用的叠加、计数、缓冲、栅格和路线结果；失败最多返工两轮。支持严格验收、数据语义版本绑定和可下载核验记录。[覆盖范围与限制](docs/SPATIAL_QUALITY.md)。
- **质量与审图**：点击“检查出图”检查实际 QGIS 版面与标注，应用出版版式；支持图像的模型可读取真实地图预览并记录视觉观察，和数值检查分别展示。

- **GAIA 工作区**：圆润的三栏数据/地图/常驻助手布局，独立聊天区、浅深主题、自定义强调色和地图背景。
- **QGIS 原生插件**：本机真实注册 440 个 Processing 算法，原生布局、工程、样式与 QPT 模板保存；通过插件 SDK 继续扩展其他应用。
- **Skills 与代码**：安装 SKILL.md 方法包，Harness 按任务读取和编排；Python/PyQGIS 沙箱代码生成新数据并保存可复用算法。

- **数据收件箱**：附件上传、多文件配套、ZIP / KMZ 解包、资源与子图层发现、自然语言导入、缺失 CRS 提示。
- **35 个确定性算法**：缓冲、裁剪、叠加、空间连接、最近邻、筛选、字段计算、网格、DBSCAN、IDW、热力密度、栅格计算、NDVI、地形分析、栅格转面、分区统计等。
- **结果自动入层**：每次分析保存新数据；原输入保留。支持空结果、属性表、样式、重命名、定位、数据导出和处理血缘。
- **图层绘制顺序**：拖动图层左侧手柄，或使用上移/下移按钮；聚焦手柄后可用方向键、Home / End 排序。列表上方优先显示，矢量与栅格共用持久顺序；刷新、常规出图及 QGIS 工程保存/重开保持顺序。连接模型后也可要求助手调整图层顺序。专题模板仍按其绑定的输入制图。
- **真实制图输出**：PNG / JPEG / TIFF / SVG / PDF；A4 / A3、横竖版、标题、指北针、图例、比例尺与角落位置。支持拖动、缩放、元素属性、地图范围、层级、锁定与撤销。预览和导出共用布局。
- **Responses API**：工具调用后原样回传 reasoning / function-call 项，保留加密推理上下文；可选择推理强度。兼容 Chat Completions。
- **可重放工作流**：模型可保存算法 DAG；执行时校验参数、检查输入、逐节点发布结果并保留执行凭据。

插件架构、运行边界及扩展方式见 [插件与 Skills](docs/PLUGINS_AND_SKILLS.md)。原生 QGIS 可通过 `bash scripts/install_qgis_runtime.sh` 安装（当前安装器为 macOS ARM64）；运行时不进入 Git。

完整目录和限制见 [能力与格式](docs/CAPABILITIES.md)，操作步骤见 [验收说明](docs/ACCEPTANCE.md)。

## 数据与自然语言

点击“添加地理数据”，或把附件交给右侧助手。Shapefile 同时上传 `.shp/.shx/.dbf/.prj` 或使用 ZIP；GeoPackage 可选择子图层；带地理参考的 TIFF 可直接入层。

```text
请检查并导入刚上传的 stations.zip
统计地铁站 800 米直线范围内的公园数量
计算 DEM 的坡度，把结果加入图层，再统计各分区的平均坡度
把指北针放到左上角，图例放到右下角，标题设为“研究区分析”，导出 PDF
将这套缓冲和统计步骤保存成工作流，下次用相同参数重放
```

复杂语义规划需要连接模型；**离线模式是有限规则解析**，支持明确的示例缓冲 / 计数、导入、布局调整和导出，不具备通用推理。算法工具箱和已保存工作流无需模型即可运行。
模型遇到多个输入、子图层或缺少坐标系时，应先询问，不自行猜测。

## 模型设置

在“模型设置”中选择“连接模型”，填写实际可用的模型名与 API Key。
OpenAI 根地址为 `https://api.openai.com/v1`，协议选“自动”或“Responses”。自动模式为官方 OpenAI 地址选择 Responses，其他兼容地址默认选择 Chat Completions；支持 Responses 的代理可手动指定。

密钥只保存在当前页面内存；刷新后需重新填写。也可在启动前设置 `GIS_LLM_API_KEY`。密钥不写入浏览器存储、运行记录或 Git。
模型接收任务、图层摘要、属性样本与工具结果；开启视觉审阅时还会发送地图 PNG 预览，可在模型设置关闭。完整地理文件留在本地。“测试连接”会发起一次短请求，可能产生 API 用量，不读取地理文件。

Responses 使用 `store: false` 和 `reasoning.encrypted_content`，工具循环与本地检查点保留供应商返回的不透明加密推理项，用于跨重启恢复；不展示隐藏思维文本。API Key 不进入检查点。界面展示计划、实际工具步骤、参数、验收和用量。
当前不是逐 token 流式显示；同会话问答持续衔接，中断任务可从检查点继续。重启服务后需要重新提供 API Key，或使用服务端环境变量。
真实供应商请求需要使用自己的有效凭据验收，模拟响应不能代替真实连通性。

## Harness 与实现

React + MapLibre / FastAPI + LangGraph + SQLite / GeoPandas + GDAL + Rasterio + Shapely + PyProj + Matplotlib。

```text
自然语言任务 / 手动算法 / 工作流
             ↓
模型适配 → 计划与工具发现 → 参数契约与输入检查
             ↓
确定性 GIS 执行 → 结果检查 → 独立数据与图层
             ↓
SQLite 事件 / 输入哈希 / 方法参数 / 布局与下载成果
```

- `provider.py`：Responses / 兼容协议、连接诊断、密钥脱敏。
- `durable.py` / `execution.py`：LangGraph 持久循环、审批中断、工具回执与恢复。
- `memory.py` / `memory_tools.py`：五层记忆的上下文装配、结构化资产、偏好与知识检索。
- `validation.py` / `learned_tools.py`：统一验收与代码配方的验证、审核、推广。
- `harness.py` / `studio_tools.py`：类型化工具、GIS 检查钩子、计划与离线命令。
- `algorithms.py`：35 个算法与参数契约；表达式使用受限 AST，不执行任意 Python。
- `formats.py`：GDAL 导入导出、收件箱、栅格预览、原生投影快照。
- `workflows.py`：最多 12 节点的依赖检查、拓扑执行和重放凭据。
- `cartography.py` / `plugins/`：统一布局、原生 QGIS / Python 执行插件、五种格式、工程与模板。
- `skills.py` / `plugin_tools.py`：Skill 包、代码配方与 Harness 插件工具。
- `store.py`：SQLite 追加事件、不可变产物与 SHA-256 血缘。

模型循环最多 24 轮，轮间检查 600 秒预算，HTTP 超时独立为 120 秒。Responses 每轮最多 12 个调用，兼容 Chat 每轮最多 8 个；Responses 同一失败调用连续重复 3 次后停止。
工作区一次运行一个任务。“停止”在当前工具 / HTTP 返回后生效，已完成图层保留；重启将未完成任务标记中断，不宣称自动断点续算。

## 验证

```bash
PYTHONPATH=backend GEOAGENT_DISABLE_QGIS=1 .venv/bin/python -m pytest -q
cd frontend && npm run build
```

浏览器检查应使用隔离工作区，避免操作真实项目：

```bash
GEOAGENT_WORKSPACE=/tmp/gaia-qa PORT=8767 ./start.sh
# 另一终端，提供 Playwright 和浏览器后执行
BASE_URL=http://127.0.0.1:8767 node scripts/gaia-ui-test.cjs
```

可用 `PLAYWRIGHT_MODULE` 指定模块、`CHROME_PATH` 指定 Chrome。v0.4 验收见 [Harness 验证记录](docs/VERIFICATION_V04.md)。此前界面与插件验收见 [v0.3 验证记录](docs/VERIFICATION_V03.md)；[verification.json](verification.json) 保留早期 v0.2 记录。GAIA 浏览器测试需要先导入真实矢量和 DEM，可用下载脚本和 `seed_native_demo.py` 准备隔离工作区。
`sample-data/` 和界面示例均为合成数据，不代表真实站点、公园、行政区或地形。

## 下一阶段与限制

QGIS Processing 桥接、原生布局及工程/模板已实现；macOS 使用 Seatbelt，Windows AppContainer 原生 GIS 与隔离测试已通过，但桌面安装包仍待验收。节点级检查点恢复已实现，不支持单个算法进程从中间像元续算。路网服务区的完整交互与核验、完整交互符号系统、大文件分块 / 空间数据库、澄清后继续、跨项目工作流和独立 GIS 正确性基准仍待完善。
本版没有多用户鉴权、三维、Earth Engine、影像深度学习、自动在线数据检索、拓扑编辑和完整桌面工程互通。布局编辑已支持撤销/重做；数据成果保持独立保存。
基础布局采用 EPSG:3857；专业专题 / 地形模板支持米制出图投影、分级图例、地名避让、等高线与定位插图，见 [真实数据制图](docs/PROFESSIONAL_MAPS.md)。导出不含在线底图；地图 TIFF 是排版图像，栅格数据导出才是地理参考 GeoTIFF。

参考依据和取舍见 [架构参考](docs/RESEARCH.md)。界面结合 frontend-design、Impeccable、Interface Design，并按用户最新要求形成 GAIA 自有布局和标识；见 [设计参考](docs/DESIGN_REFERENCES.md)。未复制其他 GIS Agent 的源码或截图。
