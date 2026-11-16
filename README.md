# 中文 SolidWorks 助手 1.4.1

**中文说需求，建模有步骤，结果有检查。**

面向中文用户的 Windows 本机 SolidWorks 自动化 skill，提供零件检查、改型、标准视图图像、版本指标对比与中性格式导出。复杂螺纹、装配配合、工程图和基础静力仿真提供专题经验；工程图另有可选后端接口，已打通本机基础三视图流程，仍需人工验收。

独立社区项目，与 Dassault Systèmes / SOLIDWORKS 无官方关联或背书。需要合法许可的本机 SolidWorks；本包不附带软件、模型或官方模板。新增及有权授权的修改使用 [MIT](LICENSE)，已知上游及原包来源限制见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 最快开始

1. 将本文件夹放到可写位置。已安装 Windows Python 3.9+ 时，双击 **启动助手.cmd**。
2. 首次选“环境检查”；若缺依赖，双击 **安装基础环境.cmd**，在本文件夹创建独立 `.venv`，安装 pywin32/Pillow。该安装步骤会联网，不修改系统 Python 或宿主配置。
3. 再打开助手，按中文菜单选任务，填写已保存且已关闭的输入文件与一个全新的输出文件夹。没有 Python 时按 [INSTALL.md](INSTALL.md) 手动准备。
4. 完成后查看终端显示的报告目录：中文摘要、JSON 记录与执行日志。失败或中断后先检查状态，不直接重复改型。

也可以让 AI 使用 [SKILL.md](SKILL.md)，或直接执行：

```powershell
python -X utf8 -B scripts/cad_assistant.py 能力
python -X utf8 -B scripts/cad_assistant.py 诊断
python -X utf8 -B scripts/cad_assistant.py 检查 "D:\cad\轴.SLDPRT" --plan
python -X utf8 -B scripts/cad_assistant.py 检查 "D:\cad\轴.SLDPRT"
python -X utf8 -B scripts/cad_assistant.py 导出 "D:\cad\轴.SLDPRT" --out "D:\deliver\neutral" --formats step,x_t
```

安装独立环境后，命令中的 `python` 可替换为 `.venv\Scripts\python.exe`。`--plan` 仅检查参数并显示执行计划，不启动 SW。

## 提供什么

| 能力 | 当前交付 | 关键范围 |
|---|---|---|
| 中文入口与结果摘要 | 双击菜单、中文命令别名、环境检查、任务记录 | 安装器不会自动安装 SW 或配置 AI 宿主 |
| 零件检查、图形区图像、导出与对比 | 本地可执行脚本 | 导出仅校验保存/非空文件；对比不是几何等价证明 |
| 倒角与指定端密封锥 | 副本输出，明确填写尺寸 | 只适用脚本规定的轴对齐几何 |
| 螺纹、配合、爆炸、图纸标注与仿真 | 按任务阅读的实测经验文档 | 未统一封装为通用命令；部分项目仍有验收缺口 |
| 扩展工程图后端 | 固定提交的本机 CLI 适配器 | 自行安装与配置；基础三视图、保存重开与 PDF 已联调，完整尺寸仍需人工验收 |

机器可读范围见 [capabilities.json](capabilities.json)，每个文件的用途见 [文件说明.md](文件说明.md)。详细命令见 [中文使用指南](中文使用指南.md)；扩展后端见 [后端接入](references/backend-integration.md)。

## 让结果更可靠的措施

统一入口通过同一用户的排他锁避免本包的多个入口同时操作 SW，记录输入 SHA256 与预期输出，并在失败/中断后保留待确认状态。它不能锁住用户手动操作、其他 CAD 程序或绕过入口的旧脚本。运行期间不要并行编辑任务模型。

入口不设置“超时就重跑”的写操作逻辑；COM 调用超时不代表修改已经停止。执行完成也不等于生产验收，具体尺寸、工程图和仿真按任务核对。详情见 [执行与恢复](references/execution-and-recovery.md)。

## 验证范围

1.4.1 在 SW2026 SP1.1 实机验证新版入口：17 项本地工作流检查、11 项高级样例与基础冒烟 11 PASS / 3 SKIP；另完成基础环境安装与新环境 SW 读取。40 项离线回归通过。可选后端生成了基础三视图、原生重开及 PDF，但样例尺寸不完整，仍需人工验收。本轮不重测历史全部配合/螺纹/仿真，也不代表全功能认证。详见 [本轮实机验证](references/live-validation-1.4.1.md)；历史记录见 [runtime-validation.md](references/runtime-validation.md)。

不收集遥测或主动上传 CAD；环境安装会访问 pip 索引，外部后端及 AI 宿主的行为另行核查。日志、截图和模型仍可能包含敏感内容，见 [PRIVACY.md](PRIVACY.md)。
