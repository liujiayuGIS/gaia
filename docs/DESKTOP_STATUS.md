# 桌面版交付状态（2026-11-03）

支持平台仅为 **macOS Apple Silicon（arm64）** 与 **Windows 10/11 x64**。已移除 Intel Mac 构建、旧安装包及其校验文件；后续构建矩阵仅保留这两个平台。

## 0.5.0-beta.5

本版已交付：提问和回答均有时间、复制与引用操作；提问可编辑为新任务，回答支持只读重新组织说明、反馈、Markdown / 代码复制和对话导出。系统离线语音可用时支持朗读。

| 平台 | 本版实际检查 | 下载 |
| --- | --- | --- |
| macOS arm64 | 74 项原生测试；开发版及打包版真实系统剪贴板、引用、编辑、反馈持久化、只读重新回答；名称、图标、架构及使用后签名 | [DMG](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.5-df3cd7b/GAIA-0.5.0-beta.5-mac-arm64.dmg) |
| Windows x64 | 74 项原生测试；开发版、打包版及 NSIS 实际安装后的同组消息操作与重启检查；GAIA 程序、安装器及快捷方式品牌验证 | [安装器](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.5-df3cd7b/GAIA-0.5.0-beta.5-win-x64.exe) |

继续覆盖原生 GIS 分析、中文 SHP、图层删除与撤销、助手拖宽、字体和布局、PDF、原生保存、交互地图以及输出预算持久化。独立浏览器验收覆盖 15 组消息交互，包括正文 / 代码 / Markdown 复制、引用提交、编辑新任务、取消恢复草稿、反馈保留、导出、Markdown 渲染及深色 / 窄窗口菜单。常规后端回归 166 项通过、8 项原生专用检查跳过；原生构建使用上述各 74 项测试另外验收。

