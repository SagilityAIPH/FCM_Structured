"""Offline controller tests; no Windows, CMS, database or PDF dependencies."""
import ast
import importlib.util
from pathlib import Path
import re
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
        self.dlg = Mock(handle=100)
        self.dlg.process_id.return_value = 77
        controls = {'tbEmployer': self.employer, 'tbClaimantFirst': self.claimant,
                    'tbCustomer': Mock()}
        self.dlg.child_window.side_effect = lambda **selector: SimpleNamespace(
            wrapper_object=lambda: controls[selector['auto_id']])
        self.native = Mock(handle=1234)
        self.native.friendly_class_name.return_value = 'Edit'
        self.native.style.return_value = 0
        self.native.window_text.return_value = self.fields['customer']
        self.other_edit = Mock(handle=2222)
        self.other_edit.friendly_class_name.return_value = 'Edit'
        self.native_builder = Mock(handle=100)
        self.native_builder.descendants.return_value = [self.other_edit, self.native]
        self.employer_info = SimpleNamespace(
            handle=1234, automation_id='tbEmployer', process_id=77)
        self.other_info = SimpleNamespace(
            handle=2222, automation_id='tbClaimantLast', process_id=77)
        self.native_desktop, self.uia_desktop = Mock(), Mock()
        self.native_desktop.window.side_effect = lambda handle: SimpleNamespace(
            wrapper_object=lambda: {100: self.native_builder, 1234: self.native}[handle])
        self.uia_desktop.window.side_effect = lambda **selector: SimpleNamespace(
            wrapper_object=lambda: SimpleNamespace(element_info={
                1234: self.employer_info, 2222: self.other_info}[selector['handle']])
        ) if 'handle' in selector else self.dlg
        self.desktop = Mock()
        self.desktop.side_effect = lambda backend: (
            self.native_desktop if backend == 'win32' else self.uia_desktop)
        self.win32con = SimpleNamespace(WM_SETTEXT=12, SMTO_ABORTIFHUNG=2, ES_READONLY=2048)
        self.win32gui = SimpleNamespace(IsWindow=Mock(return_value=True),
                                       IsChild=Mock(return_value=True),
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
        self.native_desktop.window.assert_called_once_with(handle=1234)
        self.native_builder.descendants.assert_not_called()
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
        self.employer.handle = 0
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
            ('missing builder', self.win32gui.IsWindow, 'return_value', False, 'builder native window is missing'),
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

    def test_zero_or_stale_hwnd_recovers_only_named_native_edit_and_continues(self):
        for handle in (0, 9999):
            with self.subTest(handle=handle):
                self.employer.handle = handle
                self.win32gui.IsWindow.side_effect = lambda hwnd: hwnd != 9999
                self.assertEqual(self.run_step()['status'], 'completed')
                self.native_builder.descendants.assert_called()
                self.win32gui.SendMessageTimeout.assert_called_once_with(
                    1234, 12, 0, self.fields['customer'], 2, 5000)
                self.claimant.iface_value.SetValue.assert_called_once_with('Synthetic')
                self.other_edit.window_text.assert_not_called()
                self.win32gui.SendMessageTimeout.reset_mock()
                self.claimant.iface_value.SetValue.reset_mock()

    def test_recovery_rejects_missing_ambiguous_or_foreign_identity_without_writes(self):
        self.employer.handle = 0
        cases = (
            ('no match', self.native_builder.descendants, 'return_value',
             [self.other_edit], 'no matching Edit'),
            ('multiple matches', self.other_info, 'automation_id',
             'tbEmployer', 'multiple matching Edits'),
            ('cross process', self.employer_info, 'process_id', 88, 'another process'),
            ('outside builder', self.win32gui.IsChild, 'return_value',
             False, 'outside the current builder'),
            ('wrong identity', self.employer_info, 'handle', 3333, 'identity changed'),
            ('stale recovered handle', self.win32gui.IsWindow, 'side_effect',
             lambda hwnd: hwnd != 1234, 'identity changed'),
        )
        for case, target, attribute, value, message in cases:
            with self.subTest(case=case):
                previous = getattr(target, attribute)
                try:
                    setattr(target, attribute, value)
                    self.assert_failed(self.run_step(), 'RuntimeError', message)
                    self.win32gui.SendMessageTimeout.assert_not_called()
                finally:
                    setattr(target, attribute, previous)

    def test_employer_is_resolved_again_after_focus_delay(self):
        stale = Mock()
        self.dlg.child_window.side_effect = [
            SimpleNamespace(wrapper_object=lambda: stale),
            SimpleNamespace(wrapper_object=lambda: self.employer),
            SimpleNamespace(wrapper_object=lambda: self.claimant)]
        def delay(seconds):
            stale.iface_value.SetValue.assert_not_called()
            self.assertEqual(self.dlg.child_window.call_count, 1)
        self.runtime['time'].sleep.side_effect = delay
        self.assertEqual(self.run_step(missing=False)['status'], 'completed')
        self.runtime['focus_control'].assert_called_once_with(stale)
        self.employer.iface_value.SetValue.assert_called_once_with(self.fields['customer'])
        stale.iface_value.SetValue.assert_not_called()

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


class ClaimantResultTests(unittest.TestCase):
    """Execute the actual nested claimant decision without opening RRS."""

    @classmethod
    def setUpClass(cls):
        path = HERE.parent / 'Deploy-Ready' / 'legacy_steps.py'
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        builder = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                       and node.name == 'CreateSubjectLineBuilder')
        check = next(node for node in ast.walk(builder) if isinstance(node, ast.FunctionDef)
                     and node.name == 'CheckClaimantResult')
        factory = ast.parse(
            'def factory(ucc, allData, safe_click, notify, to_mmddyyyy, time):\n'
            '    pass\n').body[0]
        factory.body = [check] + ast.parse('return CheckClaimantResult').body
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[])),
                     str(path), 'exec'), namespace)
        cls.factory = staticmethod(namespace['factory'])

    def make_check(self, rows, *, fail_click=None):
        fields = dict(dob='01/02/1980', doi='03/04/2020', claimType='Workers Compensation')
        grid, ucc = Mock(), Mock()
        grid.iface_grid.CurrentRowCount = len(rows)
        controls = {key: Mock() for key in ('btnSelect', 'btnClose')}
        for index, row in enumerate(rows):
            controls[f'Select Row {index}'] = Mock()
            for column, value in row.items():
                control = Mock()
                control.iface_value.CurrentValue = value
                controls[f'{column} Row {index}, Not sorted.'] = control
        grid.child_window.side_effect = lambda *, title, **kwargs: SimpleNamespace(
            wrapper_object=lambda: controls[title])
        ucc.child_window.side_effect = lambda *, auto_id, **kwargs: (
            grid if auto_id == 'dgResults'
            else SimpleNamespace(wrapper_object=lambda: controls[auto_id]))
        clicks = []
        def click(control):
            clicks.append(control)
            if fail_click and control is controls[fail_click]:
                raise RuntimeError('Synthetic click failure')
        notify, normalize, clock = Mock(), Mock(side_effect=lambda value: value), Mock()
        run = self.factory(ucc, fields, click, notify, normalize, clock)
        return SimpleNamespace(run=run, controls=controls, clicks=clicks, grid=grid,
                               notify=notify, normalize=normalize, clock=clock)

    @staticmethod
    def matching_row(source='EDI'):
        return dict(Source=source, DOB='01/02/1980', DOI='03/04/2020',
                    LOI="Workers' Compensation")

    def test_single_result_selects_once_without_source_or_date_matching(self):
        for row in (
            dict(Source='MANUAL', DOB='12/31/1999', DOI='12/31/2025', LOI='Other'),
            dict(Source='EDI', DOB='', DOI='12/31/2025', LOI='Other'),
            self.matching_row(),
        ):
            with self.subTest(row=row):
                check = self.make_check([row])
                self.assertIs(check.run(), True)
                self.assertEqual(check.clicks, [check.controls['Select Row 0'],
                                               check.controls['btnSelect']])
                check.grid.child_window.assert_called_once_with(
                    title='Select Row 0', control_type='CheckBox')
                check.notify.assert_not_called()
                check.normalize.assert_not_called()

    def test_multiple_results_select_only_unique_matching_edi(self):
        check = self.make_check([self.matching_row('MANUAL'), self.matching_row(' edi ')])
        self.assertIs(check.run(), True)
        self.assertEqual(check.clicks, [check.controls['Select Row 1'],
                                       check.controls['btnSelect']])
        check.notify.assert_not_called()

    def test_multiple_edi_results_notify_without_selection(self):
        check = self.make_check([self.matching_row(), self.matching_row()])
        self.assertIsNone(check.run())
        self.assertEqual(check.clicks, [])
        check.notify.assert_called_once_with(
            'Notice', 'Multiple Results! Kindly select appropriate Claimant\n'
                      'Click Ok once Claim/Claimant is set')

    def test_multi_no_match_and_zero_rows_keep_existing_behavior(self):
        cases = [
            ([self.matching_row('MANUAL'), self.matching_row('OTHER')], False, True),
            ([], None, False),
        ]
        for key, value in (('DOB', '12/31/1999'), ('DOI', '12/31/2025'), ('LOI', 'Other')):
            row = dict(self.matching_row(), **{key: value})
            cases.append(([self.matching_row('MANUAL'), row], None, False))
        for rows, expected, closes in cases:
            with self.subTest(rows=rows):
                check = self.make_check(rows)
                self.assertIs(check.run(), expected)
                self.assertEqual(check.clicks, [check.controls['btnClose']] if closes else [])
                check.notify.assert_not_called()

    def test_single_result_click_failures_do_not_return_success(self):
        for target in ('Select Row 0', 'btnSelect'):
            with self.subTest(target=target):
                check = self.make_check([self.matching_row()], fail_click=target)
                with self.assertRaisesRegex(RuntimeError, 'Synthetic click failure'):
                    check.run()
                self.assertEqual(check.clicks, [check.controls['Select Row 0']] +
                                 ([check.controls['btnSelect']] if target == 'btnSelect' else []))
                check.clock.sleep.assert_not_called()


