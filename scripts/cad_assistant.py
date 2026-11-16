"""中文任务入口。只执行白名单脚本；外部工程图后端必须显式配置。"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
PIN = '36bc337357723b9763759ff06e4a1afab990b823'
STATUS = {'completed': '执行完成', 'review_required': '需要人工检查',
          'failed': '执行失败', 'result_unknown': '结果待确认', 'blocked': '未执行'}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('请输入大于零的有限数值')
    return number


def native_file(value, suffixes=('.sldprt',)):
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in suffixes:
        raise ValueError('输入文件类型不支持：' + str(path))
    return path


def empty_destination(value):
    path = Path(value).expanduser().resolve()
    if path.exists():
        raise ValueError('请选一个尚不存在的输出文件夹：' + str(path))
    return path


def backend_config(path):
    config = read_json(Path(path).resolve(strict=True))
    if set(config) != {'backend', 'root', 'python', 'revision'}:
        raise ValueError('后端配置只接受 backend/root/python/revision 四项')
    if config['backend'] != 'wzyn-drawing' or config['revision'] != PIN:
        raise ValueError('当前只适配固定提交的 wzyn-drawing 后端，不能自动换版')
    for key in ('root', 'python'):
        if not isinstance(config[key], str) or not Path(config[key]).is_absolute():
            raise ValueError(key + ' 必须是本机绝对路径')
    root = Path(config['root']).resolve(strict=True)
    python = Path(config['python']).resolve(strict=True)
    if not root.is_dir() or not python.is_file() or python.suffix.lower() != '.exe':
        raise ValueError('请提供后端仓库目录和独立环境的 python.exe')
    if not (root/'scripts/sw_drawing_package.py').is_file():
        raise ValueError('后端缺少 scripts/sw_drawing_package.py')
    # Verify Git revision and tracked modifications; no installation or execution of backend code.
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0')
    def git(*args):
        run = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                             text=True, encoding='utf-8', errors='replace', timeout=15, env=env)
        if run.returncode:
            raise ValueError('无法核对后端 Git 状态；请安装 Git 并使用独立的干净检出')
        return run.stdout.strip()
    if git('rev-parse', 'HEAD') != PIN:
        raise ValueError('后端实际提交与适配提交不一致')
    if git('status', '--porcelain', '--untracked-files=no'):
        raise ValueError('后端有已跟踪文件修改，请使用独立干净检出')
    return root, python


def build_plan(args):
    """Validate all CLI inputs before spawning SW; return data-only execution plan."""
    action = args.action
    python = Path(sys.executable)
    cwd = ROOT
    inputs, outputs = [], []
    external = False
    if action == 'drawing':
        cwd, python = backend_config(args.backend_config)
        spec_path = Path(args.spec).resolve(strict=True)
        spec = read_json(spec_path)
        if not isinstance(spec, dict) or not isinstance(spec.get('sourceModel'), str):
            raise ValueError('DrawingSpec 必须含 sourceModel')
        source = Path(spec['sourceModel'])
        if not source.is_absolute():
            raise ValueError('DrawingSpec.sourceModel 必须是绝对路径')
        source = native_file(source, ('.sldprt', '.sldasm'))
        out = empty_destination(args.out)
        command = [str(python), '-X', 'utf8', '-B', str(cwd/'scripts/sw_drawing_package.py'),
                   '--spec', str(spec_path), '--output-dir', str(out), '--filename', 'drawing.slddrw']
        inputs = [spec_path, source]
        outputs = [out/'drawing.slddrw', out/'drawing.pdf', out/'drawing_review_report.json']
        external = True
        limit = '基础三视图/PDF 已本机联调；完整尺寸与关联仍需人工检查，不能作为自动生产验收。'
    else:
        command = [str(python), '-X', 'utf8', '-B']
        if action == 'doctor':
            command += [str(ROOT/'scripts/doctor.py')]
            limit = '仅检查本机环境，不连接或启动 SW，不验证附加模块许可证。'
        elif action in ('inspect', 'render', 'export', 'chamfer', 'cone'):
            suffixes = ('.sldprt', '.sldasm') if action in ('render', 'export') else ('.sldprt',)
            source = native_file(args.file, suffixes)
            inputs = [source]
            if action == 'inspect':
                command += [str(ROOT/'scripts/inspect_model.py'), str(source), '--features']
                if args.edges:
                    command.append('--edges')
                limit = '检查零件全部实体与特征树；汇总指标不能证明几何等价。'
            else:
                out = empty_destination(args.out)
                if action == 'render':
                    command += [str(ROOT/'scripts/render.py'), str(source), str(out/(source.stem+'.png')), args.view]
                    outputs = [out/(source.stem+'.png')]
                    limit = '保存标准视图图形区 PNG；不是照片级渲染或工程图验收。'
                elif action == 'export':
                    formats = [s.strip().lower().lstrip('.') for s in args.formats.split(',')]
                    if not formats or len(set(formats)) != len(formats) or any(s not in ('x_t','step','stp','igs','iges') for s in formats):
                        raise ValueError('格式限 x_t/step/stp/igs/iges，且不能重复')
                    command += [str(ROOT/'scripts/export_neutral.py'), str(source), '--out', str(out), '--fmt', ','.join(formats)]
                    outputs = [out/(source.stem+'.'+fmt) for fmt in formats]
                    limit = '仅保存与非空文件检查；使用当前 SW 导出首选项，不证明接收软件兼容。'
                else:
                    angle = args.angle if action == 'chamfer' else args.half_angle
                    if not 0 < angle < 90:
                        raise ValueError('角度必须大于 0 且小于 90 度')
                    if action == 'chamfer':
                        command += [str(ROOT/'scripts/seal_chamfer.py'), str(source), '--out', str(out), '--width', str(args.width), '--angle', str(angle)]
                    else:
                        command += [str(ROOT/'scripts/add_cone.py'), str(out), str(source), '--width', str(args.width), '--half-angle', str(angle), '--end', args.end]
                    outputs = [out/source.name]
                    limit = '仅支持脚本规定的单轴、轴对齐几何；使用副本，继承原脚本局部/体积与保存回读检查。'
        elif action == 'compare':
            old, new = (Path(v).resolve(strict=True) for v in (args.old, args.new))
            if not old.is_dir() or not new.is_dir():
                raise ValueError('新旧版本输入必须都是文件夹')
            # Exclude reports from either input to keep snapshots and comparisons stable.
            out = empty_destination(args.out)
            if any(out == p or p in out.parents for p in (old, new)):
                raise ValueError('对比输出必须放在两个输入文件夹之外')
            inputs = sorted({p for folder in (old, new) for p in folder.rglob('*')
                             if p.is_file() and p.suffix.lower() in ('.sldprt','.sldasm')})
            outputs = [out/'diff.txt', out/'diff.json']
            command += [str(ROOT/'scripts/compare_versions.py'), str(old), str(new), '--out', str(outputs[0]), '--json', str(outputs[1])]
            limit = '仅比较汇总指标和特征树；不支持装配几何等价判定。'
        else:
            raise ValueError('没有可执行的任务：' + action)
    if outputs:
        report_root = Path(args.reports).resolve()
        if report_root == out or out in report_root.parents:
            raise ValueError('任务记录目录不能放进本次尚未创建的输出目录，请另选 --reports')
    return dict(action=action, command=command, cwd=str(cwd), inputs=[str(p) for p in inputs],
                expected_outputs=[str(p) for p in outputs], external=external, limitation=limit,
                backend='wzyn-drawing@'+PIN if external else 'local-com')


def state_dir():
    # One directory per Windows user, shared across copies of this skill.
    return Path(tempfile.gettempdir())/'solidworks-cad-automation-session'


@contextmanager
def session_guard(folder=None):
    folder = Path(folder) if folder else state_dir()
    folder.mkdir(parents=True, exist_ok=True)
    lock = (folder/'session.lock').open('a+b')
    acquired = False
    try:
        if lock.seek(0, 2) == 0:
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise ValueError('另一个中文入口任务仍在运行，请等它结束') from exc
        yield folder
    finally:
        if acquired:
            lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def pid_alive(pid):
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return ctypes.get_last_error() != 87  # Access denied is inconclusive; block.
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def resolve_pending(confirmation):
    if confirmation != '已核对SW状态':
        raise ValueError('先人工核对 SW 文档、输出和任务进程，再传 --confirm 已核对SW状态')
    with session_guard() as folder:
        pending = folder/'pending.json'
        if not pending.exists():
            print('没有待确认任务。')
            return 0
        record = read_json(pending)
        if any(pid_alive(record[key]) for key in ('pid', 'child_pid') if record.get(key)):
            raise ValueError('记录中的任务进程仍在运行，不能清除状态')
        archive = folder/('resolved-'+uuid.uuid4().hex+'.json')
        pending.rename(archive)
        print('已归档待确认状态。此操作不撤销或重做 CAD。')
    return 0


def classify_result(plan, code, log, output_records):
    if code < 0 or code > 255:
        return 'result_unknown'
    if plan['external']:
        # The pinned CLI prints one final JSON object. Unknown/mixed stdout fails closed.
        try:
            response = json.loads(log)
        except (ValueError, TypeError):
            return 'result_unknown'
        if not isinstance(response, dict):
            return 'result_unknown'
        state = response.get('status')
        if state in ('failed', 'fail', 'blocked'):
            return 'failed'
        if code in (0, 2) and state in ('pass', 'pilot', 'review_required') and all(r['nonempty'] for r in output_records):
            # Never turn an external drawing result into manufacturing acceptance.
            return 'review_required'
        return 'result_unknown'
    if code != 0:
        return 'failed'
    return 'completed' if all(r['nonempty'] for r in output_records) else 'failed'


def run_plan(plan, reports, guard_folder=None):
    with session_guard(guard_folder) as folder:
        pending = folder/'pending.json'
        if pending.exists():
            raise ValueError('上个任务结果待确认：'+str(pending)+'；请人工核对后使用 resolve-pending')
        before = {p: digest(p) for p in plan['inputs']}
        reports = Path(reports).resolve()
        task = reports/(datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8])
        task.mkdir(parents=True, exist_ok=False)
        record = dict(schema_version='1.0', task_id=task.name, status='result_unknown',
                      started_utc=datetime.now(timezone.utc).isoformat(), plan=plan,
                      input_sha256_before=before, pid=os.getpid(), validation=[], outputs=[])
        atomic_json(task/'result.json', record)
        atomic_json(pending, record)
        env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
        if plan['external']:
            # Do not inject this skill's module paths into an independent backend.
            env.pop('PYTHONPATH', None)
            env.pop('PYTHONHOME', None)
        try:
            with (task/'console.log').open('wb') as stream:
                process = subprocess.Popen(plan['command'], cwd=plan['cwd'], env=env,
                                           stdout=stream, stderr=subprocess.STDOUT, shell=False)
                record['child_pid'] = process.pid
                atomic_json(pending, record)
                code = process.wait()  # No false promise that timing out cancels a COM mutation.
            log = (task/'console.log').read_text(encoding='utf-8', errors='replace')
            outputs = [dict(path=p, nonempty=Path(p).is_file() and Path(p).stat().st_size > 0)
                       for p in plan['expected_outputs']]
            result_payload = log
            if plan['external']:
                # The pinned backend emits progress before its JSON. Use its named report
                # in this task's previously absent output directory, never scrape log text.
                report_path = Path(plan['expected_outputs'][-1])
                result_payload = report_path.read_text(encoding='utf-8-sig') if report_path.is_file() else ''
            status = classify_result(plan, code, result_payload, outputs)
            after = {p: digest(p) if Path(p).is_file() else None for p in before}
            unchanged = all(after[p] == sha for p, sha in before.items())
            if not unchanged:
                status = 'failed'
            record.update(status=status, child_exit_code=code, outputs=outputs, input_sha256_after=after,
                          validation=[dict(check='输入文件SHA256保持', passed=unchanged),
                                      dict(check='预期输出均存在且非空', passed=all(r['nonempty'] for r in outputs))],
                          ended_utc=datetime.now(timezone.utc).isoformat())
        except BaseException as exc:
            # Popen errors before a child exists are known not to have executed CAD.
            record.update(status='result_unknown' if record.get('child_pid') else 'blocked',
                          error=type(exc).__name__+': '+str(exc))
        atomic_json(task/'result.json', record)
        if record['status'] in ('result_unknown', 'failed') and plan['action'] != 'doctor':
            atomic_json(pending, record)
        else:
            pending.unlink()
        summary = ('# SolidWorks 中文任务结果\n\n状态：'+STATUS[record['status']]+'\n\n任务：'+plan['action']+
                   '\n\n后端：'+plan['backend']+'\n\n范围：'+plan['limitation']+
                   '\n\n此报告只复述执行与文件检查；具体尺寸和生产适用性按任务验收。'+
                   '\n\n详细记录：result.json；执行日志：console.log。日志可能含路径及模型信息。\n')
        if record.get('outputs'):
            summary += '\n输出检查：\n\n'+'\n'.join('- '+('文件非空：' if item['nonempty'] else '缺失或空文件：')+item['path'] for item in record['outputs'])+'\n'
        if record.get('validation'):
            summary += '\n检查结果：\n\n'+'\n'.join('- '+item['check']+'：'+('通过' if item['passed'] else '未通过') for item in record['validation'])+'\n'
        if record.get('error'):
            summary += '\n异常：'+record['error']+'\n'
        (task/'结果摘要.md').write_text(summary, encoding='utf-8')
        print(STATUS[record['status']]+'；任务报告：'+str(task))
        print('验证范围：'+plan['limitation'])
        if record['status'] in ('failed', 'result_unknown') and plan['action'] != 'doctor':
            print('已暂停后续任务；先检查日志、SW 状态与可能生成的文件，再人工清除待确认状态。')
        return 0 if record['status'] == 'completed' else 2 if record['status'] == 'review_required' else 1


def show_capabilities():
    data = read_json(ROOT/'capabilities.json')
    print('本地“已实测”指历史 SW2026 SP1.1 脚本；新入口已通过本轮实机流程；扩展后端仅基础三视图/PDF，完整尺寸待人工验收。')
    for item in data['capabilities']:
        print(item['name']+'：'+item['status']+'；'+item['delivery']+'；'+item['limitation'])
    return 0


def setup_environment():
    """Explicit installation command; never invoked by doctor or normal CAD tasks."""
    if sys.platform != 'win32' or sys.version_info < (3, 9):
        raise ValueError('安装基础环境需要 Windows 和 Python 3.9+')
    import venv
    destination = ROOT/'.venv'
    marker = destination/'.cad-assistant-managed'
    python = destination/'Scripts/python.exe'
    if destination.exists() and (not marker.is_file() or not python.is_file()):
        raise ValueError('已有非本助手管理或不完整的 .venv，请先人工检查，不会覆盖或删除')
    if not destination.exists():
        print('正在本文件夹创建独立 .venv；不会修改系统 Python 或 AI 宿主配置。')
        venv.EnvBuilder(with_pip=True).create(destination)
        marker.write_text('solidworks-cad-automation\n', encoding='utf-8')
    print('将通过当前 pip 索引下载 pywin32 和 Pillow；详细输出如下。')
    run = subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(ROOT/'requirements.txt')], shell=False)
    if run.returncode:
        print('依赖安装失败，请检查上方网络或版本提示，再重新运行安装命令。')
        return 1
    print('基础环境准备完成。请双击“启动助手.cmd”；GUI helper 的 numpy 需另外按需安装。')
    return 0


def parser():
    ap = argparse.ArgumentParser(description='中文 SolidWorks 助手：统一检查、改型、导出与可选工程图后端。')
    sub = ap.add_subparsers(dest='action', required=True)
    for name, aliases, help_text in [
        ('capabilities',['能力'],'查看能力状态，不启动 SW'),
        ('doctor',['诊断'],'检查环境，不启动 SW'),
        ('setup',['安装环境'],'显式下载基础依赖到本包 .venv，不修改宿主配置'),
        ('inspect',['检查'],'检查一个零件'),
        ('render',['截图'],'导出模型图形区 PNG'),
        ('export',['导出'],'导出中性格式'),
        ('chamfer',['倒角'],'两端外圆边倒角'),
        ('cone',['密封锥'],'指定端密封锥'),
        ('compare',['对比'],'对比两版零件目录'),
        ('drawing',['工程图'],'实验：调用已配置的固定版本后端'),
        ('backend-check',['后端检查'],'只检查外部后端配置和 Git 提交'),
        ('resolve-pending',['恢复'],'人工核对后解除待确认状态'),
        ('menu',['菜单'],'中文交互菜单')]:
        p = sub.add_parser(name, aliases=aliases, help=help_text, description=help_text)
        p.set_defaults(action=name)
        if name in ('inspect','render','export','chamfer','cone'):
            p.add_argument('file', help='已保存、已关闭的输入文件')
        if name in ('render','export','chamfer','cone','compare','drawing'):
            p.add_argument('--out', required=True, help='尚不存在的输出文件夹')
        if name in ('doctor','inspect','render','export','chamfer','cone','compare','drawing'):
            p.add_argument('--plan', action='store_true', help='仅检查输入并显示计划，不启动 SW')
            p.add_argument('--reports', default=str(Path.cwd()/'out/task-reports'), help='本机任务记录目录')
        if name == 'inspect':
            p.add_argument('--edges', action='store_true', help='额外列出圆边')
        if name == 'render':
            p.add_argument('--view', choices=('iso','front','top','right'), default='iso', help='iso 等轴/front 正视/top 俯视/right 右视')
        if name == 'export':
            p.add_argument('--formats', default='x_t,step', help='逗号分隔：x_t,step,stp,igs,iges')
        if name in ('chamfer','cone'):
            p.add_argument('--width', type=positive, required=True, help='宽度，mm；必须明确填写')
        if name == 'chamfer':
            p.add_argument('--angle', type=positive, required=True, help='倒角角度，度')
        if name == 'cone':
            p.add_argument('--half-angle', type=positive, required=True, help='相对回转轴的半角，度')
            p.add_argument('--end', choices=('lo','hi'), required=True, help='lo 低坐标端 / hi 高坐标端')
        if name == 'compare':
            p.add_argument('old', help='旧版零件目录')
            p.add_argument('new', help='新版零件目录')
        if name in ('drawing','backend-check'):
            p.add_argument('--backend-config', required=True, help='本机后端 JSON 配置，不随公开包分发')
        if name == 'drawing':
            p.add_argument('--spec', required=True, help='固定版本上游 DrawingSpec JSON；sourceModel 必须为绝对路径')
        if name == 'resolve-pending':
            p.add_argument('--confirm', required=True, help='人工核对后填：已核对SW状态')
    return ap


def ask_path(prompt):
    return input(prompt).strip().strip('"')


def menu():
    while True:
        print('\n中文 SolidWorks 助手\n1 环境检查  2 能力范围  3 检查零件  4 导出 STEP/Parasolid\n5 两端倒角  6 密封锥  7 标准视图 PNG  8 目录对比  9 后端配置检查  0 退出')
        selection = input('选择编号：').strip()
        if selection == '0':
            return 0
        try:
            if selection in ('1','2'):
                argv = ['doctor' if selection == '1' else 'capabilities']
            elif selection in ('3','4','5','6','7'):
                action = {'3':'inspect','4':'export','5':'chamfer','6':'cone','7':'render'}[selection]
                argv = [action, ask_path('输入文件路径：')]
                if action != 'inspect':
                    argv += ['--out', ask_path('新输出文件夹（尚不存在）：')]
                if action in ('chamfer','cone'):
                    argv += ['--width', input('宽度 mm：').strip()]
                    argv += ['--angle' if action == 'chamfer' else '--half-angle', input('角度（密封锥填相对轴半角）度：').strip()]
                if action == 'cone':
                    argv += ['--end', input('端部 lo/hi：').strip()]
            elif selection == '8':
                argv = ['compare', ask_path('旧版目录：'), ask_path('新版目录：'), '--out', ask_path('新输出目录：')]
            elif selection == '9':
                argv = ['backend-check', '--backend-config', ask_path('本机后端配置 JSON：')]
            else:
                print('请输入菜单中的编号。')
                continue
            result = main(argv)
            if result:
                print('请先处理提示的问题；不要直接重复写操作。')
        except SystemExit:
            print('参数有误，请按提示重新输入。')
        except (EOFError, KeyboardInterrupt):
            return 1


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    args = parser().parse_args(argv)
    try:
        if args.action == 'menu':
            return menu()
        if args.action == 'setup':
            return setup_environment()
        if args.action == 'capabilities':
            return show_capabilities()
        if args.action == 'resolve-pending':
            return resolve_pending(args.confirm)
        if args.action == 'backend-check':
            root, python = backend_config(args.backend_config)
            print('固定版本和入口文件检查通过：'+str(root)+'；Python：'+str(python))
            print('尚未导入依赖、启动 SW 或验证工程图。')
            return 0
        plan = build_plan(args)
        if args.plan:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
            return 0
        if sys.platform != 'win32':
            raise ValueError('CAD 执行需要 Windows；当前环境可查看能力、使用 --plan')
        required = [] if args.action == 'doctor' or plan['external'] else ['pythoncom','win32com']
        if args.action == 'render':
            required.append('PIL')
        missing = [name for name in required if importlib.util.find_spec(name) is None]
        if missing:
            raise ValueError('当前 Python 缺少：'+', '.join(missing)+'；请按 INSTALL.md 配置，不会自动安装')
        return run_plan(plan, args.reports)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print('未执行：'+str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
