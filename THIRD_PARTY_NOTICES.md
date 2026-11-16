# 许可与来源

本项目新增及维护者有权授权的修改按根目录 [LICENSE](LICENSE) 中的 MIT 条款发布。发布许可不会授予维护者并不拥有的第三方权利。原输入包没有附带 LICENSE，且来自 AI 辅助查找和修改；不能据此认定原包全部原创或全部已获授权。

## 已确认的参考来源

`scripts/swlib.py` 的 `select_mark` 原有注释注明参考 [wzyn20051216/solidworks-automation-skill](https://github.com/wzyn20051216/solidworks-automation-skill) 的 ISelectData / Mark / Select4 做法。此处保留该署名，并随包完整保留其 MIT 版权及许可文本：[上游 MIT](licenses/solidworks-automation-skill-MIT.txt)。该标注仅描述已知参考，未认定整个项目为上游的复制品。

核查快照：提交 `36bc337357723b9763759ff06e4a1afab990b823` 的 [LICENSE](https://github.com/wzyn20051216/solidworks-automation-skill/blob/36bc337357723b9763759ff06e4a1afab990b823/LICENSE)。原始使用时点与更早来源尚未恢复；当前快照不能证明历史上所有内容的授权状态。

## 1.4.1 新增适配与设计参考

统一入口与 CLI 适配由本项目编写，未复制外部执行器源码。固定提交的 wzyn `sw_drawing_package.py` 仅作为用户自行准备的可选外部入口；本包不分发其源码/依赖。其仓库顶层 MIT 不代替对 PyMuPDF 等传递依赖的许可核对。

串行执行、错误分级与接口兼容的设计参考也包括 [andrewbartels1/SolidworksMCP-python](https://github.com/andrewbartels1/SolidworksMCP-python)（9738d96944f6b4896730e5874e3ba00dfeb1d023，MIT）和 [ZiChen-Ni/solidworks-com-automation-skill](https://github.com/ZiChen-Ni/solidworks-com-automation-skill)（5bb8df4d688a287a3577fa82cc8d2956abe578ac，MIT），没有将这些项目的文件加入本包；不宣称已接入它们的服务或所有工具。

## 未随包分发的材料

- 原减速器完整尺寸教学案例未收入公开版，等待确认设计来源；本地实测版保留。
- SolidWorks 安装文件、互操作 DLL/TLB、官方帮助、模板、图标、官方样件、截图和仿真结果均未分发。API 名称用于调用说明，不等于附带官方软件授权。
- pywin32、Pillow、numpy 由用户按需另行安装，受各自许可约束；这里不分发依赖代码。
- 对其他 GitHub 项目的比较只引用项目事实与链接，不引入其源文件。特别是 AGPL 项目的代码没有纳入 MIT 分发。

SOLIDWORKS 及相关产品名称属于各自权利人。本项目名称用于描述兼容目标，不使用官方徽标、不表示官方认证。

## 发布者仍需确认的范围

尚未追溯到原包的全部文档、代码及原始设计来源。发现额外来源时，应恢复原署名、检查当时适用的许可，并按要求补充通知或移除不具备分发权的内容。扫描及补齐 MIT 不能保证不存在侵权；如果要求完整的权利确认，应先完成来源追溯再发布。上传者另需确认其 CAD 数据不属于雇主、客户或其他保密项目。
