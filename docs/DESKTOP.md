# GAIA 桌面版

桌面版使用 Electron 打开现有工作台，在本机启动独立 Python 服务。安装包包含 Python、QGIS、GDAL/PROJ 和科学计算库，无需用户另装 Python、Node 或 QGIS。模型推理需配置自己的 API；离线 GIS 运算与制图不依赖云端模型。

日常操作见 [GAIA 用户手册](USER_GUIDE.md)。各平台本次可下载的安装包以 [GitHub Releases](https://github.com/liujiayuGIS/gaia/releases) 实际文件为准；具体原生安装验收见 [交付状态](DESKTOP_STATUS.md)。

## 下载与安装

从 [GitHub Releases](https://github.com/liujiayuGIS/gaia/releases) 下载已发布且匹配处理器的安装包：

|系统|安装包|要求|
|---|---|---|
|macOS Apple Silicon|GAIA-版本-mac-arm64.dmg|macOS 15 或更新；M 系列处理器|
|macOS Intel|GAIA-版本-mac-x64.dmg|macOS 15 或更新；Intel 处理器|
|Windows x64|GAIA-版本-win-x64.exe（以该 Release 实际文件为准）|Windows 10/11 64 位；x64 处理器|

macOS 打开 DMG 并将 GAIA 拖入 Applications。Windows 安装向导默认安装到当前用户目录，无需管理员权限。首次启动会校验并解压 GIS 运行时，可能需要几分钟和数 GB 磁盘空间；之后直接启动。首次初始化不需要额外下载 GIS 环境。

交互地图优先使用 WebGL 2；图形环境不可用时，自动切换到 Leaflet 兼容二维地图，支持矢量、栅格、图层顺序和要素交互。QGIS 数据分析与出图照常运行。

当前为未配置商业代码签名/Apple 公证的测试版，系统可能提示未知开发者或 SmartScreen。发布页面提供 SHA-256 校验值；正式无提示分发仍需维护者配置相应签名证书与 Apple 公证凭据。不要通过关闭系统整体安全检查来安装。

## 数据、更新与日志

- macOS：`~/Library/Application Support/GAIA/workspace`。
- Windows：`%APPDATA%\GAIA\workspace`。
- 在应用“文件 → 打开工作区目录”查看本机数据，“帮助 → 打开日志目录”查看启动日志。
- 应用更新替换程序文件，保留工作区、会话、任务检查点和个人界面设置。运行时按哈希分别保存，安装中断可重试；旧运行时目前不自动清理。
- 关闭应用会停止本地服务和活动作业，保存的检查点可在重新启动后继续。仍需重新提供只保存在内存的模型 API Key。
- 现有浏览器开发版的数据不会被自动搬走。可在桌面版重新导入原始数据；迁移完整工作区前，应退出两个应用并做好备份。
- 这一版采用手动下载安装更新，尚未启用后台自动更新。

## 进程与权限

`gaia://app` 是稳定的界面地址，主题和会话设置不会因端口变化丢失。Electron 主进程通过私有桥接访问随机 loopback 端口，使用每次启动新生成的令牌；本机其他网页无法直接读写该服务。渲染器不启用 Node.js，使用 contextIsolation 和 Chromium sandbox，IPC 只暴露启动状态与重试。

代码执行仍需 Harness 中的审批。macOS 使用 Seatbelt，Windows 使用无网络能力的 AppContainer 与 Job Object：仅授予公开运行库和插件代码读取权限，每个作业使用独立容器 SID，允许写入该作业及容器私有目录，退出时删除容器。运行器不继承模型密钥。隔离初始化失败时拒绝执行，不回退为无隔离代码。

## 从源码构建

程序、安装盘和快捷方式统一使用 GAIA 名称与用户提供的盖亚标志。安装包包含当前用户手册，可从“帮助 → 打开本地用户手册”读取。

三种包必须分别在目标 OS/架构构建。仓库的 `.github/workflows/desktop.yml` 在 macOS ARM64、macOS x64 和 Windows x64 上构建与验收。所选平台全部成功后提供带校验和的预发布安装包；失败时草稿不会自动发布。手动触发时可用 target 选择 all、windows 或 macos，方便补齐某个平台。

本机构建需要 Node.js 24、micromamba 和 Python。先安装前端、桌面依赖，然后生成包含全部 GIS 依赖的运行时：

```bash
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix desktop ci
python scripts/package_desktop_runtime.py --mamba micromamba
npm --prefix desktop test
npm --prefix desktop run smoke
npm --prefix desktop run dist
```

构建产物位于 `.desktop-build/installers`。运行环境、安装包、个人工作区和密钥不进入 Git。`package_desktop_runtime.py` 输出运行时校验和、实际依赖版本、上游来源和第三方许可材料，方便复现和核对。

开发调试可设置 `GAIA_DEV_RUNTIME` 指向已装齐依赖的 Conda 环境，以跳过首次解压。该选项只作用于未打包模式。`GAIA_DESKTOP_DATA_DIR` 用于测试时隔离工作区。

验证分三层：普通后端回归；真实 QGIS/代码隔离测试；Electron 窗口中执行 API、地图加载、重启后设置和图层保持。平台构建和原生测试结果以具体 GitHub Actions 运行记录为准；模拟测试不能代替目标平台运行。

实现参考：[Electron 安全边界](https://www.electronjs.org/docs/latest/tutorial/security)、[Conda 环境重定位](https://conda.github.io/conda-pack/)、[electron-builder 安装包配置](https://www.electron.build/v26/docs/configuration/)。
