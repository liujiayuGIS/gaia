# 开源参考与 Harness 路线

核查日期：2026-10-30。依据官方仓库与 API 文档；这是功能取舍，不是横向复现或性能排名。

| 参考 | 借鉴点 | 已实现与差距 |
| --- | --- | --- |
| [ATFfang/OpenGIS](https://github.com/ATFfang/OpenGIS) | 语言、地图、图层与处理的一体工作台 | 独立实现前后端、产物入层与轨迹；未复制源码，未运行其基准 |
| [opengeos/GeoAgent](https://github.com/opengeos/GeoAgent) | 多地图 / GIS 适配器、工具元数据与模型配置 | 已统一参数契约与可发现目录；尚未提供全部适配器与外部服务 |
| [nkarasiak/qgis-mcp](https://github.com/nkarasiak/qgis-mcp) | 桥接原生 QGIS 能力 | 当前没有安装 QGIS；下一阶段应实现隔离的 qgis_process / PyQGIS 适配器 |
| [OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning) / [function calling](https://developers.openai.com/api/docs/guides/function-calling) | 连续传递推理上下文与实际工具结果 | Responses 无状态模式原样回传 reasoning / function_call，以 call_id 对应结果；真实供应商需有效凭据验收 |

## Harness 的具体落地

1. 语义规划与 GIS 执行分离：模型发现算法契约，内核执行计算；没有任意 Python / Shell 工具。
2. 输入先检查：同次运行需要 inspect；参数、距离、CRS、资源量与几何结果有独立约束。
3. 成果与解释绑定：输入哈希、参数、运行 ID、方法和工具输出关联到新图层。
4. 成功链可保存为 DAG：依赖校验、逐节点发布、结果凭据；重放不必再次让模型规划每个动作。
5. 布局是受控对象：自然语言更新布局，预览与导出共用渲染逻辑。
6. 预算与失败可见：轮数、调用数量、重复失败和取消有明确边界。

这些是实现特性，不证明优于其他 Harness。几何有效与参数合规不能证明用户的研究方法正确。

## 向桌面 GIS 广度和可验证优势推进

优先做 QGIS Processing 桥接，从真实算法清单生成元数据，以隔离文件和统一成果协议执行。ArcGIS 专有算法需要具备相应许可与 ArcPy 环境，文件格式兼容不能代替工具能力。

随后实现可恢复澄清状态、幂等节点、检查点和重试策略。当前任务失败后需要新任务继续，不宣称精确断点续算。

建立独立 GIS 验真任务集：轴顺序、投影、单位、空结果、边界与重叠计数、NoData、波段口径、地形边界、制图位置、格式往返。参考答案来自独立 QGIS / GDAL 流程或解析解，不能让模型或同一实现自评。固定模型、输入、预算和工具版本后比较成功率、数值误差、耗时、费用和失败类型。

继续补齐路网、在线数据目录、符号与出版制图、PostGIS / 大文件，再评估三维和影像深度学习；不用工具数量代替能力质量。
