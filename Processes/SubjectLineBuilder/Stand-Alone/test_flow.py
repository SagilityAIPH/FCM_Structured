"""Offline controller tests; no Windows, CMS, database or PDF dependencies."""
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('subject_runner_test', HERE / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def success(app=None):
    global botStop, data
    helper(app)
    data = {'claimNumber': 'TEST-001'}
    botStop = False


def stopped(app=None):
    return


def failed(app=None):
    raise RuntimeError('Synthetic failure')


def legacy_exit(app=None):
    raise SystemExit()


class SubjectLineFlowTests(unittest.TestCase):
    def test_completion_uses_same_runtime_and_app(self):
        calls = []
        app = object()
        runtime = {'helper': calls.append}
        result = runner.load_core().run_flow(runtime, app=app, steps=success)
        self.assertEqual(result['status'], 'completed')
        self.assertIs(result['data'], runtime['data'])
        self.assertEqual(calls, [app])
        self.assertFalse(runtime['botStop'])

    def test_stop_does_not_return_previous_claim(self):
        runtime = {'botStop': False, 'data': {'claimNumber': 'STALE'}}
        result = runner.load_core().run_flow(runtime, steps=stopped)
        self.assertEqual(result['status'], 'stopped')
        self.assertEqual(result['data'], {})
        self.assertTrue(runtime['botStop'])

    def test_exceptions_and_legacy_exit_fail_without_killing_host(self):
        for action in (failed, legacy_exit):
            with self.subTest(action=action.__name__):
                runtime = {}
                result = runner.load_core().run_flow(runtime, steps=action)
                self.assertEqual(result['status'], 'failed')
                self.assertTrue(runtime['botStop'])

    def test_steps_load_without_windows_dependencies(self):
        steps = runner.load_core()._load_steps()
        self.assertEqual(steps.__name__, 'CreateSubjectLineBuilder')

    def test_downstream_processes_are_not_called(self):
        def forbidden():
            self.fail('Standalone builder must not run downstream steps')
        runtime = {'CompleteTriageAndExportAttachment': forbidden,
                   'OpenUnity': forbidden, 'CompleteAssignment': forbidden,
                   'helper': lambda app: None}
        self.assertEqual(runner.load_core().run_flow(runtime, steps=success)['status'], 'completed')


if __name__ == '__main__':
    unittest.main()
