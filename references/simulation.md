# 仿真：基础静力与附加模块

以下来自 SW2026 SP1.1 的样件实测。先核对当前机器的接口、模板与许可；通过范围和限制见 [运行验证](runtime-validation.md)。保存与绑定问题见 [API 排错](api-pitfalls.md)。


GUI“工具 → 插件”激活 Simulation 后，通过 `GetAddInObject('SldWorks.Simulation')` 获取回调；注册表有项并不证明模块可算。本轮只验证单实体线弹性静力分析，不覆盖接触、疲劳、非线性、运动或流体。

本机 COM 有生成绑定与运行时 dispatch 不一致：回调的 `CosmosWorks`、`ICWPressure` 和 `ICWMesh` 用动态 Dispatch 后才能正确调用；`AddRestraint/AddPressure` 的实体数组用 `VT_ARRAY | VT_VARIANT`。不要对全部接口无差别改成动态调用，按实际 DISPID 和结果核对。动态 dispatch 的无参方法有时读取即执行，返回 int；只在返回 callable 时再次调用。

通过样例：AISI 1020 钢，10×10×100 mm，E=200 GPa，一端固定、另一端 10 MPa 均布压力（等效 1000 N）；高质量网格尺寸 3 mm、容差 0.15 mm；5839 节点、3490 单元。求解错误码 0，最大 URES=0.0049857558 mm，解析 pL/E=0.005 mm，相对差 0.285%；保存后重开研究和结果仍可读取。

验证至少包括材料、载荷方向/单位、约束实体、网格数量、求解返回、结果量级、反力平衡，以及代表性网格加密。该样例只做解析位移对照，未完成网格收敛或工程强度验收。原云图以 Å 显示（4.986×10⁴ Å=0.004986 mm）；后续调整显示单位时 SW 崩溃，不能将该显示操作列为通过。保留 CWR 和求解日志，不用空白模型截图冒充云图。

模块用途：Simulation 做结构有限元，Motion 做随时间的机构动力学，Flow Simulation 做流体/传热，CAM 做加工工序和刀路，Routing 做管路/电气布线，Toolbox 提供标准件，PDM 管理文件版本与流程。基础 CAD 配合本身不能证明 Motion 分析通过；模块是否可用还取决于安装与许可。
