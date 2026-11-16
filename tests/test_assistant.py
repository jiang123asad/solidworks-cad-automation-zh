"""Offline orchestration tests; no installed SW, no backend CAD calls."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import cad_assistant as cad


class AssistantTests(unittest.TestCase):
    def parse(self, *args):
        return cad.parser().parse_args(args)

    def test_chinese_alias_and_no_implicit_cone_dimensions(self):
        args = self.parse('检查', 'example.SLDPRT', '--plan')
        self.assertEqual(args.action, 'inspect')
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.parse('密封锥', 'example.SLDPRT', '--out', 'new', '--end', 'hi')

    def test_plan_keeps_chinese_spaces_and_metacharacters_literal(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'中文 空格 & (轴).SLDPRT'
            source.write_bytes(b'fixture')
            out = Path(folder)/'新 输出'
            plan = cad.build_plan(self.parse('cone', str(source), '--out', str(out),
                                             '--width', '2', '--half-angle', '60', '--end', 'hi', '--plan'))
            self.assertIn(str(source), plan['command'])
            self.assertEqual(plan['expected_outputs'], [str(out/source.name)])
            self.assertFalse(out.exists())

    def test_existing_output_and_invalid_formats_block_before_spawn(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'a.SLDPRT'
            source.touch()
            with self.assertRaises(ValueError):
                cad.build_plan(self.parse('export', str(source), '--out', folder))
            for formats in ('step,step', 'exe', ''):
                with self.assertRaises(ValueError):
                    cad.build_plan(self.parse('export', str(source), '--out', str(Path(folder)/'new'), '--formats', formats))
            with self.assertRaises(ValueError):
                cad.build_plan(self.parse('export',str(source),'--out',str(Path(folder)/'new'),
                                          '--reports',str(Path(folder)/'new/reports')))

    def test_nonfinite_and_out_of_range_angles_rejected(self):
        with redirect_stderr(io.StringIO()):
            for number in ('nan', 'inf', '-1', '0'):
                with self.assertRaises(SystemExit):
                    self.parse('chamfer', 'a', '--out', 'b', '--width', number, '--angle', '15')
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'a.SLDPRT'
            source.touch()
            with self.assertRaises(ValueError):
                cad.build_plan(self.parse('chamfer', str(source), '--out', str(Path(folder)/'new'), '--width', '1', '--angle', '90'))

    def test_compare_rejects_output_inside_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder)/'old', Path(folder)/'new'
            a.mkdir(); b.mkdir()
            with self.assertRaises(ValueError):
                cad.build_plan(self.parse('compare', str(a), str(b), '--out', str(a/'reports')))

    def test_backend_pin_and_git_cleanliness(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'repo'
            (root/'scripts').mkdir(parents=True)
            (root/'scripts/sw_drawing_package.py').touch()
            python = Path(folder)/'python.exe'
            python.touch()
            config = Path(folder)/'backend.local.json'
            config.write_text(json.dumps(dict(backend='wzyn-drawing', root=str(root), python=str(python), revision=cad.PIN)), encoding='utf-8')
            def completed(text):
                return subprocess.CompletedProcess([], 0, stdout=text, stderr='')
            with patch.object(cad.subprocess, 'run', side_effect=[completed(cad.PIN+'\n'),completed('')]):
                self.assertEqual(cad.backend_config(config), (root,python))
            with patch.object(cad.subprocess, 'run', return_value=completed('another revision')):
                with self.assertRaises(ValueError):
                    cad.backend_config(config)
            with patch.object(cad.subprocess, 'run', side_effect=[completed(cad.PIN),completed(' M scripts/file.py')]):
                with self.assertRaises(ValueError):
                    cad.backend_config(config)

    def test_backend_configuration_cannot_supply_arbitrary_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder)/'config.json'
            config.write_text(json.dumps(dict(backend='wzyn-drawing',root=folder,python='python',revision=cad.PIN,command=['bad'])),encoding='utf-8')
            with self.assertRaises(ValueError):
                cad.backend_config(config)

    def test_external_pass_is_review_required_and_mixed_stdout_unknown(self):
        plan = dict(external=True)
        outputs = [dict(nonempty=True)]
        self.assertEqual(cad.classify_result(plan,0,'{"status":"pass"}',outputs),'review_required')
        self.assertEqual(cad.classify_result(plan,2,'{"status":"review_required"}',outputs),'review_required')
        self.assertEqual(cad.classify_result(plan,0,'progress\n{"status":"pass"}',outputs),'result_unknown')
        self.assertEqual(cad.classify_result(plan,0,'[]',outputs),'result_unknown')
        self.assertEqual(cad.classify_result(plan,0,'{"status":"pass"}',[dict(nonempty=False)]),'result_unknown')
        self.assertEqual(cad.classify_result(plan,1,'{"status":"blocked"}',[]),'failed')

    def test_local_zero_exit_does_not_hide_missing_output(self):
        self.assertEqual(cad.classify_result(dict(external=False),0,'',[dict(nonempty=False)]),'failed')
        self.assertEqual(cad.classify_result(dict(external=False),0,'',[dict(nonempty=True)]),'completed')
        self.assertEqual(cad.classify_result(dict(external=False),3221225477,'',[]),'result_unknown')

    def test_same_user_lock_blocks_another_process(self):
        with tempfile.TemporaryDirectory() as folder:
            with cad.session_guard(folder):
                code = 'import sys;sys.path.insert(0,sys.argv[1]);import cad_assistant as c\nwith c.session_guard(sys.argv[2]): pass'
                run = subprocess.run([sys.executable,'-B','-c',code,str(ROOT/'scripts'),folder],capture_output=True)
                self.assertNotEqual(run.returncode,0)
            with cad.session_guard(folder):
                pass

    def fixture_plan(self, source, output, code):
        return dict(action='export',command=[sys.executable,'-X','utf8','-B','-c',code],cwd=str(source.parent),
                    inputs=[str(source)],expected_outputs=[str(output)],external=False,
                    backend='offline-test',limitation='离线测试，不启动 SW')

    def test_success_records_fingerprints_and_clears_pending(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root/'input.SLDPRT',root/'out.step'
            source.write_bytes(b'source')
            code = 'from pathlib import Path;Path('+repr(str(output))+').write_bytes(b"output")'
            with redirect_stdout(io.StringIO()):
                result = cad.run_plan(self.fixture_plan(source,output,code),root/'reports',root/'guard')
            self.assertEqual(result,0)
            report = cad.read_json(next((root/'reports').glob('*/result.json')))
            self.assertEqual(report['input_sha256_before'],report['input_sha256_after'])
            self.assertFalse((root/'guard/pending.json').exists())
            self.assertTrue(next((root/'reports').glob('*/结果摘要.md')).is_file())

    def test_modified_source_forces_failure_and_next_task_is_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, output = root/'input.SLDPRT',root/'out.step'
            source.write_bytes(b'source')
            code = ('from pathlib import Path;Path('+repr(str(source))+').write_bytes(b"changed");'
                    'Path('+repr(str(output))+').write_bytes(b"output")')
            plan = self.fixture_plan(source,output,code)
            with redirect_stdout(io.StringIO()):
                result = cad.run_plan(plan,root/'reports',root/'guard')
            self.assertEqual(result,1)
            self.assertTrue((root/'guard/pending.json').exists())
            with self.assertRaises(ValueError):
                cad.run_plan(plan,root/'reports',root/'guard')

    def test_interrupt_keeps_pending_and_does_not_retry_child(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root/'input.SLDPRT'
            source.write_bytes(b'source')
            plan = self.fixture_plan(source,root/'out.step','pass')
            with patch.object(cad.subprocess,'Popen') as popen, redirect_stdout(io.StringIO()):
                popen.return_value.pid = 123456
                popen.return_value.wait.side_effect = KeyboardInterrupt()
                self.assertEqual(cad.run_plan(plan,root/'reports',root/'guard'),1)
                self.assertEqual(popen.call_count,1)
            record = cad.read_json(root/'guard/pending.json')
            self.assertEqual(record['status'],'result_unknown')
            self.assertEqual(record['child_pid'],123456)

    def test_environment_failure_does_not_block_future_tasks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            plan=dict(action='doctor',command=[sys.executable,'-c','raise SystemExit(1)'],cwd=folder,
                      inputs=[],expected_outputs=[],external=False,backend='offline-test',limitation='环境检查')
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cad.run_plan(plan,root/'reports',root/'guard'),1)
            self.assertFalse((root/'guard/pending.json').exists())

    def test_resolve_requires_confirmation_and_refuses_live_process(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaises(ValueError):
                cad.resolve_pending('yes')
            with patch.object(cad,'state_dir',return_value=root):
                cad.atomic_json(root/'pending.json',dict(pid=456))
                with patch.object(cad,'pid_alive',return_value=True),self.assertRaises(ValueError):
                    cad.resolve_pending('已核对SW状态')
                with patch.object(cad,'pid_alive',return_value=False),redirect_stdout(io.StringIO()):
                    self.assertEqual(cad.resolve_pending('已核对SW状态'),0)
                self.assertFalse((root/'pending.json').exists())
                self.assertEqual(len(list(root.glob('resolved-*.json'))),1)

    def test_setup_does_not_overwrite_an_existing_unmanaged_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'.venv').mkdir()
            with patch.object(cad,'ROOT',root), patch.object(cad.sys,'platform','win32'):
                with patch.object(cad.subprocess,'run') as run, self.assertRaises(ValueError):
                    cad.setup_environment()
                run.assert_not_called()

    def test_external_progress_log_uses_structured_sidecar(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            source=root/'input.SLDPRT';source.write_bytes(b'source')
            drawing,pdf,report=[root/name for name in ('drawing.slddrw','drawing.pdf','drawing_review_report.json')]
            code=('from pathlib import Path;print("backend progress before JSON");'+
                  ';'.join('Path('+repr(str(p))+').write_bytes(b"data")' for p in (drawing,pdf))+';'+
                  'Path('+repr(str(report))+').write_text(\'{"status":"pass"}\',encoding="utf-8")')
            plan=self.fixture_plan(source,drawing,code)
            plan.update(external=True,expected_outputs=list(map(str,(drawing,pdf,report))))
            with redirect_stdout(io.StringIO()):
                result=cad.run_plan(plan,root/'reports',root/'guard')
            self.assertEqual(result,2)
            self.assertFalse((root/'guard/pending.json').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
