"""Offline controller tests; no Windows, CMS, database or PDF dependencies."""
import ast
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, PropertyMock, patch

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

    def test_legacy_exit_retains_blank_original_exception_and_builder_call_site(self):
        namespace = {}
        source = '\n' * 838 + (
            'def legacy_failure(app=None):\n'
            '    try:\n'
            '        value_pattern()\n'
            '    except Exception:\n'
            '        sys.exit(9)\n')
        exec(compile(source, 'legacy_steps.py', 'exec'), namespace)
        helpers = {}
        exec(compile('def value_pattern():\n    raise ValueError()\n',
                     'synthetic_value_pattern.py', 'exec'), helpers)
        runtime = {'sys': sys, 'value_pattern': helpers['value_pattern'],
                   'botStop': False, 'data': {'stale': True}}
        result = runner.load_core().run_flow(runtime, steps=namespace['legacy_failure'])
        self.assertEqual(result, {'status': 'failed', 'stage': 'subject_line_builder',
                                 'type': 'ValueError', 'error': 'ValueError (legacy_steps.py:841)',
                                 'exit_code': 9})
        self.assertTrue(runtime['botStop'])
        self.assertEqual(runtime['data'], {})

    def test_bare_legacy_exit_keeps_generic_result(self):
        runtime = {}
        self.assertEqual(runner.load_core().run_flow(runtime, steps=legacy_exit),
                         {'status': 'failed', 'stage': 'subject_line_builder',
                          'error': 'Legacy builder exited before completion', 'exit_code': None})
        self.assertTrue(runtime['botStop'])

    def test_direct_blank_exception_reports_action_not_helper_frame(self):
        def blank_failure(app=None):
            helper()
        def helper():
            raise RuntimeError()
        result = runner.load_core().run_flow({'helper': helper}, steps=blank_failure)
        self.assertEqual(result['type'], 'RuntimeError')
        self.assertEqual(result['error'],
                         f'RuntimeError (test_flow.py:{blank_failure.__code__.co_firstlineno + 1})')

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
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['stage'], 'subject_line_builder')
                self.assertEqual(result['type'], 'ValueError')
                self.assertRegex(result['error'],
                                 rf'^ValueError: skip_capture=True requires {missing} \(legacy_steps\.py:\d+\)$')

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
                                 'type': 'RuntimeError',
                                 'error': 'RuntimeError: Synthetic failure '
                                          f'(test_flow.py:{forwarded_failure.__code__.co_firstlineno + 1})'})

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


