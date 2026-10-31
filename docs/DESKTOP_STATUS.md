# 桌面版交付状态（2026-10-31）

## 已可下载

发布：[`desktop-v0.5.0-beta.1-6feef3e`](https://github.com/liujiayuGIS/geoagent-studio/releases/tag/desktop-v0.5.0-beta.1-6feef3e)。这是 **macOS 预览版**，包含 Apple Silicon 和 Intel 两个 DMG 及 SHA-256 文件。最低 macOS 15。

两种架构均通过[原生构建验收](https://github.com/liujiayuGIS/geoagent-studio/actions/runs/41177767396)：首次展开离线 GIS 环境、实际 QGIS 算法与 PDF 出图、原生文件保存、交互地图、重启后图层与设置保持、打包应用启动及使用后的签名完整性检查。代码签名仅为 ad-hoc，尚无 Apple Developer ID 与公证。

## Windows 尚待完成安装包验收

Windows 10/11 x64 的 Electron、NSIS、Python/QGIS 环境、AppContainer 代码隔离和构建流程已提交。原生 Windows GIS 与隔离测试已通过，包括 QGIS 缓冲区、PDF、工程保存和重新打开。

首次启动曾在 `conda-unpack` 打开已加载的 `_bz2.pyd` 时遇到锁定。提交 `f5f5700` 修复了“文件内容不变仍以写权限打开”的上游行为，并增加四个测试，保留 Conda 原有路径替换逻辑和真实写入失败。**该修复尚未在 Windows 原生构建中重新验证，Windows 安装包尚未发布。**

[最新构建](https://github.com/liujiayuGIS/geoagent-studio/actions/runs/41178954272) 在任何作业运行前被 GitHub 阻止，提示：`recent account payments have failed or your spending limit needs to be increased`。需仓库账号在 Billing & plans 恢复 Actions 可用额度后重跑。

恢复后可执行：

```bash
gh run rerun 41178954272 --repo liujiayuGIS/geoagent-studio
```

完整工作流还会验证 Windows 的首次运行、打包后的应用以及 NSIS 实际安装后的应用；三种架构全部通过后才自动发布新的完整桌面预览版。不能将本机模拟测试当作 Windows 验收。

源码位于 [`codex/desktop-v05`](https://github.com/liujiayuGIS/geoagent-studio/tree/codex/desktop-v05)。仓库为私有，下载者需具有访问权限；本次没有改变可见性。
