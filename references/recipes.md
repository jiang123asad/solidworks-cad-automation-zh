# 操作配方

所有命令在 skill 根目录执行；输入零件必须是已保存且未在 SW 中打开的文件。脚本拒绝覆盖现有输出。CAD 操作需要本机 SolidWorks，本次打包检查不代表 CAD 实测。

## 零件测量与特征树

```powershell
python scripts/inspect_model.py "D:\cad\part.SLDPRT" --features --edges
```

遍历全部实体并打印总体积。装配和图纸只输出特征树并报告几何未实现。圆柱轴向量无量纲，长度 mm，锥面角为相对轴线的半角。装饰螺纹可出现在子特征中，看到螺纹节点不代表实体螺纹牙型已建模。

## 两端倒角

```powershell
python scripts/seal_chamfer.py "D:\cad\*.SLDPRT" --out "D:\deliver\chamfer" --width 1.5 --angle 15
```

仅对可判定单一 XYZ 回转轴的几何使用。每次倒角后重新枚举边，检查总体积减少且实体数保持；保存后回读总体积。角度-距离倒角的输入角度不必等于期望锥面半角，有精确密封角需求用下方配方并检查局部尺寸。

## 指定端密封锥

```powershell
python scripts/add_cone.py "D:\deliver\cone" "D:\cad\part.SLDPRT" --width 3.37 --half-angle 75 --end hi
```

75° / 3.37 mm 是原项目案例，须以用户尺寸为准。轴向深度 `D=W/tan(半角)`；现成脚本不自动缩小宽度，窄环不够则失败。只支持单实体、单一轴对齐、标准平面包含实际轴心的几何。草图位置与中文模板坐标需核验，非标准模板用 `ModelToSketchTransform` 适配后再运行。

三角形绕轴完整切除的理想去除体积为 `π*D*(R*W-W²/3)`（外圆半径 R、径向宽 W），不适用于台阶、已有槽或局部端面。使用目标端面圆边、半角、宽度和总体积共同验证，不能只检查零件上“存在一个 75° 锥面”。

## 目录版本初筛

```powershell
python scripts/compare_versions.py "D:\old" "D:\new" --out "D:\deliver\diff.txt" --json "D:\deliver\diff.json" --volume-tol 1
```

按相对路径配对，保留不同子目录同名件。`METRICS_DIFFER` 表示几何汇总量有差异；`FEATURES_DIFFER` 只说明树有变化；`NO_DIFFERENCE_DETECTED` 不证明等几何或“仅重存”。等体积改形、位姿、配置、材料与公差可能漏检；重要改型追加目标尺寸、质量中心/惯量或实体几何比较。

## 导出与保存

```powershell
python scripts/export_neutral.py "D:\cad\*.SLDPRT" --out "D:\deliver\neutral" --fmt x_t,step
```

清除选择，读取保存返回值和文件生成情况；任一文件失败返回非零。导出报告不代表接收版本验证。原生旧版保存范围见 [能力与兼容性](capability-matrix.md)。

## 新建模型及 GUI 补充

公开版不附带原减速器箱体案例。新建模型时按当前任务建立参数，先使用简单、可独立验证的几何测试 API。

阵列/镜像先依据当前 API 定义、选择标记与几何测试；失败后通过宿主桌面工具查看界面、API 预选、填写参数、观察结果，最后 API 回读。参考 [GUI 协同](gui-and-tooling.md)。
