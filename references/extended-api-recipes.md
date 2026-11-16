# SW2026 SP1.1 扩展调用要点

以下是本机实际成功的教学样件调用约定。详细实现见 `../scripts/extended_selftest.py`；米、弧度为 API 输入单位。每个用例创建自己的文档，并验证几何或属性后保存；仅关闭本次创建的文档。空输出目录避免覆盖和重复样件混淆。

```powershell
python scripts/extended_selftest.py --out D:\cad-test\run1
python scripts/extended_selftest.py --group body --out D:\cad-test\run2
```

`body` 6 项：复制、镜像、加厚、独立拔模、线性与圆周实体阵列。`specialty` 5 项：孔向导沉孔、筋、材料、RGB、装配干涉。需要默认零件/装配模板及材料数据库。COM 顺序运行；输出 results.json 在每个用例结束时更新，任何失败退出码非零。不要与用户交互建模同时运行。测试不是任意几何的自动修复器。

| 操作 | 已验证选择和参数 | 结果核对 |
|---|---|---|
| 移动/复制实体 | IBody2.Select2，Mark=1；InsertMoveCopyBody2 | 实体数 1→2、质心 x 位移 60 mm |
| 镜像实体 | 实体 Mark=256，基准面 Mark=2；InsertMirrorFeature2 | 两实体质心 x 为 ±15 mm |
| 曲面加厚 | 曲面体 Mark=1；FeatureBossThicken 厚 2 mm | 40×30 mm 面变为 2400 mm³ 实体 |
| 独立拔模 | 中性面 Mark=1，待拔模面 Mark=2；InsertMultiFaceDraft 3° | 平面法向与 sin(3°) 相符 |
| 线性实体阵列 | PatternElement=2、BodyPattern=True、PatternBodyArray；D1Axis 直边 | 3 个 10 mm 方块，总体积 3000 mm³ |
| 圆周实体阵列 | 同上；Axis 为 IRefAxis，4 实例、2π 等间距 | 4 实体，总体积 4000 mm³ |
| 孔向导 | CreateDefinition(swFmHoleWzd)，InitializeHole ISO HexBolt M6 CounterBore，面用 SelectByRay Mark=0 | 找到半径 3.3 mm 的圆柱孔面并减少体积 |
| 筋 | 在 L 形实体中间建立草图；ModelToSketchTransform 转换端点；InsertRib 平行草图方向 | 筋特征持久化、增加实体体积 |
| 材料 | GetMaterialDatabases 读取现有库；IPartDoc.SetMaterialPropertyName2 | 读回 AISI 1020，密度 7900 kg/m³ |
| 装配干涉 | InterferenceDetectionManager.GetInterferences；finally Done() | 两重叠方块干涉体积 12000 mm³ |

InsertRib 为无返回值方法；不能用返回非空判断成功。InsertRefPlane 返回 IRefPlane，不能直接当 IFeature 调用 Select2；从树重新获得对应 RefPlane 特征再选。

HoleWizard5 有 27 个参数，Value1…Value12 的 12 个数值参数不可漏。即使签名正确，标准、紧固件类型、尺寸和选面条件仍会影响结果。本机沉孔 FeatureData 路径通过，直接 ISO M6 间隙孔路径没有验证去料，保留为失败记录。

实体布尔并集使用 SWBODYADD=15903；15902 是相减。草图等距倒角 CreateChamfer 类型为 2，需同时选择两条线。

通过样件不代表完整钣金加工、焊件切割清单生产配置、工程图尺寸标注、有限元分析或制造流程已通过。每个产品任务仍需目标尺寸、重建状态、保存回读和引用检查。