class EmployerWriteTests(unittest.TestCase):
    """Execute the real Employer source block, rebound by the shared controller."""

    @classmethod
    def setUpClass(cls):
        path = HERE.parent / 'Deploy-Ready' / 'legacy_steps.py'
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        builder = next(node for node in tree.body
                       if isinstance(node, ast.FunctionDef) and node.name == 'CreateSubjectLineBuilder')
        statements = next(node.body for node in ast.walk(builder)
                          if isinstance(node, ast.Try) and any(
                              isinstance(item, ast.Assign) and any(
                                  isinstance(target, ast.Name) and target.id == 'tbEmployer'
                                  for target in item.targets) for item in node.body))
        start = next(i for i, node in enumerate(statements)
                     if isinstance(node, ast.Assign) and any(
                         isinstance(target, ast.Name) and target.id == 'tbEmployer'
                         for target in node.targets))
        end = next(i for i in range(start + 1, len(statements))
                   if isinstance(statements[i], ast.Assign) and any(
                       isinstance(target, ast.Name) and target.id == 'tbClaimantFirst'
                       for target in statements[i].targets))
        # Include the next field's actual write to prove execution continues.
        function = ast.parse('def employer_step(app=None):\n    pass\n').body[0]
        function.body = (
            ast.parse('global botStop, data').body + statements[start:end + 2]
            + ast.parse('data = allData\nbotStop = False').body)
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                     str(path), 'exec'), namespace)
        cls.steps = staticmethod(namespace['employer_step'])

    def setUp(self):
        self.missing_pattern = type('NoPatternInterfaceError', (Exception,), {})
        self.fields = {'customer': 'Synthetic Employer MiXeD', 'claimantFirst': 'Synthetic'}
        self.employer = Mock(handle=1234)
        self.claimant = Mock()
        self.dlg = Mock()
        controls = {'tbEmployer': self.employer, 'tbClaimantFirst': self.claimant,
                    'tbCustomer': Mock()}
        self.dlg.child_window.side_effect = lambda **selector: SimpleNamespace(
            wrapper_object=lambda: controls[selector['auto_id']])
        self.native = Mock(handle=1234)
        self.native.friendly_class_name.return_value = 'Edit'
        self.native.style.return_value = 0
        self.native.window_text.return_value = self.fields['customer']
        self.desktop = Mock()
        self.desktop.return_value.window.return_value.wrapper_object.return_value = self.native
        self.win32con = SimpleNamespace(WM_SETTEXT=12, SMTO_ABORTIFHUNG=2, ES_READONLY=2048)
        self.win32gui = SimpleNamespace(IsWindow=Mock(return_value=True),
                                       SendMessageTimeout=Mock(return_value=(1, 1)))
        self.runtime = {'allData': self.fields, 'dlg': self.dlg, 'Desktop': self.desktop,
                        'focus_control': Mock(), 'time': SimpleNamespace(sleep=Mock()),
                        'uia_defines': SimpleNamespace(NoPatternInterfaceError=self.missing_pattern)}
        self.module_patch = patch.dict(sys.modules, {'win32con': self.win32con,
                                                     'win32gui': self.win32gui})
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)

    def run_step(self, missing=True):
        if missing:
            self.employer.iface_value.SetValue.side_effect = self.missing_pattern()
        return runner.load_core().run_flow(self.runtime, steps=self.steps)

    def assert_failed(self, result, kind, message):
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['type'], kind)
        self.assertIn(message, result['error'])
        self.assertNotIn(self.fields['customer'], result['error'])
        self.assertTrue(self.runtime['botStop'])
        self.assertEqual(self.runtime['data'], {})
        self.claimant.iface_value.SetValue.assert_not_called()

    def test_uia_success_does_not_use_native_fallback(self):
        self.assertEqual(self.run_step(missing=False)['status'], 'completed')
        self.employer.iface_value.SetValue.assert_called_once_with(self.fields['customer'])
        self.desktop.assert_not_called()
        self.win32gui.SendMessageTimeout.assert_not_called()
        self.claimant.iface_value.SetValue.assert_called_once_with('Synthetic')

    def test_missing_pattern_writes_same_hwnd_verifies_exact_case_and_continues(self):
        # Missing iface_value itself (not just SetValue) is the real UIA failure.
        type(self.employer).iface_value = PropertyMock(side_effect=self.missing_pattern())
        self.assertEqual(self.run_step(missing=False)['status'], 'completed')
        self.dlg.child_window.assert_any_call(auto_id='tbEmployer', control_type='Edit')
        self.desktop.assert_called_once_with(backend='win32')
        self.desktop.return_value.window.assert_called_once_with(handle=1234)
        self.native.verify_actionable.assert_called_once_with()
        self.win32gui.SendMessageTimeout.assert_called_once_with(
            1234, 12, 0, self.fields['customer'], 2, 5000)
        self.native.window_text.assert_called_once_with()
        self.claimant.iface_value.SetValue.assert_called_once_with('Synthetic')

    def test_unrelated_uia_exception_does_not_fallback(self):
        self.employer.iface_value.SetValue.side_effect = ValueError('Synthetic UIA failure')
        self.assert_failed(self.run_step(missing=False), 'ValueError', 'Synthetic UIA failure')
        self.desktop.assert_not_called()
        self.win32gui.SendMessageTimeout.assert_not_called()

    def test_real_guarded_function_rebound_to_legacy_namespace_reaches_next_field(self):
        self.fields.update(claimType='synthetic', specialInstructions='', providerZip='00000')
        self.employer.iface_value.SetValue.side_effect = self.missing_pattern()
        self.claimant.iface_value.SetValue.side_effect = SystemExit('synthetic next field boundary')
        self.desktop.side_effect = lambda backend: (
            self.desktop.return_value if backend == 'win32'
            else SimpleNamespace(window=lambda **kwargs: self.dlg))
        self.runtime.update(
            sys=sys, safe_click=Mock(), GoodyearSearchFacilityName=lambda text: '',
            get_validation_missing=lambda fields: [])
        result = runner.load_core().run_flow(
            self.runtime, steps=runner.load_core()._load_steps(),
            allData=self.fields, emaiDisplay=Mock(), skip_capture=True, skip_cms=True)
        self.assertEqual(result['exit_code'], 'synthetic next field boundary')
        self.win32gui.SendMessageTimeout.assert_called_once_with(
            1234, 12, 0, self.fields['customer'], 2, 5000)
        self.native.window_text.assert_called_once_with()
        self.claimant.iface_value.SetValue.assert_called_once_with('Synthetic')

    def test_missing_wrong_or_unwritable_control_fails_before_native_write(self):
        cases = (
            ('zero handle', self.employer, 'handle', 0, 'missing'),
            ('missing handle', self.win32gui.IsWindow, 'return_value', False, 'missing'),
            ('wrong handle', self.native, 'handle', 5678, 'identity changed'),
            ('wrong class', self.native.friendly_class_name, 'return_value', 'Button', 'not an Edit'),
            ('disabled', self.native.verify_actionable, 'side_effect',
             RuntimeError('Synthetic disabled control'), 'disabled'),
            ('hidden', self.native.verify_actionable, 'side_effect',
             RuntimeError('Synthetic hidden control'), 'hidden'),
            ('read-only', self.native.style, 'return_value', 2048, 'read-only'),
        )
        for label, target, attribute, value, message in cases:
            with self.subTest(case=label):
                previous = getattr(target, attribute)
                try:
                    setattr(target, attribute, value)
                    self.assert_failed(self.run_step(), 'RuntimeError', message)
                    self.win32gui.SendMessageTimeout.assert_not_called()
                finally:
                    setattr(target, attribute, previous)

    def test_native_write_refusal_exception_or_readback_mismatch_fails(self):
        cases = (
            ('api refusal', self.win32gui.SendMessageTimeout, 'return_value', (0, 1),
             'RuntimeError', 'write failed'),
            ('message refusal', self.win32gui.SendMessageTimeout, 'return_value', (1, 0),
             'RuntimeError', 'write failed'),
            ('native exception', self.win32gui.SendMessageTimeout, 'side_effect',
             OSError('Synthetic native failure'),
             'OSError', 'Synthetic native failure'),
            ('different case', self.native.window_text, 'return_value', self.fields['customer'].upper(),
             'RuntimeError', 'verification failed'),
            ('readback failure', self.native.window_text, 'side_effect',
             OSError('Synthetic readback failure'), 'OSError', 'Synthetic readback failure'),
        )
        for label, target, attribute, value, kind, message in cases:
            with self.subTest(case=label):
                previous = getattr(target, attribute)
                try:
                    setattr(target, attribute, value)
                    self.assert_failed(self.run_step(), kind, message)
                finally:
                    setattr(target, attribute, previous)


if __name__ == '__main__':
    unittest.main()