class ProviderNameSearchTests(unittest.TestCase):
    """Run actual nested search closures with synthetic UI controls."""

    @classmethod
    def setUpClass(cls):
        path = HERE.parent / 'Deploy-Ready' / 'legacy_steps.py'
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        builder = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                       and node.name == 'CreateSubjectLineBuilder')
        body = next(node.body for node in builder.body if isinstance(node, ast.Try))
        missing = next(node for node in body if isinstance(node, ast.If)
                       and isinstance(node.test, ast.Name) and node.test.id == 'missing')
        names = {'_get_edit', '_set_value', '_select_state', '_click_search',
                 '_wait_search_idle', '_results_count', '_fill_common_filters',
                 '_clear_all_inputs', '_search_with'}
        shared = [node for node in body if isinstance(node, ast.FunctionDef)
                  and node.name in {'_seed_provider_search_inputs', 'run_provider_search',
                                    'run_provider_search_part'}]
        call = next(i for i, node in enumerate(body) if isinstance(node, ast.Assign)
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == 'run_provider_search')
        add_if = body[call + 1]
        guarded_add = ast.If(test=add_if.test, body=add_if.body[:3], orelse=[])
        execute = ast.parse('def execute():\n    pass').body[0]
        execute.body = [body[call], guarded_add]
        cls.factories = {}
        for mode, helpers in (('main', body), ('part', missing.body)):
            factory = ast.parse(
                'def factory(allData, ups, safe_click, focus_control, time, match, snapshots):\n'
                '    _click_first_row_if_any = CheckPrvFromList = match\n'
                '    tbZipVal, cbStateVal, tbCityVal, tbPhoneVal, tbFacilityVal, tbFirstVal, tbLastVal = snapshots\n'
            ).body[0]
            factory.body += shared + [node for node in helpers
                                      if isinstance(node, ast.FunctionDef) and node.name in names]
            factory.body += [execute] + ast.parse(
                f'return run_provider_search{"_part" if mode == "part" else ""}, execute').body
            namespace = {'re': re}
            exec(compile(ast.fix_missing_locations(ast.Module(body=[factory], type_ignores=[])),
                         str(path), 'exec'), namespace)
            cls.factories[mode] = namespace['factory']

    def make_search(self, mode, *, doctor=False, prefilled=True, fault=None, results=(1,)):
        fields = dict(providerName='The Synthetic Clinic', providerFirst='',
                      providerLast='', providerPhone='5550100', providerCity='Synthetic City',
                      providerState='ZZ', providerZip='00000')
        if doctor:
            fields.update(providerFirst='Synthetic', providerLast='Doctor')
        values = dict(tbFacility='', tbFirst='', tbLast='',
                      tbPhone='5550999' if prefilled else '',
                      tbCity='Existing City' if prefilled else '',
                      tbZip='11111' if prefilled else '', cbState='XY' if prefilled else '')
        controls = {}
        for auto_id, value in values.items():
            control = Mock()
            control.iface_value.CurrentValue = value
            control.iface_value.SetValue.side_effect = (
                lambda text, ctrl=control: setattr(ctrl.iface_value, 'CurrentValue', text))
            controls[auto_id] = control
        if fault:
            auto_id, kind = fault
            control = controls[auto_id]
            if kind == 'write':
                control.iface_value.SetValue.side_effect = RuntimeError('Synthetic confidential detail')
                control.type_keys.side_effect = RuntimeError('Synthetic confidential detail')
            elif kind == 'mismatch':
                control.iface_value.SetValue.side_effect = lambda text: None
            elif kind == 'read':
                def fail_read(text):
                    type(control.iface_value).CurrentValue = PropertyMock(
                        side_effect=RuntimeError('Synthetic confidential detail'))
                control.iface_value.SetValue.side_effect = fail_read
        for auto_id in ('btnSearch', 'btnAddNew', 'lblStatus', 'dgResults'):
            controls[auto_id] = Mock()
        controls['lblStatus'].is_visible.return_value = False
        ups = Mock()
        ups.child_window.side_effect = lambda *, auto_id, **kwargs: SimpleNamespace(
            wrapper_object=lambda: controls[auto_id])
        searches = []
        clicks = []
        counts = iter(results)
        def click(control):
            clicks.append(control)
            if control is controls['btnSearch']:
                searches.append({key: controls[key].iface_value.CurrentValue for key in values})
                controls['dgResults'].iface_grid.CurrentRowCount = next(counts)
        match = Mock(return_value=True if mode == 'main' else
                     (True, 'Synthetic Result', 'Synthetic Address', '5550100'))
        snapshots = [values[key] for key in ('tbZip', 'cbState', 'tbCity', 'tbPhone',
                                            'tbFacility', 'tbFirst', 'tbLast')]
        clock = SimpleNamespace(sleep=Mock(), monotonic=lambda: 0)
        run, execute = self.factories[mode](fields, ups, click, Mock(), clock, match, snapshots)
        return SimpleNamespace(run=run, execute=execute, fields=fields, controls=controls,
                               searches=searches, clicks=clicks, match=match)

    def test_prefilled_location_seeds_facility_before_first_search_and_routes_matching(self):
        for mode, expected in (('main', 'Synthetic'), ('part', 'The Synthetic Clinic')):
            with self.subTest(mode=mode):
                ui = self.make_search(mode)
                result = ui.run()
                self.assertEqual(len(ui.searches), 1)
                self.assertEqual(ui.searches[0]['tbFacility'], expected)
                self.assertEqual(ui.searches[0]['tbCity'], 'Existing City')
                self.assertEqual(ui.searches[0]['tbZip'], '11111')
                self.assertEqual(ui.searches[0]['tbPhone'], '5550100')
                self.assertEqual(ui.searches[0]['cbState'], 'XY')
                self.assertEqual(ui.searches[0]['tbFirst'], '')
                self.assertEqual(ui.searches[0]['tbLast'], '')
                ui.match.assert_called_once_with('fac', 'The Synthetic Clinic', None, None)
                self.assertEqual(result, (1, True) if mode == 'main' else
                                 (1, 'Synthetic Result', 'Synthetic Address', '5550100'))

    def test_doctor_route_clears_stale_facility_and_preserves_names(self):
        for mode in ('main', 'part'):
            with self.subTest(mode=mode):
                ui = self.make_search(mode, doctor=True)
                ui.controls['tbFacility'].iface_value.CurrentValue = 'Stale Facility'
                ui.run()
                self.assertEqual(ui.searches[0]['tbFacility'], '')
                self.assertEqual(ui.searches[0]['tbFirst'], 'Synthetic')
                self.assertEqual(ui.searches[0]['tbLast'], 'Doctor')
                ui.match.assert_called_once_with('prof', None, 'Synthetic', 'Doctor')

    def test_facility_route_clears_conflicting_doctor_fields(self):
        for mode in ('main', 'part'):
            with self.subTest(mode=mode):
                ui = self.make_search(mode)
                ui.controls['tbFirst'].iface_value.CurrentValue = 'Stale'
                ui.controls['tbLast'].iface_value.CurrentValue = 'Doctor'
                ui.run()
                self.assertEqual(ui.searches[0]['tbFirst'], '')
                self.assertEqual(ui.searches[0]['tbLast'], '')

    def test_existing_keystroke_fallback_requires_successful_readback(self):
        for mode in ('main', 'part'):
            with self.subTest(mode=mode):
                ui = self.make_search(mode)
                control = ui.controls['tbFacility']
                control.iface_value.SetValue.side_effect = RuntimeError('Synthetic UIA failure')
                def type_value(text, **kwargs):
                    control.iface_value.CurrentValue = '' if text == '^a{BACKSPACE}' else text
                control.type_keys.side_effect = type_value
                ui.run()
                self.assertEqual(len(ui.searches), 1)
                self.assertEqual(ui.searches[0]['tbFacility'],
                                 'Synthetic' if mode == 'main' else 'The Synthetic Clinic')

    def test_later_searches_keep_legacy_facility_strategy_and_filter_stages(self):
        for mode, expected in (('main', 'Synthetic'), ('part', 'The Synthetic Clinic')):
            with self.subTest(mode=mode):
                ui = self.make_search(mode, results=(0, 0, 1))
                ui.match.return_value = False if mode == 'main' else (False, None, None, None)
                ui.run()
                self.assertEqual([item['tbFacility'] for item in ui.searches], [expected] * 3)
                self.assertEqual([item['tbCity'] for item in ui.searches],
                                 ['Existing City', '', 'Synthetic City'])
                self.assertEqual([item['tbZip'] for item in ui.searches], ['11111', '', '00000'])
                self.assertEqual([item['tbPhone'] for item in ui.searches], ['5550100'] * 3)

    def test_available_phone_replaces_blank_or_stale_input_before_search(self):
        for mode in ('main', 'part'):
            for prefilled in (True, False):
                for existing in ('', '5550999'):
                    with self.subTest(mode=mode, prefilled=prefilled, existing=existing):
                        ui = self.make_search(mode, prefilled=prefilled)
                        ui.fields['providerPhone'] = ' 202-555-0100 '
                        ui.controls['tbPhone'].iface_value.CurrentValue = existing
                        ui.run()
                        self.assertEqual(ui.searches[0]['tbPhone'], '202-555-0100')

    def test_missing_phone_preserves_initial_filter_and_later_clears_it(self):
        for mode in ('main', 'part'):
            for phone in ('', None, '   '):
                with self.subTest(mode=mode, phone=phone):
                    ui = self.make_search(mode, results=(0, 0, 1))
                    ui.fields['providerPhone'] = phone
                    ui.match.return_value = False if mode == 'main' else (False, None, None, None)
                    ui.run()
                    self.assertEqual([item['tbPhone'] for item in ui.searches],
                                     ['5550999', '', ''])

    def test_phone_write_and_readback_failures_stop_search_and_add(self):
        for mode in ('main', 'part'):
            for prefilled in (True, False):
                for kind in ('write', 'mismatch', 'read'):
                    with self.subTest(mode=mode, prefilled=prefilled, fault=kind):
                        ui = self.make_search(mode, prefilled=prefilled, fault=('tbPhone', kind))
                        with self.assertRaisesRegex(
                                RuntimeError, r'^tbPhone provider input (write|verification) failed$'):
                            (ui.execute if mode == 'main' else ui.run)()
                        self.assertEqual(ui.searches, [])
                        self.assertNotIn(ui.controls['btnAddNew'], ui.clicks)
                        ui.match.assert_not_called()

    def test_phone_failure_after_initial_search_blocks_later_search_and_add(self):
        for mode in ('main', 'part'):
            for kind in ('write', 'mismatch', 'read'):
                with self.subTest(mode=mode, fault=kind):
                    ui = self.make_search(mode)
                    control = ui.controls['tbPhone']
                    def reject_match(*args):
                        if kind == 'write':
                            control.iface_value.SetValue.side_effect = RuntimeError(
                                'Synthetic confidential detail')
                            control.type_keys.side_effect = RuntimeError('Synthetic confidential detail')
                        elif kind == 'mismatch':
                            control.iface_value.CurrentValue = '5550999'
                            control.iface_value.SetValue.side_effect = lambda text: None
                        else:
                            type(control.iface_value).CurrentValue = PropertyMock(
                                side_effect=RuntimeError('Synthetic confidential detail'))
                        return False if mode == 'main' else (False, None, None, None)
                    ui.match.side_effect = reject_match
                    with self.assertRaisesRegex(
                            RuntimeError, r'^tbPhone provider input (write|verification) failed$'):
                        (ui.execute if mode == 'main' else ui.run)()
                    self.assertEqual(len(ui.searches), 1)
                    self.assertEqual(ui.searches[0]['tbPhone'], '5550100')
                    self.assertNotIn(ui.controls['btnAddNew'], ui.clicks)
                    ui.match.assert_called_once()

    def test_name_write_readback_and_conflicting_clear_failures_stop_search_and_add(self):
        for mode in ('main', 'part'):
            for prefilled in (True, False):
                for doctor, auto_id, kind in (
                    (False, 'tbFacility', 'write'), (False, 'tbFacility', 'mismatch'),
                    (False, 'tbFacility', 'read'), (False, 'tbFirst', 'write'),
                    (False, 'tbLast', 'mismatch'), (True, 'tbFacility', 'mismatch'),
                    (True, 'tbFirst', 'write'), (True, 'tbLast', 'mismatch'),
                ):
                    with self.subTest(mode=mode, prefilled=prefilled, doctor=doctor,
                                      control=auto_id, fault=kind):
                        ui = self.make_search(mode, doctor=doctor, prefilled=prefilled,
                                              fault=(auto_id, kind))
                        if doctor and auto_id == 'tbFacility':
                            ui.controls[auto_id].iface_value.CurrentValue = 'Stale Facility'
                        if not doctor and auto_id == 'tbLast':
                            ui.controls[auto_id].iface_value.CurrentValue = 'Stale Doctor'
                        with self.assertRaisesRegex(RuntimeError,
                                                    rf'^{auto_id} provider input (write|verification) failed$'):
                            (ui.execute if mode == 'main' else ui.run)()
                        self.assertEqual(ui.searches, [])
                        self.assertNotIn(ui.controls['btnAddNew'], ui.clicks)
                        ui.match.assert_not_called()

    def test_missing_identity_fails_without_broad_search_or_add(self):
        for mode in ('main', 'part'):
            for prefilled in (True, False):
                with self.subTest(mode=mode, prefilled=prefilled):
                    ui = self.make_search(mode, prefilled=prefilled)
                    ui.fields['providerName'] = ''
                    with self.assertRaisesRegex(RuntimeError, 'require provider identity'):
                        (ui.execute if mode == 'main' else ui.run)()
                    self.assertEqual(ui.searches, [])
                    self.assertNotIn(ui.controls['btnAddNew'], ui.clicks)


