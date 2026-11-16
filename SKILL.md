---
name: solidworks-cad-automation
description: 在 Windows 上通过本机 SolidWorks COM 和必要的 GUI 操作 CAD；提供零件改型、检查与导出脚本，以及配合、工程图和基础静力仿真的实测调用指导。用于操作 SolidWorks 或 SLDPRT、SLDASM、SLDDRW；不用于无 SolidWorks 环境的通用转换。
metadata:
  version: "1.4.1"
---

# 中文 SolidWorks 助手

面向中文用户，用本机 SolidWorks 完成可验证的 CAD 操作。优先 COM 精确定位与建模，必要时用当前宿主提供的桌面工具补充操作。环境不可用时交付脚本与明确的未验证项，不声称已生成或验证 CAD。

文件位置和每个文件的内容见 [文件说明](文件说明.md)；安装与人工阅读从 [README.md](README.md) 开始。

## 开始与任务分流

1. 确认输入、目标尺寸、配置、输出位置及目标 CAD 版本。能从文件和已有指令确定的信息直接读取；影响几何的缺失尺寸才询问，不把案例参数当设计要求。
2. 优先使用统一入口 `python -X utf8 -B scripts/cad_assistant.py`：`能力` 查询 [capabilities.json](capabilities.json)，`诊断` 只检查环境。命令见 [中文使用指南](中文使用指南.md)，安装见 [INSTALL.md](INSTALL.md)。任务加 `--plan` 先核对输入与后端；现成入口不适用时再按下表使用库或写专用脚本，不误称受入口排他锁保护。脚本路径相对 skill 根目录。
3. 按任务仅加载下列参考文件，不一次读取全部资料。

| 任务 | 入口与参考 |
|---|---|
| 零件检查、测量、特征树 | `scripts/inspect_model.py`；绑定或几何错误读 [API 排错](references/api-pitfalls.md) |
| 零件副本倒角、密封锥 | [建模配方](references/recipes.md)，再选 `seal_chamfer.py` / `add_cone.py` |
| 两版零件目录初筛 | `compare_versions.py`；结果为指标差异，不能证明几何完全相同 |
| 跨版本或跨 CAD 交付 | [能力与兼容性](references/capability-matrix.md)，再用 `export_neutral.py` |
| 阵列、镜像、独立拔模、加厚、筋、孔向导 | [已验证调用要点](references/extended-api-recipes.md)；`extended_selftest.py --out 新目录` 创建验证样件 |
| API 失败、GUI 操作 | 先读 [API 排错](references/api-pitfalls.md)，需要 GUI 时读 [GUI 协同](references/gui-and-tooling.md) |
| 实体螺纹 | [螺纹建模与出图](references/threads.md) |
| 装配配合、皮带、爆炸视图 | [装配专项](references/assembly-mates.md)；区分配合创建与运动行为验证 |
| 工程图视图、BOM/气泡、孔表、尺寸与公差/焊接符号 | [工程图与标注](references/drawings-annotations.md)；按尺寸策略和实际 PDF 验收，零件几何脚本不直接适用 |
| 基础结构静力仿真、附加模块 | [基础仿真](references/simulation.md)；先确认模块可用，再核对材料/载荷/单位与解析量级 |

## 统一入口与扩展后端

统一入口支持 inspect/render/export/chamfer/cone/compare 及对应中文别名，一次处理一个模型。倒角和锥面明确填写尺寸，输出目录必须全新。它使用参数列表启动子进程、记录输入指纹与结果；运行期间不要并行人工编辑。失败或中断先读日志核对 SW，不自动重做写操作，恢复见 [执行与恢复](references/execution-and-recovery.md)。

需要结构化工程图时，可由用户显式配置固定提交的 wzyn 后端，见 [后端接入](references/backend-integration.md)。当前适配已在 SW2026 SP1.1 打通基础三视图/保存重开/PDF；样例尺寸不完整，不能作为生产验收；不自动安装或换后端。工程图可审视结果仍标“需要人工检查”；不能宣称外部项目所有工具均已集成。普通任务不安装依赖，只有明确调用安装环境命令才创建本包 .venv 并联网安装基础包。

## 操作与数据约定

