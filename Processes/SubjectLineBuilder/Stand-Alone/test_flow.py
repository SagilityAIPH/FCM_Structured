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


def forwarded(app=None, *, allData=None, emaiDisplay=None, skip_capture=False, skip_cms=False):
    global botStop, data
    record(app, allData, emaiDisplay, skip_capture, skip_cms, botStop, data)
    data = allData
    botStop = False


def forwarded_exit(app=None, **kwargs):
    raise SystemExit(7)


def forwarded_failure(app=None, **kwargs):
    raise RuntimeError('Synthetic failure')


class SuppliedBuilderInputsTests(unittest.TestCase):
    def test_default_call_keeps_old_step_signature_and_result(self):
        runtime = {'botStop': False, 'data': {'stale': True}}
        result = runner.load_core().run_flow(runtime, steps=stopped)
        self.assertEqual(result, {'status': 'stopped', 'stage': 'subject_line_builder', 'data': {}})
        self.assertTrue(runtime['botStop'])

    def test_forwards_supplied_inputs_and_resets_runtime(self):
        calls = []
        fields, window, app = {'providerZip': '00000'}, object(), object()
        runtime = {'record': lambda *args: calls.append(args), 'botStop': False, 'data': {'stale': True}}
        result = runner.load_core().run_flow(runtime, steps=forwarded, app=app,
                                            allData=fields, emaiDisplay=window,
                                            skip_capture=True, skip_cms=True)
        self.assertEqual(calls, [(app, fields, window, True, True, True, {})])
        self.assertIs(calls[0][1], fields)
        self.assertIs(calls[0][2], window)
        self.assertEqual(result['status'], 'completed')
        self.assertIs(result['data'], fields)

    def test_missing_allData_raises_clear_value_error(self):
        with self.assertRaisesRegex(ValueError, 'allData'):
            runner.load_core()._load_steps()(skip_capture=True, emaiDisplay=object())

    def test_missing_emaiDisplay_raises_clear_value_error(self):
        with self.assertRaisesRegex(ValueError, 'emaiDisplay'):
            runner.load_core()._load_steps()(skip_capture=True, allData={})

    def test_flow_contains_input_validation_errors(self):
        for fields, window, missing in ((None, object(), 'allData'), ({}, None, 'emaiDisplay')):
            with self.subTest(missing=missing):
                result = runner.load_core().run_flow({}, allData=fields, emaiDisplay=window, skip_capture=True)
                self.assertEqual(result, {'status': 'failed', 'stage': 'subject_line_builder',
                                         'error': f'ValueError: skip_capture=True requires {missing}'})

    def test_new_path_contains_system_exit(self):
        runtime = {}
        result = runner.load_core().run_flow(runtime, steps=forwarded_exit,
                                            allData={}, emaiDisplay=object(), skip_capture=True, skip_cms=True)
        self.assertEqual(result, {'status': 'failed', 'stage': 'subject_line_builder',
                                 'error': 'Legacy builder exited before completion', 'exit_code': 7})
        self.assertTrue(runtime['botStop'])

    def test_new_path_contains_generic_exception(self):
        result = runner.load_core().run_flow({}, steps=forwarded_failure,
                                            allData={}, emaiDisplay=object(), skip_capture=True, skip_cms=True)
        self.assertEqual(result, {'status': 'failed', 'stage': 'subject_line_builder',
                                 'error': 'RuntimeError: Synthetic failure'})

    def test_real_guards_reach_tail_without_capture_or_cms(self):
        # Inject the real step with synthetic helpers; stop before any desktop work.
        fields = {'claimType': 'synthetic', 'customer': 'SYNTHETIC EMPLOYER',
                  'specialInstructions': '', 'providerZip': '00000'}
        window, seen = object(), []
        def tail_boundary(control):
            seen.append(control)
            raise SystemExit('synthetic tail boundary')
        runtime = {'GoodyearSearchFacilityName': lambda text: '',
                   'get_validation_missing': lambda data: [], 'focus_control': tail_boundary}
        result = runner.load_core().run_flow(runtime, steps=runner.load_core()._load_steps(),
                                            allData=fields, emaiDisplay=window,
                                            skip_capture=True, skip_cms=True)
        self.assertEqual(result['exit_code'], 'synthetic tail boundary')
        self.assertEqual(seen, [window])
        self.assertEqual(runtime['correctZipCode'], '00000')
        self.assertEqual(fields['customer'], 'SYNTHETIC EMPLOYER')


if __name__ == '__main__':
    unittest.main()
