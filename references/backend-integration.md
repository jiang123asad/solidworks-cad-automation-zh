# 可选工程图后端接入

当前适配对象：[wzyn20051216/solidworks-automation-skill](https://github.com/wzyn20051216/solidworks-automation-skill)，固定提交 `36bc337357723b9763759ff06e4a1afab990b823`，调用 `scripts/sw_drawing_package.py`。本包自行实现 CLI 适配，没有复制其源码或附带其依赖。**状态：SW2026 SP1.1 基础三视图、原生保存重开与 PDF 联调通过；尺寸完整性未通过生产验收，仍需人工检查。**

## 准备

自行在本机克隆固定提交到独立、干净的 Git 检出；不要让上游自动更新该目录。按其文档配置独立 Python（上游要求 3.10+）、依赖、SW、材料与模板。此包不自动 clone、安装或修改任何 MCP/宿主配置。

上游仓库 MIT 不等于其全部依赖都是 MIT；例如其依赖含 PyMuPDF，打包/部署前需按具体版本与使用方式核对许可。配置后运行的是本机外部代码，先检查其行为。上游的注册/帮助/模拟测试不能替代 CAD 验收。

在工作区之外保存一个本机文件，例如 `backend.local.json`，内容四项：

```json
{
  "backend": "wzyn-drawing",
  "root": "D:\\cad-tools\\solidworks-automation-skill",
  "python": "D:\\cad-tools\\solidworks-automation-skill\\.venv\\Scripts\\python.exe",
  "revision": "36bc337357723b9763759ff06e4a1afab990b823"
}
```

`root/python` 必须是实际绝对路径，不能放任意命令；本包只接受已知后端和固定入口。`backend-check` 核对 Git HEAD、已跟踪文件修改和入口文件，不导入后端依赖、不启动 SW。它不审计未跟踪文件、依赖代码或整个运行时供应链。

```powershell
python -X utf8 -B scripts/cad_assistant.py 后端检查 --backend-config "D:\cad-tools\backend.local.json"
```

## 工程图执行

按固定提交上游的 [DrawingSpec schema](https://github.com/wzyn20051216/solidworks-automation-skill/blob/36bc337357723b9763759ff06e4a1afab990b823/subskills/solidworks-engineering-drawing/schemas/drawing_spec.schema.json) 编写规格，不复制官方模板进公开仓库。`sourceModel` 必须为绝对路径。图纸标准、投影、纸张、模型尺寸、必要视图/尺寸及输出明确填写；本包不把无尺寸要求的示例当完整生产出图策略。

```powershell
python -X utf8 -B scripts/cad_assistant.py 工程图 --backend-config "D:\cad-tools\backend.local.json" --spec "D:\cad\drawing-spec.json" --out "D:\deliver\drawing-new" --plan
```

核对计划后去掉 `--plan` 执行。后端验证完整 DrawingSpec；本入口验证基本输入、固定提交与输出，记录源模型/规格指纹，通过参数列表调用独立 Python，不将本包 `PYTHONPATH` 注入后端。

完成后检查 `drawing.slddrw`、`drawing.pdf`、`drawing_review_report.json` 和入口任务日志。退出码 0/2 且返回已知可审视状态、预期文件非空时只标“需要人工检查”。控制台允许出现进度日志，入口改读本任务生成的 drawing_review_report.json；该报告缺失、无效或状态不明时暂停后续任务；不自动换到其他项目再次建图。孔表 PDF、尺寸遗漏、关联与布局必须实际检查。

当前没有接入 andrewbartels1、ZiChen-Ni、TS 或 AGPL 项目的执行服务。它们只作为设计参考，不能将其全部工具数计入本包能力。后端升级先修改适配与回归，再更新固定版本，不靠配置随意跳过版本核对。

## 本机联调发现

GB_T 图纸需要实际图幅模板；未给模板时，本机返回 DRAWING_GBT_TEMPLATE_MISSING。请在自己的 DrawingSpec.templateCandidates 中填写实际存在且匹配纸张的本机 `.slddrt` 路径，不打包官方模板。

上游会先打印连接与建图进度，然后打印 JSON；1.4.1 使用新输出目录中的结构化审视报告识别状态。回归覆盖该行为，保持可审视结果为“需要人工检查”。两孔板样例虽然生成三视图，自动带出尺寸仅有厚度，缺外形/孔径/孔位尺寸；后端返回 pass 也不能代替完整尺寸策略和人工验收。详见 [本轮验证](live-validation-1.4.1.md)。