class LegacyInjuryDropdownTests(unittest.TestCase):
    """Execute only the actual injury block through the rebinding controller."""

    @classmethod
    def setUpClass(cls):
        path = HERE.parent / 'Deploy-Ready' / 'legacy_steps.py'
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        statements = next(node.body for node in ast.walk(tree)
                          if isinstance(node, ast.Try) and any(
                              isinstance(item, ast.ImportFrom)
                              and item.module == 'AI.injury_classification'
                              for item in node.body))
        start = next(i for i, node in enumerate(statements)
                     if isinstance(node, ast.ImportFrom)
                     and node.module == 'AI.injury_classification')
        end = next(i for i in range(start, len(statements))
                   if isinstance(statements[i], ast.Assign) and any(
                       isinstance(target, ast.Name) and target.id == 'cbClaimType'
                       for target in statements[i].targets))
        function = ast.parse('def injury_step(app=None):\n    pass\n').body[0]
        function.body = (ast.parse('global botStop, data').body + statements[start:end]
                         + ast.parse('data = {"boundary_reached": True}\nbotStop = False').body)
        namespace = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                     str(path), 'exec'), namespace)
        cls.step = staticmethod(namespace['injury_step'])

    @staticmethod
    def combo(current='', options=(), *, selection_pattern=False, fault=None):
        class NoPatternInterfaceError(Exception):
            pass

        class Combo:
            def __init__(self):
                self.current, self.writes, self.enumerations = current, [], 0
            def selected_text(self):
                if not selection_pattern:
                    raise NoPatternInterfaceError()
                return self.current
            @property
            def iface_value(self):
                if fault == 'initial_read' or (fault == 'readback' and self.writes):
                    raise NoPatternInterfaceError()
                return SimpleNamespace(CurrentValue=self.current, SetValue=self.set_value)
            def children(self, **_): return []
            def select(self, value):
                if not selection_pattern:
                    raise NoPatternInterfaceError()
                self.set_value(value)
            def set_value(self, value):
                self.writes.append(value)
                if fault == 'write':
                    raise RuntimeError('Synthetic selection failure')
                if fault != 'mismatch':
                    self.current = value
            def expand(self):
                self.enumerations += 1
                if fault == 'enumeration':
                    raise NoPatternInterfaceError()
            def collapse(self): pass
            def descendants(self, **_):
                return [SimpleNamespace(window_text=lambda option=option: option) for option in options]
        return Combo()

    def run_block(self, combos, fields=None):
        # The real path loader/imports and adapter run; only desktop/time are synthetic.
        with patch.object(sys, 'path', [str(runner.ROOT / 'src'), *sys.path]):
            from fcm_intake.legacy_loader import load_module_from_path
            def load_ui(name, path):
                ui = load_module_from_path(name, path)
                ticks = iter(range(1000))
                ui.time = SimpleNamespace(sleep=lambda *_: None, monotonic=lambda: next(ticks) / 10)
                return ui
            notices, looked_up = [], []
            def child_window(auto_id, control_type):
                self.assertEqual(control_type, 'ComboBox')
                looked_up.append(auto_id)
                return SimpleNamespace(wait=lambda *_, **kw: None,
                                       wrapper_object=lambda: combos[auto_id])
            runtime = {'dlg': SimpleNamespace(child_window=child_window),
                       'allData': fields if fields is not None else {
                           'injuryType': 'lower back strain', 'injuryCause': 'lifted a heavy box'},
                       'notify': lambda *args: notices.append(args)}
            with patch.dict(sys.modules, {'pywinauto': SimpleNamespace(Desktop=Mock())}), patch(
                    'fcm_intake.legacy_loader.load_module_from_path', side_effect=load_ui) as loader:
                result = runner.load_core().run_flow(runtime, steps=self.step)
            loader.assert_called_once_with(
                'subject_line_injury_ui', HERE.parent / 'Deploy-Ready' / 'rrs_ui.py')
        return SimpleNamespace(result=result, notices=notices, controls=looked_up)

    def test_matches_actual_options_and_verifies_without_selection_pattern(self):
        for selection_pattern in (False, True):
            with self.subTest(selection_pattern=selection_pattern):
                combos = {
                    'cbInjuryType': self.combo(options=['Sprain or Tear', 'Strain'],
                                              selection_pattern=selection_pattern),
                    'cbInjuryCause': self.combo(options=['Lifting', 'Holding or Carrying'],
                                               selection_pattern=selection_pattern)}
                outcome = self.run_block(combos)
                self.assertEqual(outcome.result['status'], 'completed')
                self.assertEqual(outcome.controls, ['cbInjuryType', 'cbInjuryCause'])
                self.assertEqual(combos['cbInjuryType'].writes, ['Strain'])
                self.assertEqual(combos['cbInjuryCause'].writes, ['Lifting'])
                self.assertEqual(outcome.notices, [])

    def test_prefilled_values_are_kept_and_none_placeholder_is_fillable(self):
        for current in ('Sprain or Tear', '  Sprain or Tear  ', 'None'):
            with self.subTest(current=current):
                combos = {'cbInjuryType': self.combo(current, ['Strain']),
                          'cbInjuryCause': self.combo('Holding or Carrying', ['Lifting'])}
                outcome = self.run_block(combos)
                self.assertEqual(outcome.result['status'], 'completed')
                self.assertEqual(combos['cbInjuryType'].writes, ['Strain'] if current == 'None' else [])
                self.assertEqual(combos['cbInjuryType'].enumerations, 1 if current == 'None' else 0)
                self.assertEqual(combos['cbInjuryCause'].writes, [])
                self.assertEqual(combos['cbInjuryCause'].enumerations, 0)
                self.assertEqual(outcome.notices, [])

    def test_unmatched_or_missing_inputs_notify_manual_without_free_text_write(self):
        for fields in ({}, {'injuryType': '', 'injuryCause': 'None'},
                       {'injuryType': None, 'injuryCause': '   '},
                       {'injuryType': 'strain', 'injuryCause': 'lifting'}):
            with self.subTest(fields=fields):
                combos = {'cbInjuryType': self.combo(options=['Laceration']),
                          'cbInjuryCause': self.combo('None', ['Holding or Carrying'])}
                outcome = self.run_block(combos, fields)
                self.assertEqual(outcome.result['status'], 'completed')
                self.assertEqual([c.writes for c in combos.values()], [[], []])
                self.assertEqual(len(outcome.notices), 2)
                for label, notice in zip(('Injury Type', 'Injury Cause'), outcome.notices):
                    self.assertEqual(notice[0], 'Notice')
                    self.assertIn(f'{label} requires manual selection', notice[1])

    def test_option_selection_and_readback_failures_stop_controller(self):
        for ident in ('cbInjuryType', 'cbInjuryCause'):
            for fault in ('initial_read', 'enumeration', 'empty_options', 'write', 'mismatch', 'readback'):
                with self.subTest(ident=ident, fault=fault):
                    combos = {'cbInjuryType': self.combo(options=['Strain']),
                              'cbInjuryCause': self.combo(options=['Lifting'])}
                    combos[ident] = self.combo(
                        options=[] if fault == 'empty_options' else ['Strain', 'Lifting'],
                        fault=fault)
                    outcome = self.run_block(combos)
                    self.assertEqual(outcome.result['status'], 'failed')
                    self.assertEqual(outcome.result['type'], 'RuntimeError')
                    detail = {
                        'initial_read': 'Dropdown value could not be read',
                        'enumeration': f'{ident} dropdown options could not be read',
                        'empty_options': f'{ident} dropdown options could not be read',
                        'write': 'Synthetic selection failure',
                        'mismatch': f'{ident} dropdown selection could not be verified',
                        'readback': 'Dropdown value could not be read',
                    }[fault]
                    self.assertIn(detail, outcome.result['error'])
                    self.assertNotIn('data', outcome.result)
                    self.assertEqual(outcome.notices, [])
                    self.assertEqual(combos[ident].writes,
                                     [('Strain' if ident == 'cbInjuryType' else 'Lifting')]
                                     if fault in ('write', 'mismatch', 'readback') else [])
                    if ident == 'cbInjuryType':
                        self.assertEqual(combos['cbInjuryCause'].writes, [])


if __name__ == '__main__':
    unittest.main()
