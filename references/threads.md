# 螺纹：实体建模与工程图要求

以下来自 SW2026 SP1.1 的样件实测。先核对当前机器的接口、模板与许可；通过范围和限制见 [运行验证](runtime-validation.md)。保存与绑定问题见 [API 排错](api-pitfalls.md)。


`FeatureManager.CreateDefinition(swFmSweepThread)` → `IThreadFeatureData.InitializeThreadData()` → 设置轮廓库、规格、方法、终止条件、起始边 → `CreateFeature`。

本机通过：Ø10 × 30 mm 圆柱，Metric Die，M10×1.5，右旋，切削，盲深 20 mm；覆盖直径 0.01 m、螺距 0.0015 m。创建后检查特征错误、规格/螺距/深度以及去料，再保存回读。轮廓库在本机 ProgramData 的 Thread Profiles 中，不能硬编码其他机器的安装年份。

实体螺纹和装饰螺纹用途不同。按用户的干涉、加工、出图或计算要求选择；工程图仍需明确标准、规格、旋向、有效深度和必要的退刀/倒角，不能用三维螺旋几何代替完整螺纹标注。
