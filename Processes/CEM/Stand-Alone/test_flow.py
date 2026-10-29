"""CEM synthetic scenarios and self-test report contract."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_cem_standalone_test_runner', HERE / 'run.py')
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


class ScenarioTests(unittest.TestCase):
    def test_every_scenario(self):
        rows = runner.scenario_rows()
        self.assertEqual(len(rows), 17)
        for name, expected, actual, passed in rows:
            with self.subTest(name=name):
                self.assertTrue(passed, (expected, actual))
                self.assertEqual(set(actual), set(runner.load_contract().new_result()))

    def test_self_test_report_and_exit_code(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'report.txt'
            done = subprocess.run([sys.executable, str(HERE / 'run.py'), '--self-test', '--report', str(report)],
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            contents = report.read_text(encoding='utf-8')
            self.assertIn('Scenarios: 17/17 passed', contents)
            self.assertIn('Smoke: PASS', contents)
            for name, *_ in runner.scenario_rows():
                self.assertIn(name + ' | ', contents)

    def test_scoped_scenario_exit(self):
        self.assertEqual(runner.main(['--scenario', 'request-submitted']), 0)
        self.assertEqual(runner.main(['--scenario', 'submit-uncertain']), 2)


if __name__ == '__main__':
    unittest.main()
