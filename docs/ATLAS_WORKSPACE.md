# GAIA Atlas / Folio 工作台

2026-11-02 按用户确认的组合实现：A「浮屿」用于地图，C「图志」用于出图，B「地层」仅提供分析流程抽屉。

## 地图工作区

- 地图铺满工作区，左侧数据 / 工具 / 格式 / 目录改为浮动面板，可收起；助手始终是右侧独立区域。
- 顶部浮动操作条进入导入、算法与布局。右侧地图工具提供定位、属性表、在线底图和 Python 代码入口。
- 顶部搜索或 Cmd / Ctrl + K 检索现有图层及真实算法目录。选择图层会定位，选择算法打开已初始化的参数表。
- Cmd / Ctrl + Enter 发送助手输入，附件按钮进入原有数据导入流程。

## 分析流程抽屉

抽屉默认紧凑显示，点击展开后读取当前会话最近任务的真实 `tool_started` / `tool_completed` 事件。每项操作可查看参数、执行耗时与实际回执；有 `layer_id` 时可直接定位输出图层，也可下载运行记录。

没有任务或回执时说明当前状态，不生成示意步骤。中断、失败、等待审批与完成分别显示；工具成功与任务通过验收是不同层次，沿用助手的验收报告。展开后的实际高度会同步到地图控件和数据面板，避免遮挡比例尺或运行按钮。

## 出图模式

出图模式使用独立版面侧栏、当前原生布局的缩略图、元素列表和毫米标尺。缩略图由同一个 QGIS scene 中的真实元素图像组合，不额外触发整张地图渲染。原有拖动、缩放、属性、撤销 / 重做、模板和导出接口保持连接。

只显示当前工程实际存在的页面，不仿照概念图填入虚构的多个版式。窄屏导出按钮固定可见，其他较多的工具可横向滚动。

## 主题与响应式

浅 / 深主题及用户强调色继续保存。主按钮根据实际亮度选择更高对比度的白色或深色文字，地图符号不跟随工作台强调色变化。1050px 及以下使用“数据与工具 / 地图与布局 / GAIA 助手”切换，避免挤压三栏。

设计令牌见 [DESIGN.md](../DESIGN.md)，实现样式在 `frontend/src/atlas.css`。批准的概念图与选择记录保存在 `.impeccable/mocks/decision/`；生成图只作设计参考，没有作为交互地图或打印页面使用。

## 验证

在独立公开数据工作区执行：

```bash
GEOAGENT_WORKSPACE=/tmp/gaia-atlas-qa .venv/bin/python scripts/qa_quality_server.py
BASE_URL=http://127.0.0.1:8767 PLAYWRIGHT_MODULE="$PWD/desktop/node_modules/playwright" CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' node scripts/atlas-ui-test.cjs
```

检查实际 QGIS 运行、流程抽屉、搜索进入参数表、输出跳转、原生版面缩略图、PDF 保存、自定义色彩对比度、主题保存、1100px 桌面和 390px 手机交互。既有 `gaia-ui-test.cjs` 验证布局拖动与属性编辑，`layer-order-ui-test.cjs` 验证鼠标 / 键盘 / 触摸绘制顺序。

这次更新是工作台源码和本地 Web 界面。既有 macOS Release 安装包尚未重新打包；Windows 安装包仍按之前决定等待 Actions 额度恢复后验收。
