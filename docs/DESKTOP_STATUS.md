# 桌面版交付状态（2026-11-02）

支持平台仅为 **macOS Apple Silicon（arm64）** 与 **Windows 10/11 x64**。已移除 Intel Mac 构建、旧安装包及其校验文件；后续构建矩阵仅保留这两个平台。

## 0.5.0-beta.2 已交付

本版包含 Atlas / Folio 工作台、会话与 Harness、布局样式、字体及用户手册。程序、安装器和快捷方式统一使用 GAIA 名称与用户提供的盖亚图标。

| 平台 | 已通过的实际检查 | 下载 |
| --- | --- | --- |
| macOS arm64 | 27 项原生 GIS / 沙箱测试；开发版及打包应用完整启动和重启；布局、保存、名称、图标、arm64 架构与使用后签名 | [DMG](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.2-2c85c0d/GAIA-0.5.0-beta.2-mac-arm64.dmg) |
| Windows x64 | 27 项原生 GIS / 沙箱测试；开发版、打包版及 NSIS 实际安装后的完整启动和重启；程序 / 安装器图标逐像素一致，开始菜单快捷方式名称和目标正确 | [安装器](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.2-2c85c0d/GAIA-0.5.0-beta.2-win-x64.exe) |

两平台的客户端检查覆盖私有 API、GIS 分析、实际字体目录与中文字体、原生布局场景、离线自然语言样式、手动样式与字体、PDF 导出、原生文件保存、交互地图，以及重启后图层 / 样式 / 字体保留。Windows 在实际安装后再次执行这些检查。它们是本次验收流程的覆盖范围，不代表全部 GIS 算法均已逐项验收。

- [macOS 构建记录](https://github.com/liujiayuGIS/gaia/actions/runs/41415517763)
- [Windows 构建、NSIS 安装与图标验收记录](https://github.com/liujiayuGIS/gaia/actions/runs/41417048213)
- [macOS 验收回执](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.2-2c85c0d/GAIA-beta2-arm64-verification.json)
- [Windows 验收回执](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.2-2c85c0d/GAIA-beta2-windows-verification.json)

应用代码基于 `2c85c0d`；Windows 构建提交 `f46939d` 仅修正验收脚本与构建流程，流程已校验两者应用输入没有变化，复用已验收的 macOS 安装包。完整源码在 [codex/desktop-beta2](https://github.com/liujiayuGIS/gaia/tree/codex/desktop-beta2)。

[发布页、安装包与 SHA-256](https://github.com/liujiayuGIS/gaia/releases/tag/desktop-v0.5.0-beta.2-2c85c0d) · [用户手册](USER_GUIDE.md) · [离线 HTML 手册](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.2-2c85c0d/GAIA-User-Guide-zh-CN.html)

macOS 要求 15 或更新，采用 ad-hoc 签名，尚无 Apple 公证；Windows 尚无商业代码签名。仓库仍为私有，下载需要相应访问权限。
