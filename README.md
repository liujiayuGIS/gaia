# GAIA

**Geospatial Artificial Intelligence Assistant · 地理空间人工智能助手盖亚**

本地运行的地理空间人工智能工作台。用自然语言安排分析，也可以手动选择数据、填写参数；结果生成新图层，并通过 QGIS 布局编辑、核验和导出地图。

**[用户手册](docs/USER_GUIDE.md) · [离线 HTML 手册](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.3-3d2aafd/GAIA-User-Guide-zh-CN.html) · [下载安装包](https://github.com/liujiayuGIS/gaia/releases/tag/desktop-v0.5.0-beta.3-3d2aafd) · [桌面开发源码](https://github.com/liujiayuGIS/gaia/tree/codex/desktop-beta2)**

![GAIA 工作区](screenshots/gaia-workspace.png)

## 下载与开始使用

当前桌面预览版为 **0.5.0-beta.3**，内置 Python、QGIS、GDAL/PROJ 和科学计算库。本版修复中文 Shapefile 文字编码与截断字段名导入，增加输出预算设置及 DeepSeek 推理工具链兼容。

| 平台 | 状态 |
| --- | --- |
| macOS Apple Silicon（M 系列） | [下载 DMG](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.3-3d2aafd/GAIA-0.5.0-beta.3-mac-arm64.dmg)，要求 macOS 15+；打包应用与品牌检查通过 |
| Windows 10/11 x64 | [下载安装器](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.3-3d2aafd/GAIA-0.5.0-beta.3-win-x64.exe)；实际安装、运行、重启及名称 / 图标检查通过 |

打开 DMG，将 GAIA 拖入“应用程序”，首次启动等待本地 GIS 环境初始化。离线算法与制图不需要模型；复杂自然语言分析需配置自己的模型 API。当前 macOS 包尚无 Apple Developer ID / 公证，具体安装说明与 SHA-256 在发布页。仓库已公开，安装包可免登录下载。外部用户可查看、下载或 Fork，也可以提交 Pull Request；未获写权限的账号无法直接推送或合并修改到原仓库。

第一次使用建议按 [十分钟完成第一张地图](docs/USER_GUIDE.md#quickstart) 操作：加载合成演示数据 → 执行 800 米缓冲计数 → 调整布局 → 检查出图 → 保存 PDF。

## 可以做什么

- **数据与图层**：导入 SHP、GeoPackage、GeoJSON、CSV、GeoTIFF 等；选择子图层，调整显隐、绘制顺序和符号，导出新的分析数据。
- **自然语言与手动算法**：连接 Responses 等模型接口，由助手选择插件和编排任务；也可直接使用参数表运行 QGIS / Python 算法。
- **可审阅的分析**：执行前核对几何、CRS、单位与数据语义；执行后按适用规则检查成果，记录错误、警告和未验证项。
- **制图与交付**：QGIS 原生布局、可拖动元素、四种指北针、比例尺样式目录、五种高程色带和本机字体，导出 PDF、SVG、PNG、JPEG、TIFF，保存 QGIS 工程与数据包。
- **会话与恢复**：连续会话、具体步骤审批、节点级检查点恢复；项目文件、执行状态、稳定偏好和方法知识各自保存。
- **扩展研究方法**：插件与 Skills、受限 Python / PyQGIS 代码、保存工作流，以及验证和人工审核后的自定义工具推广。

算法目录由实际环境决定，不代表全部算法都已独立验收。当前不等同于 QGIS / ArcGIS Pro 的完整能力，也没有超过其他 Agent 的同条件评测结论。限制见 [能力与格式](docs/CAPABILITIES.md)。

## 用户文档

| 文档 | 内容 |
| --- | --- |
| [用户手册](docs/USER_GUIDE.md) | 18 个章节：安装、模型、导入、分析、图层、出图、审批恢复、记忆、扩展、备份与排错 |
| [桌面版说明](docs/DESKTOP.md) | 系统要求、数据路径、安全边界与源码打包 |
| [交付状态](docs/DESKTOP_STATUS.md) | 已验收平台与本次发布状态 |
| [空间质量](docs/SPATIAL_QUALITY.md) | 语义契约、领域核验和视觉审图的前提与范围 |
| [Harness 与记忆](docs/HARNESS_V04.md) | 持久执行、审批、五层记忆和工具沉淀 |
| [插件与 Skills](docs/PLUGINS_AND_SKILLS.md) | 插件契约、方法包和代码运行方式 |

## 源码开发

**当前桌面开发源码位于 `codex/desktop-beta2` 分支；本默认分支同步维护首页与用户文档。** 获取桌面实现时请指定分支：

```bash
 git clone --branch codex/desktop-beta2 https://github.com/liujiayuGIS/gaia.git
 cd gaia
```

开发启动与验证见 [桌面源码 README](https://github.com/liujiayuGIS/gaia/blob/codex/desktop-beta2/README.md)；两平台打包流程见 [桌面版说明](docs/DESKTOP.md)。已有本地克隆可更新远程地址：

```bash
 git remote set-url origin https://github.com/liujiayuGIS/gaia.git
```

问题反馈请到 [Issues](https://github.com/liujiayuGIS/gaia/issues)，附应用版本、操作步骤、错误文字和可分享的最小数据样本；不要提交 API Key 或受限数据。
