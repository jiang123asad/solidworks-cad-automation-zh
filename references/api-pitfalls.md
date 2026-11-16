# COM 与建模排错

原包的 SW2026 SP1.1 / pywin32 / 中文界面经验仅供定位问题；本包没有保留可复现的原始测试模型和日志，因此不能作为所有版本的能力结论。

## 类型库与签名

`swlib` 优先读取 `SLDWORKS_TLB`，再枚举注册表类型库和常见路径，用实际 `GetLibAttr()` 的 GUID/LCID/主次版本生成绑定。多个 SW 版本并存时指定对应 TLB；不要硬编码注册表的 `22.0` 或把 SW 修订号和 TLB 版本混为一谈。

COM 返回子对象可能需要包装成 `IEdge`、`ICurve`、`ISurface`、`IModelDoc2`。遇到成员缺失先检查接口和当前版本生成的 `gen_py` 签名；不要批量删除共享缓存。`ISketchManager.CreateArc` 与旧式 `IModelDoc2.CreateArc` 等方法有不同签名，使用当前 API 帮助及生成绑定确认。不存在的旧方法名不能证明某功能无 API。

`OpenDoc6` / `Save3` / `Extension.SaveAs` 的早期绑定通常把输出参数放入 tuple。读取文档对象、错误位与警告位；异常、空对象和非零错误位都要报告。警告位需解释，不能悄悄丢弃。文件必须在保存成功后再发布。

## 单位和几何

- API 建模参数为米、弧度。`CylinderParams` / `CircleParams` 中位置和半径转 mm，三个轴向分量保持无量纲。`ConeParams` 半角转度，基准圆半径不一定是顶点半径。
- `GetBodyBox` / `GetBox` 是包围盒，用于粗筛，不能替代精确端面坐标或尺寸公差验收。
- 多实体需汇总全部实体；`bodies()` 仅适用于零件实体。装配体要按 `IAssemblyDoc` / `IComponent2`、配置、抑制/轻化状态与组件变换另行遍历；不能强转 `IPartDoc`。
- 回转轴通过圆柱面和同轴圆边共同确认；盘件的最长边往往是直径。斜轴或多轴件停止自动加工，转用明确的轴选择和坐标变换。

## 草图与方向

短边可能受推断影响。批量创建精确线段可临时设 `SketchManager.AddToDB=True`，并在 `finally` 恢复旧值。检查闭合轮廓、草图平面、单位、有效中心线和自交；草图点数不是可靠的闭合性证明。

`FeatureCut4` / `FeatureExtrusion2` 的方向取决于草图法向、终止条件和布尔参数，`Dir=True` 是原案例的参数，不能当全局修复。锥度角按实际草图、拔模方向及局部锥面验证。旋转切除的轴选择和特征范围也应匹配当前签名；不要无条件禁用特征范围处理多实体。

新建草图后精确选择对应草图，不依赖“最后一个草图”在复杂树上总能定位。重建或新特征后旧边引用可能失效；每次操作重新枚举目标几何。选择 API 返回 False 时清理选择并停止该步。

## 特征树

顶层用 `GetNextFeature()`，子层用 `GetNextSubFeature()`；共享子特征可能重复出现。封装采用全局节点预算与深度限制，触限报错，不静默截断。特征名可以改名或本地化，版本筛查不能只据名称断定几何变化。

## 批处理和恢复

使用 `owned_doc` 与 `part_output` 管理本任务打开的文档和隔离副本。拒绝已打开输入、既有输出、同名输入和源目标重合。验证失败时不发布结果，未保存的失败文档只按本任务所有权关闭；不关用户的其他文档。

COM 断连后不要自动强杀 SW 或循环重建同一特征；记录已完成和失败项，再在干净会话恢复。`NewPart()` 是创建操作，失败后需检查是否已产生文档，不能用重试循环创建大量空文档。

## 保存、兼容性和判断标准

当前版本原生保存用 `Save3`，导出使用 `Extension.SaveAs` 并清空选择，避免只导出选中的部分。文件存在或大于某个字节数不能证明导出正确；回读和接收端版本才验证兼容性。

较新 SW 的某些版本和许可支持向前两版保存原生文档，具体限制需查当前帮助；不要向 `SaveAs` 随意传年份或把旧版本失败推断为永远不支持。Parasolid 也有格式版本，STEP 有应用协议和装配结构设置，脚本当前沿用会话首选项，交付前记录并验证。

体积不变可能是属性变更、曲面或等体积改形；面数减少也可能是有效切除。验证目标尺寸、位置、实体数及对应几何，而不是规定“所有特征都必须减体积/增面”。

## 扩展实测发现

- IBody2 不支持 IEntity.Select4；用 `select_body_mark` → IBody2.Select2(append, SelectData)。面的/边的 Mark 选择仍用 `select_mark`。
- CreateDefinition 只支持其文档列出的特征类型。返回空对象时，核对专用方法；镜像、独立拔模和加厚分别用 InsertMirrorFeature2、InsertMultiFaceDraft、FeatureBossThicken 已通过。
- 线性/圆周实体阵列显式设置 PatternElement=swBodiesToPattern(2)、BodyPattern=True 和 PatternBodyArray，不能只设 BodyPattern。圆周轴如为特征需 GetSpecificFeature2。
- 配置切换的返回 False 可能表示已经处于该配置，读回 ConfigurationManager.ActiveConfiguration.Name 才判断结果。
- 工程图 CreateDrawViewFromModelView3 在本机需要先加载源模型，并使用实际本地化视图名；`*前视` 已通过，不能硬编码为所有语言。
- 颜色回读按 8 位通道量化，使用 1/255 容差；不能要求浮点值逐位相同。
- OpenDoc6 用于原生文档；中性格式用 LoadFile4 和对应 ImportData。IGES 实测用 GetImportFileData+LoadFile4("r") 回读成功。
- 重建错误、文件载入警告和几何后置条件分别记录；保存成功不等于文件重开无警告。

更多参数和证据边界见 [扩展调用要点](extended-api-recipes.md)。


## 专项实测的接口与文档状态


- 先检查本机类型库生成的接口签名。遇到一个 COM 对象包装成另一接口后行为异常，可先用 `QueryInterface(接口.CLSID, pythoncom.IID_IDispatch)`，再用对应的生成类包装；不要据此统一改写全部已工作的绑定。
- `GetErrorCode2(False)` 在本机返回 `(错误码, 是否警告)`，不要把非空元组直接当失败。值为 0 才表示无特征错误。
- 装配体配合位于 `MateGroup` 的子特征中；只遍历顶层会漏掉它们。
- 区分只读和查看模式。导出前检查 `IsOpenedReadOnly()`、`IsOpenedViewOnly()`，工程图另检查 `IsDetailingMode()`。只读文件 `Save3` 失败不能算保存通过；换可编辑副本或明确的 SaveAs 流程。
- 本轮孔表原生文件保存且能读取单元格，但回读进入查看模式，PDF 导出返回错误 4097 / 警告 1024。GUI 重载未解决；不能仅凭表格数据宣布 PDF 通过，也不能由此断言 SW 不支持孔表。
