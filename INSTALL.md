# 安装与环境

本包是 UTF-8 文档、Python 源码和 Windows 启动脚本，不附带 SolidWorks、模型或官方模板。安装 skill 不代表 CAD 或外部后端已经真机验证。

## 最简单的本机使用

Windows + 已许可的 SolidWorks + Python 3.9+。解压到可写目录，双击 [安装基础环境.cmd](安装基础环境.cmd) 在本文件夹创建独立 `.venv` 并安装 [requirements.txt](requirements.txt)；安装会联网访问当前 pip 索引。再双击 [启动助手.cmd](启动助手.cmd)，先选环境检查。它优先用本包 `.venv`，其次系统 `py -3`/`python`，不自动安装解释器。

已有依赖时可直接打开启动助手。安装器不会覆盖其他已有 `.venv`，不改系统 Python、注册表、hosts、AI 宿主配置或 SolidWorks 首选项；不会自动下载 SW/附加模块。若无法创建虚拟环境，按 Python 报错修复，或使用已准备好的 Python 直接运行脚本。

## 手动准备

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -X utf8 -B scripts/cad_assistant.py 诊断
# 仅旧 GUI helper 或原离线回归需要
.venv\Scripts\python.exe -m pip install numpy
```

手工创建的环境可由启动助手使用；安装基础环境命令不会接管它。基础依赖为 pywin32/Pillow，范围版本不是完整锁文件，升级后应重新验证。

自定义 SW 类型库路径可在当前终端设置 `$env:SLDWORKS_TLB = 'D:\SOLIDWORKS\sldworks.tlb'`。首次运行生成 COM 绑定可能需要可写缓存；不要为修复本任务随意删除其他程序共享 `gen_py`。

## 安装为 Codex skill

将整个 `solidworks-cad-automation` 文件夹复制到 `$CODEX_HOME/skills`，未设置时通常为 `$env:USERPROFILE/.codex/skills`。最后路径应为 `skills/solidworks-cad-automation/SKILL.md`。已有同名 skill 时先比较/备份，不静默覆盖。必要时重载宿主。本包不自动配置 MCP。

全新解压示例：

```powershell
$skillRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
Expand-Archive -LiteralPath '.\solidworks-cad-automation-zh-1.4.1.zip' -DestinationPath $skillRoot
```

## 检查层级

- `cad_assistant.py 能力` / 任何任务加 `--plan`：读文档/检查参数，不启动 SW。
- `cad_assistant.py 诊断`：本机环境检查，不启动 SW；不证明附加模块许可。
- `doctor.py --connect`：直接连接或启动 SW，仅诊断连接。
- `api_selftest.py` / `extended_selftest.py --out 新空目录`：旧的真机测试，会创建/关闭自己的 CAD 文档，不能与助手并行运行。
- `python -X utf8 -B -m unittest discover -s tests -p "test_*.py"`：40 项离线回归；旧测试需 pywin32/Pillow/numpy，不连接 SW。

扩展后端是单独选装项，见 [backend-integration.md](references/backend-integration.md)；不需要外部后端即可使用本地零件工具。