- 使用 `scripts/swlib.py` 的类型库绑定和接口包装。API 输入默认 **米、弧度**；封装返回的长度为 **mm**、体积为 **mm³**，方向向量无量纲，`cone_of` 半角为度。
- 只操作本任务输入和创建的文档。脚本遇到已打开的同路径文件会退出，避免关闭用户文档或读取未保存状态；可另建输入副本继续。不要调用 `CloseAllDocuments` 或为了恢复批处理强杀 SolidWorks。
- 修改在隔离副本中完成，验证和保存成功后才发布输出。默认拒绝覆盖、同名冲突和源目标相同；需要重跑时选新的输出目录。批量失败应有非零退出码及逐件结果。
- COM 按单一线程顺序调用，不跨线程共享对象。重建后重新取得实体、面、边，避免拓扑失效。`AddToDB` 等临时状态放在 `try/finally` 中恢复。
- 平面按实际特征名和草图变换确定。不能只凭包围盒最长边确定回转轴，不能把中文模板坐标当通用规则。斜轴、多轴、偏置草图不适用现成密封锥脚本时，先明确报告边界，再用变换矩阵适配。

## 最小用法

```powershell
python scripts/doctor.py
python scripts/inspect_model.py "D:\cad\part.SLDPRT" --features --edges
python scripts/render.py "D:\cad\part.SLDPRT" "D:\deliver\part.png" iso
python scripts/seal_chamfer.py "D:\cad\part.SLDPRT" --out "D:\deliver\chamfer" --width 1.5 --angle 15
python scripts/add_cone.py "D:\deliver\cone" "D:\cad\part.SLDPRT" --width 3.37 --half-angle 75 --end hi
python scripts/export_neutral.py "D:\cad\part.SLDPRT" --out "D:\deliver\neutral" --fmt x_t,step
python scripts/compare_versions.py "D:\old" "D:\new" --out "D:\deliver\diff.txt" --json "D:\deliver\diff.json"
```

批处理的通配符由导出/改型脚本展开，PowerShell 中可传带引号的 `"D:\cad\*.SLDPRT"`。先在一个有代表性的副本验证，再批量处理。

## 验证与故障处理

特征返回对象或 `True` 只是一个信号。重建后根据目标验证：

- 加料/去料：所有实体的总体积、实体数及目标位置的面/边。体积变化方向应合理，数值使用任务尺度下的容差；面数不必增加。
- 密封锥/孔/拔模：目标端或目标面的直径、角度、位置、深度；总量变化不能代替局部尺寸验证。
- 曲面、尺寸、材料、配置、外观或等体积改形：检查对应属性/拓扑/位置，体积不变不能判失败。
- 配合与工程图：核对实体引用、求解错误和需要的运动关系；尺寸/符号须同时检查值、几何关联及实际渲染，不能只凭创建返回值。
- 仿真：核对材料、载荷/约束、单位、网格和求解返回，并用解析值或其他独立证据检查量级；云图存在不能代替数值验证。
- 保存：检查 API 布尔值、错误位与警告位、文件生成，再关闭并重新打开输出核对目标指标。中性格式导出脚本只检查保存与文件生成；导入兼容性需在接收方或回读测试验证。

```python
import swlib
sw = swlib.app()
with swlib.owned_doc(sw, r"D:\cad\part.SLDPRT") as raw:
    doc = swlib.model(raw)
    print(swlib.total_volume(raw), swlib.total_faces(raw))
    for kind, name, depth in swlib.walk_features(doc):
        print(depth, kind, name)
```

失败时依次检查活动文档/配置、生成绑定签名、选择类型和 Mark、草图闭合与变换、方向和作用范围。一次只改一个有依据的因素；同一失败最多尝试两种有理由的修正，随后记录失败或切 GUI。崩溃/RPC 断连后停止本批并保留结果，由用户处理其他未保存文档后再恢复。

## 证据与交付

1.3.0 增加本机 SW2026 SP1.1 的螺纹、21 个配合用例、爆炸、工程图标注及基础静力实测记录，详见 [实测范围](references/runtime-validation.md)。孔表 PDF 与皮带联动为部分通过；机械配合全行程和完整生产出图仍有未验证项。仿真求解/结果回读通过，后续云图显示调整触发 SW 崩溃，已停止该批。`extended_selftest.py` 仍提供前轮 11 项可重跑的高级样例；本轮专项提供调用参考，未包装为通用自动建模脚本。通过的是给定几何与参数，不能称为全部功能认证。插件注册表只说明注册状态，不能证明许可证或模块计算通过。

交付实际输出路径、逐件成功/失败、关键前后指标、保存/回读结果和未完成验证。装配体中替换改型零件需额外检查引用、配置和配合；不能把单个零件副本当作已更新的完整装配。

1.4.1 实机验证和范围见 [本轮实测](references/live-validation-1.4.1.md)。外部工程图解析以新输出目录中的结构化报告为准，不从混杂控制台日志截取 JSON。