- [两平台构建、安装及验收](https://github.com/liujiayuGIS/gaia/actions/runs/41596553003)
- [Mac 回执](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.5-df3cd7b/GAIA-beta5-macos-verification.json) · [Windows 回执](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.5-df3cd7b/GAIA-beta5-windows-verification.json)
- [发布页及 SHA-256](https://github.com/liujiayuGIS/gaia/releases/tag/desktop-v0.5.0-beta.5-df3cd7b) · [用户手册](USER_GUIDE.md) · [离线 HTML 手册](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.5-df3cd7b/GAIA-User-Guide-zh-CN.html)

安装包应用输入基于 `df3cd7b901022c7ccb5a8246256986920681d275`，后续文档更新不改变安装包。消息模型测试采用模拟协议响应，没有使用付费账号；浏览器剪贴板与语音交互使用测试替身，桌面剪贴板另以真实写入 / 读回验收。未验证实际朗读音质和每台设备的语音可用性，未声称全部 GIS 算法均已逐项验收。

## 0.5.0-beta.4

本版已交付，新增工作区图层删除 / 恢复，以及可保存的助手拖动调宽。删除适用于矢量与栅格，源文件和本地恢复数据保留；图层面板和自然语言共用底层操作。

| 平台 | 本版实际检查 | 下载 |
| --- | --- | --- |
| macOS arm64 | 66 项原生测试；开发版及打包版删除、撤销、自然语言删除、拖宽、重启状态保留；名称、图标、架构与使用后签名 | [DMG](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.4-e7e2701/GAIA-0.5.0-beta.4-mac-arm64.dmg) |
| Windows x64 | 66 项原生测试；开发版、打包版及 NSIS 实际安装后的同组交互与重启检查；应用 / 安装器图标一致，GAIA 快捷方式正确 | [安装器](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.4-e7e2701/GAIA-0.5.0-beta.4-win-x64.exe) |

同时保留中文 Shapefile、原生 GIS 分析、字体与布局样式、PDF、原生文件保存、交互地图及输出预算持久化验收。独立浏览器检查覆盖鼠标拖拽、键盘、取消与复位、宽度刷新保留、出图空间、删除失败回退、自然语言恢复、栅格移除以及深浅主题与窄窗口。

- [Mac 构建与验收](https://github.com/liujiayuGIS/gaia/actions/runs/41589694557) · [Mac 回执](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.4-e7e2701/GAIA-beta4-macos-verification.json)
- [Windows 构建、安装与验收](https://github.com/liujiayuGIS/gaia/actions/runs/41590019629) · [Windows 回执](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.4-e7e2701/GAIA-beta4-windows-verification.json)
- [发布页与 SHA-256](https://github.com/liujiayuGIS/gaia/releases/tag/desktop-v0.5.0-beta.4-e7e2701) · [用户手册](USER_GUIDE.md) · [离线 HTML 手册](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.4-e7e2701/GAIA-User-Guide-zh-CN.html)

应用输入基于 `e7e2701259d704b6608a73a260f7a9855e834710`。构建提交 `7d6123d` 仅调整桌面测试的宽视口：构建机原生 1024px 窄窗口按产品规则隐藏调宽手柄，测试先验证窄窗口删除，再显式切换宽视口验证分隔线；工作流已检查打包应用输入与发布标签一致。此后文档更新不改变安装包。验收使用合成数据和模拟模型协议，不代表全部 GIS 算法或特定付费模型账号均已验证。

## 0.5.0-beta.3

中文 Shapefile 导入、输出预算与 DeepSeek 工具链修复已完成桌面原生验收并发布。应用输入基于 `3d2aafdbe48272864d2f3bec1ae3a3ecb806aae4`；下方保留 beta.2 历史交付记录。

| 平台 | 本版实际检查 | 下载 |
| --- | --- | --- |
| macOS arm64 | 61 项原生测试；开发版及打包版启动、导入和重启；GAIA 名称、盖亚图标、arm64 架构及使用后签名验证 | [DMG](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.3-3d2aafd/GAIA-0.5.0-beta.3-mac-arm64.dmg) |
| Windows x64 | 61 项原生测试；开发版、打包版及 NSIS 实际安装后的启动、导入和重启；应用与安装器图标一致，快捷方式名称和目标正确 | [安装器](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.3-3d2aafd/GAIA-0.5.0-beta.3-win-x64.exe) |

本版新增验收覆盖中文路径下的真实 Shapefile 文件、被截断字段名的安全别名、原中文属性值和数值保留、导入警告，以及输出预算设置的重启持久化。沿用 GIS 分析、字体、自然语言与手动布局样式、PDF、原生保存及地图交互检查。

- [完整构建、安装及验收记录](https://github.com/liujiayuGIS/gaia/actions/runs/41576918202)
- [macOS 验收回执](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.3-3d2aafd/GAIA-beta3-macos-verification.json)
- [Windows 验收回执](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.3-3d2aafd/GAIA-beta3-windows-verification.json)
- [发布页及 SHA-256](https://github.com/liujiayuGIS/gaia/releases/tag/desktop-v0.5.0-beta.3-3d2aafd) · [更新说明](releases/0.5.0-beta.3.md) · [用户手册](USER_GUIDE.md) · [离线 HTML 手册](https://github.com/liujiayuGIS/gaia/releases/download/desktop-v0.5.0-beta.3-3d2aafd/GAIA-User-Guide-zh-CN.html)

原用户数据未取得，导入回归使用生成的真实 SHP 测试文件复现。DeepSeek 兼容验证采用模拟协议响应，未调用付费账号；实际服务连通性仍由用户配置决定。验收范围不代表全部 GIS 算法均已逐项验证。安装包基于上述源码提交，此后文档和独立浏览器测试脚本更新不改变已打包应用。

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

macOS 要求 15 或更新，采用 ad-hoc 签名，尚无 Apple 公证；Windows 尚无商业代码签名。仓库已公开，安装包可免登录下载；公开访问不授予仓库写权限。
