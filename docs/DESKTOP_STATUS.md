# 桌面版交付状态（2026-11-02）

支持平台仅为 **macOS Apple Silicon（arm64）** 与 **Windows 10/11 x64**。按用户要求，已停止 Intel Mac 构建，并移除相应的安装包与下载说明。

## 0.5.0-beta.2

本次将当前 Atlas / Folio 工作台、会话与 Harness、布局样式、字体及用户手册同步进安装包。程序、安装器和快捷方式统一使用 GAIA 名称与用户提供的盖亚图标。

macOS arm64 已在本机对真实 DMG 完成启动、实际 GIS 分析、自然语言和手动样式修改、PDF 与原生文件保存、图层 / 样式 / 字体重启保持，以及安装盘 / 应用名称与图标、架构和使用后签名的检查。

Windows 正在原生构建中；首次运行、NSIS 实际安装、安装后的应用重启以及程序 / 安装器 / 快捷方式的名称和图标核验全部通过后才发布。GitHub Actions 已可启动本轮构建，不再沿用此前的账单阻止结论。

安装包与 SHA-256 文件见 [GitHub Releases](https://github.com/liujiayuGIS/gaia/releases)。[当前构建记录](https://github.com/liujiayuGIS/gaia/actions/workflows/desktop.yml?query=branch%3Acodex%2Fdesktop-beta2)。源码在 [codex/desktop-beta2](https://github.com/liujiayuGIS/gaia/tree/codex/desktop-beta2)。

macOS 为 ad-hoc 签名、尚无 Apple 公证；Windows 尚无商业代码签名。仓库仍为私有，下载需要相应访问权限。
