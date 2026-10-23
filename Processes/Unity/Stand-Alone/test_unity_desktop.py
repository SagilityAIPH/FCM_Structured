"""Synthetic desktop regression tests; unique imports coexist with sibling apps."""
import ast
import importlib.util
import json
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from openpyxl import load_workbook
from AI.unity_errors import UnityFlagError

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import unity_model as model
import unity_excel as excel
spec = importlib.util.spec_from_file_location('unity_desktop_backend_tests', HERE / 'backend.py')
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


def synthetic():
    return model.defaults() | {'claimNumber': 'SYNTHETIC-001', 'customer': 'Invented Widgets',
                              'claimantFirst': 'Synthetic', 'claimantLast': 'Person'}


def synthetic_instructions(length):
    prefix, suffix = ' \n\tSynthetic instructions\n', '\nEND-SYNTHETIC \t\n'
    return prefix + 'x' * (length - len(prefix) - len(suffix)) + suffix


def legacy_function(name):
    """Read one function, stopping before the next definition or sample records."""
    path = model.ROOT / 'src' / 'fcm_intake' / 'legacy' / 'legacy_unity.py'
    lines = []
    with path.open(encoding='utf-8-sig') as source:
        for line in source:
            if not lines:
                if line.startswith(f'def {name}('):
                    lines.append(line)
            elif line.startswith(('def ', 'class ', 'if __name__')):
                break
            else:
                lines.append(line)
    return ast.parse(''.join(lines)).body[0]


class StartupTests(unittest.TestCase):
    def test_direct_entrypoints_self_test_without_pythonpath(self):
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            env.update(TEMP=directory, TMP=directory, TMPDIR=directory)
            for entrypoint in ('run.py', 'launcher.py'):
                with self.subTest(entrypoint=entrypoint):
                    report = Path(directory) / f'{entrypoint}-report.json'
                    completed = subprocess.run(
                        [sys.executable, str(HERE / entrypoint), '--self-test', '--report', str(report)],
                        cwd=model.ROOT, env=env, capture_output=True, text=True, timeout=30)
                    self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                    result = json.loads(report.read_text(encoding='utf-8'))
                    self.assertEqual(result['mode'], 'synthetic workbook roundtrip + bridge')
                    self.assertEqual(result['result']['status'], 'completed')
                    self.assertEqual(result['rows'], 1)
                    self.assertEqual(result['instruction_length'], 32767)
                    self.assertIs(result['oversized_rejected'], True)
                    for extension in ('pdf', 'msg', 'eml'):
                        local = result[f'local_{extension}_result']
                        self.assertEqual(local['status'], 'completed')
                        self.assertEqual(Path(local['attachment']).suffix.lower(), '.' + extension)

    def test_model_and_backend_import_without_repository_on_path(self):
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        for module in ('unity_model', 'backend'):
            with self.subTest(module=module):
                completed = subprocess.run(
                    [sys.executable, '-c', f'import {module}'],
                    cwd=HERE, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_spec_covers_raw_loader_shared_ai_imports(self):
        adapter_tree = ast.parse((model.ROOT / 'Final Code' / 'finalcode' / 'field_adapter.py')
                                 .read_text(encoding='utf-8-sig'))
        required = {node.module for node in ast.walk(adapter_tree)
                    if isinstance(node, ast.ImportFrom) and node.module
                    and node.module.startswith('AI.')}
        required.add('AI.referral_attachments')
        required.add('AI.unity_errors')
        spec_tree = ast.parse((HERE / 'unity_assignment.spec').read_text(encoding='utf-8'))
        hiddenimports = next(ast.literal_eval(node.value) for node in spec_tree.body
                             if isinstance(node, ast.Assign)
                             and any(isinstance(target, ast.Name) and target.id == 'hiddenimports'
                                     for target in node.targets))
        self.assertFalse(required - set(hiddenimports),
                         f'Raw field adapter imports missing from hiddenimports: {required - set(hiddenimports)}')

    def test_actual_edge_driver_detach_is_opt_in(self):
        from selenium.webdriver.edge.options import Options

        factory = legacy_function('create_driver')
        for keywords, detached in (({}, False), ({'detach': True}, True), ({'detach': False}, False)):
            with self.subTest(keywords=keywords):
                webdriver = Mock()
                service = Mock()
                env = {'EdgeOptions': Options, 'webdriver': webdriver,
                       'find_msedge_path': lambda: 'synthetic-edge.exe',
                       'build_edge_service': Mock(return_value=service),
                       'EDGE_DRIVER_PATH': 'synthetic-driver.exe'}
                exec(compile(ast.Module(body=[factory], type_ignores=[]), '<actual driver>', 'exec'), env)
                driver = env['create_driver'](**keywords)
                options = webdriver.Edge.call_args.kwargs['options']
                self.assertIs(options.experimental_options['detach'], detached)
                self.assertEqual(options.experimental_options['excludeSwitches'], ['enable-logging'])
                webdriver.Edge.assert_called_once_with(service=service, options=options)
                driver.set_page_load_timeout.assert_called_once_with(60)
                driver.set_script_timeout.assert_called_once_with(60)


class ModelTests(unittest.TestCase):
    def test_contract_and_ast(self):
        audit = model.verify_legacy_keys()
        self.assertEqual(audit['count'], 39)
        self.assertEqual(audit['context_only'], [])
        self.assertEqual(audit['unexpected'], [])
        self.assertEqual(len(model.CONTEXT_KEYS), 39)
        self.assertEqual(len(model.defaults()), 35)
        consumed_derived = set(model.DERIVED_KEYS) & set(model.CONTEXT_KEYS)
        self.assertEqual(len(consumed_derived), 5)
        self.assertEqual(set(model.defaults()), set(model.CONTEXT_KEYS) - consumed_derived | {'claimNumber'})
        self.assertEqual([g['title'] for g in model.schema()], ['Claim', 'Claimant', 'Provider', 'Adjuster', 'Attorney'])

    def test_defaults_and_requirements_by_stage(self):
        self.assertFalse(any(model.defaults().values()))
        self.assertEqual(model.validate({'claimNumber': ' X '}, 'assign')['claimNumber'], 'X')
        for stage in ('all', 'unity'):
            with self.subTest(stage=stage), self.assertRaisesRegex(ValueError, 'customer, claimantFirst, claimantLast'):
                model.validate({'claimNumber': 'X'}, stage)
        for stage in ('all', 'unity', 'assign'):
            with self.subTest(stage=stage), self.assertRaisesRegex(ValueError, 'claimNumber'):
                model.validate({}, stage)
        self.assertTrue(model.warnings(model.validate(synthetic())))

    def test_invalid_supplied_values_even_on_assign(self):
        for key, value in [('dob', '02/30/2000'), ('nextApptDate', 'tomorrow'), ('nextApptTime', '25:90'),
                           ('state', 'ZZ'), ('providerState', 'California'), ('claimantAttyState', 'zz'),
                           ('zip', '123'), ('providerZip', '123456'), ('claimantAttyZip', 'oops'),
                           ('phoneNumber', '123'), ('claimantAttyPhone', 'invalid'), ('gender', 'unsupported'),
                           ('serviceType', 'Unsupported'), ('claimID', 5), ('claimID', 'x' * 1001)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                model.validate(synthetic() | {key: value}, 'assign')
        for payload, stage in [([], 'all'), ({'unknown': 'x'}, 'assign'), ({}, 'wrong')]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                model.validate(payload, stage)

    def test_date_time_zip_phone_normalization(self):
        result = model.validate(synthetic() | {'dob': '2000-01-02', 'nextApptTime': '14:30',
                        'zip': '00123', 'providerZip': '00123-4567', 'phoneNumber': '(555) 010-2345'})
        self.assertEqual(result['dob'], '01/02/2000')
        self.assertEqual(result['nextApptTime'], '02:30 PM')
        self.assertEqual(result['zip'], '00123')
        self.assertIn('no date', model.warnings(result)[1])

    def test_instruction_limits_and_exact_controller_preservation(self):
        for length in (1001, 32767):
            instructions = synthetic_instructions(length)
            for stage in ('all', 'unity', 'assign'):
                with self.subTest(length=length, stage=stage):
                    checked = model.validate(synthetic() | {'specialInstructions': instructions}, stage)
                    self.assertEqual(checked['specialInstructions'], instructions)
                    self.assertEqual(model.to_controller(checked)['specialInstructions'], instructions)
        for value in (synthetic_instructions(32768), 123, None):
            with self.subTest(value_type=type(value)), self.assertRaisesRegex(
                    ValueError, 'specialInstructions.*32,767 characters'):
                model.validate(synthetic() | {'specialInstructions': value})
        self.assertEqual(model.validate(synthetic() | {'specialInstructions': ' \n\t '})
                         ['specialInstructions'], ' \n\t ')
        self.assertEqual(model.validate(synthetic() | {'claimID': 'x' * 1000})['claimID'], 'x' * 1000)
        self.assertEqual(model.validate(synthetic() | {'claimID': ' X '})['claimID'], 'X')
        for key in model.defaults().keys() - {'specialInstructions'}:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, f'{key}.*1,000 characters'):
                model.validate(synthetic() | {key: 'x' * 1001})

    def test_frontend_fixture_matches_shared_length_schema(self):
        fixture = json.loads((HERE / 'frontend' / 'src' / 'schema.json').read_text(encoding='utf-8'))
        self.assertEqual(fixture['schema'], model.schema())
        fields = {field['key']: field for group in model.schema() for field in group['fields']}
        self.assertEqual(fields['specialInstructions']['maxLength'], 32767)
        self.assertTrue(all(field['maxLength'] == 1000 for key, field in fields.items()
                            if key != 'specialInstructions'))

    def test_derivation_defaults_and_state_is_not_jurisdiction(self):
        data = synthetic() | {'state': 'MI', 'providerZip': '00123'}
        before = data.copy()
        result = model.to_controller(data)
        self.assertEqual(data, before)
        self.assertEqual(result['claimStateAbbr'], '')
        self.assertEqual(result['correctZipCode'], '00123')
        self.assertEqual(result['refSource'], '')
        self.assertEqual(result['serviceType'], 'Medical Full')
        self.assertEqual(result['CaseObj'], 'Coordination of Care/Services')

    def test_continental_branch_and_explicit_semantics(self):
        data = synthetic() | {'customer': 'Synthetic Continental Tire division', 'claimType': 'Auto'}
        result = model.to_controller(data, claim_jurisdiction='MI')
        self.assertEqual((result['claimStateAbbr'], result['claimStateFull']), ('MI', 'Michigan'))
        self.assertEqual((result['ServiceType'], result['serviceType'], result['refType'], result['CaseObj']),
                         ('Medical Task', 'Medical Task', 'Task', 'MI MCCA Attendant Care'))
        explicit = model.to_controller(data | {'serviceType': 'Vocational Full'}, claim_jurisdiction='MI')
        self.assertEqual(explicit['serviceType'], 'Vocational Full')
        self.assertEqual(explicit['ServiceType'], 'Medical Task')
        self.assertEqual(model.to_controller(data, claim_jurisdiction='CA')['serviceType'], 'Medical Full')


class LegacyFlagTests(unittest.TestCase):
    def setUp(self):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.remote.webelement import WebElement
        from selenium.webdriver.support import expected_conditions as EC

        self.events = []
        self.failure = None
        self.original_error = None
        self.open = False
        self.old_note_locator = (
            By.XPATH,
            './modal-template/div/div/div/div[3]/div/form/div/div[3]/text-area/form-control/div/textarea')
        self.stable_note_locator = (By.ID, 'intake-flag-for-intervention-description-text-area')
        owner = self

        class Element(WebElement):
            def __init__(self, name):
                self.name = name
                self.value = 'stale note'
                self.children = {}

            def find_element(self, by, selector):
                owner.events.append(('find', self.name, by, selector))
                child = self.children[(by, selector)]
                if owner.failure == child.name + '-locate':
                    owner.fail()
                return child

            def is_displayed(self):
                if self.name == 'modal':
                    owner.events.append(('modal-visible', owner.open))
                    return owner.open and owner.failure != 'modal-timeout'
                return True

            def is_enabled(self):
                return True

            def click(self):
                owner.events.append(('click', self.name))
                if owner.failure == self.name:
                    owner.fail()
                if self.name == 'flag':
                    owner.open = True
                elif self.name == 'reason':
                    owner.modal.children.pop(owner.old_note_locator, None)
                elif self.name == 'submit' and owner.failure != 'still-open':
                    owner.open = False

            def clear(self):
                owner.events.append(('clear', self.name))
                if owner.failure == 'note-clear':
                    owner.fail()
                self.value = ''

            def send_keys(self, value):
                owner.events.append(('type', self.name, value))
                if owner.failure == 'note-type':
                    owner.fail()
                self.value += value

            def get_attribute(self, name):
                owner.events.append(('read', self.name, name))
                if owner.failure == 'note-read':
                    owner.fail()
                return 'mismatched' if owner.failure == 'note' else self.value

        class Wait:
            def __init__(self, target, timeout):
                self.target = target

            def until(self, condition):
                for _ in range(3):
                    value = condition(self.target)
                    if value:
                        return value
                owner.fail(TimeoutError)

        self.driver, self.modal = Element('driver'), Element('modal')
        self.driver.children = {
            (By.XPATH, '/html/body/my-app/div/div/div/ng-component/div[1]/div/div[1]/span'): Element('flag'),
            (By.TAG_NAME, 'flag-for-intervention-modal'): self.modal,
        }
        note = Element('note')
        self.modal.children = {
            (By.XPATH, './modal-template/div/div/div/div[3]/div/form/div/div[1]/radio-group-input/form-control/div/label/div[1]/div/i[1]'): Element('reason'),
            self.old_note_locator: note,
            self.stable_note_locator: note,
            (By.XPATH, './modal-template/div/div/div/div[4]/div/div/div/button'): Element('submit'),
        }
        self.env = {'WebDriverWait': Wait, 'By': By, 'EC': EC, 'sys': sys,
                    'UnityFlagError': UnityFlagError}
        helper = legacy_function('flag_missing_appointment_time')
        exec(compile(ast.Module(body=[helper], type_ignores=[]), '<actual flag helper>', 'exec'), self.env)
        validation = legacy_function('validate_and_complete_task')
        branch, = [node for node in validation.body[0].body if isinstance(node, ast.If)
                   and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                           and child.func.id == 'flag_missing_appointment_time'
                           for child in ast.walk(node))]
        flag, = [node for node in branch.body if isinstance(node, ast.If)
                 and any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
                         and child.func.id == 'flag_missing_appointment_time'
                         for child in ast.walk(node))]
        # Keep the actual enclosing guard, flag statement and outer handler.
        # Replace unrelated portal work with sentinels at the following boundaries.
        self.assertEqual(branch.body[branch.body.index(flag) + 1].name, 'ValidateAddrPrv')
        branch = deepcopy(branch)
        branch.body = [deepcopy(flag), ast.parse('following_provider_work()').body[0]]
        branch.orelse = []
        validation.body[0].body = [branch, ast.parse('later_completion()').body[0]]
        self.env.update(following_provider_work=Mock(), later_completion=Mock())
        self.guard_code = compile(ast.fix_missing_locations(ast.Module(
            body=[branch], type_ignores=[])), '<actual flag guard>', 'exec')
        exec(compile(ast.fix_missing_locations(ast.Module(body=[validation], type_ignores=[])),
                     '<actual flag error boundary>', 'exec'), self.env)

    def fail(self, error_type=RuntimeError):
        self.original_error = error_type('SYNTHETIC-PRIVATE page content and Selenium message')
        raise self.original_error

    def prepare(self, **fields):
        data = model.to_controller(synthetic() | fields)
        self.env.update(driver=self.driver, dataRef=data,
                        providerName=data['providerName'], providerFirst=data['providerFirst'],
                        providerLast=data['providerLast'])
        return data

    def test_reason_layout_change_keeps_note_lookup_scoped_to_stable_id(self):
        self.prepare(providerName='Synthetic Facility')
        self.assertIs(self.modal.children[self.old_note_locator],
                      self.modal.children[self.stable_note_locator])
        exec(self.guard_code, self.env)
        self.assertNotIn(self.old_note_locator, self.modal.children)
        note_lookup = ('find', 'modal', *self.stable_note_locator)
        self.assertIn(note_lookup, self.events)
        self.assertLess(self.events.index(('click', 'reason')), self.events.index(note_lookup))
        self.assertNotIn(('find', 'modal', *self.old_note_locator), self.events)
        self.assertNotIn(('find', 'driver', *self.stable_note_locator), self.events)
        self.assertEqual(self.modal.children[self.stable_note_locator].value,
                         'Missing Provider Appointment Time')
        self.assertEqual(self.events.count(('click', 'submit')), 1)
        self.assertEqual(self.events[-1], ('modal-visible', False))
        self.env['following_provider_work'].assert_called_once()

    def test_actual_guard_and_successful_flag_continue(self):
        cases = [({}, False), ({'providerName': 'Synthetic Facility'}, True),
                 ({'providerFirst': 'Invented'}, True), ({'providerLast': 'Example'}, True),
                 ({'nextApptDate': '10/23/2026'}, True),
                 ({'providerName': 'Synthetic Facility', 'nextApptTime': '09:00 AM'}, False),
                 ({'nextApptDate': '10/23/2026', 'nextApptTime': '09:00 AM'}, False)]
        for fields, should_flag in cases:
            with self.subTest(fields=fields):
                self.setUp()
                self.prepare(**fields)
                exec(self.guard_code, self.env)
                clicks = [event for event in self.events if event[0] == 'click']
                self.assertEqual(clicks, [('click', name) for name in
                                         ('flag', 'reason', 'submit')] if should_flag else [])
                if should_flag:
                    self.assertEqual([event for event in self.events
                                      if event[0] in ('clear', 'type', 'read')],
                                     [('clear', 'note'), ('type', 'note', 'Missing Provider Appointment Time'),
                                      ('read', 'note', 'value')])
                    self.assertEqual(self.events[-1], ('modal-visible', False))
                    self.env['following_provider_work'].assert_called_once()
                elif fields:
                    self.env['following_provider_work'].assert_called_once()
                else:
                    self.env['following_provider_work'].assert_not_called()

    def test_flag_failures_stop_following_work_and_fail_checked_controller(self):
        stages = {
            'flag-locate': 'opening the flag dialog', 'flag': 'opening the flag dialog',
            'modal-timeout': 'waiting for the visible flag dialog',
            'reason-locate': 'selecting the missing-information reason',
            'reason': 'selecting the missing-information reason',
            'note-locate': 'locating the flag note', 'note-clear': 'clearing the flag note',
            'note-type': 'entering the flag note', 'note-read': 'verifying the flag note',
            'note': 'verifying the flag note', 'submit-locate': 'submitting the flag',
            'submit': 'submitting the flag', 'still-open': 'waiting for the flag dialog to close',
        }
        for failure, stage in stages.items():
            with self.subTest(failure=failure):
                self.setUp()
                data = self.prepare(providerName='Synthetic Facility')
                self.failure = failure
                with self.assertRaises(UnityFlagError) as caught:
                    exec(self.guard_code, self.env)
                self.assertEqual(caught.exception.stage, stage)
                self.assertIn(stage, str(caught.exception))
                self.assertNotIn('SYNTHETIC-PRIVATE', str(caught.exception))
                if failure == 'note':
                    self.assertIsInstance(caught.exception.__cause__, RuntimeError)
                else:
                    self.assertIs(caught.exception.__cause__, self.original_error)
                self.env['following_provider_work'].assert_not_called()
                clicks = self.events.count(('click', 'submit'))
                self.assertEqual(clicks, int(failure in ('submit', 'still-open')))
                if failure not in ('flag', 'flag-locate'):
                    self.assertTrue(self.open)
                unity = SimpleNamespace(validate_and_complete_task=self.env['validate_and_complete_task'])
                complete, confirm, record = Mock(), Mock(return_value=True), Mock()
                self.events.clear()
                result = backend._runner().load_core().run_flow(
                    data, list_attachments=lambda: [Path('synthetic.pdf')],
                    run_unity=lambda customer, claimant, payload:
                        backend.checked_validate(unity, self.driver, customer, claimant, payload),
                    record_assignment=record, complete_assignment=complete, confirm=confirm, notify=Mock())
                self.assertEqual((result['status'], result['reason']), ('failed', 'run_unity_failed'))
                self.assertEqual(result['error']['type'], 'UnityFlagError')
                self.assertIn(stage, result['error']['message'])
                self.assertNotIn('SYNTHETIC-PRIVATE', result['error']['message'])
                record.assert_called_once()
                confirm.assert_not_called()
                complete.assert_not_called()
                self.env['later_completion'].assert_not_called()
                self.env['following_provider_work'].assert_not_called()
                self.assertEqual(self.events.count(('click', 'submit')), clicks)

    def test_actual_outer_boundary_still_marks_unrelated_errors(self):
        self.prepare(providerName='Synthetic Facility')
        self.env['flag_missing_appointment_time'] = Mock(side_effect=ValueError('synthetic unrelated'))
        unity = SimpleNamespace(validate_and_complete_task=self.env['validate_and_complete_task'])
        with self.assertRaisesRegex(RuntimeError, 'Legacy Unity reported failure:.*synthetic unrelated'):
            backend.checked_validate(unity, self.driver, 'Synthetic', 'Example', self.env['dataRef'])
        self.env['following_provider_work'].assert_not_called()
        self.env['later_completion'].assert_not_called()

    def test_actual_flag_failure_through_desktop_preserves_browser_and_stops_flow(self):
        data = self.prepare(providerName='Synthetic Facility')
        self.failure = 'still-open'
        self.driver.service = Mock()
        self.driver.command_executor = Mock()
        self.driver.quit = Mock()
        unity = SimpleNamespace(create_driver=Mock(return_value=self.driver), login=Mock(),
                                validate_and_complete_task=self.env['validate_and_complete_task'])
        config = SimpleNamespace(ATTACHMENT_FOLDER='synthetic', UNITY_SCRIPT='synthetic.py')
        with patch.dict(sys.modules, {
                'fcm_intake.config': config,
                'fcm_intake.legacy_loader': SimpleNamespace(load_module_from_path=lambda *args: unity)}):
            calls = backend.live_callbacks()
        record, confirm, complete = Mock(), Mock(return_value=True), Mock()
        result = backend._runner().load_core().run_flow(
            data, list_attachments=lambda: [Path('synthetic.pdf')], run_unity=calls['run_unity'],
            record_assignment=record, confirm=confirm, complete_assignment=complete, notify=Mock())
        self.assertEqual((result['status'], result['reason']), ('failed', 'run_unity_failed'))
        self.assertEqual(result['error']['type'], 'UnityFlagError')
        self.assertIn('waiting for the flag dialog to close', result['error']['message'])
        self.assertIn('Browser left open for manual recovery', result['error']['message'])
        self.assertNotIn('SYNTHETIC-PRIVATE', result['error']['message'])
        self.assertEqual(self.events.count(('click', 'submit')), 1)
        self.driver.service.stop.assert_called_once()
        self.driver.command_executor.close.assert_called_once()
        self.driver.quit.assert_not_called()
        self.env['following_provider_work'].assert_not_called()
        self.env['later_completion'].assert_not_called()
        record.assert_called_once()
        confirm.assert_not_called()
        complete.assert_not_called()


class LegacyProviderAddressTests(unittest.TestCase):
    def setUp(self):
        from selenium.webdriver.common.by import By
        from selenium.webdriver.remote.webelement import WebElement
        from selenium.webdriver.support import expected_conditions as EC

        self.events = []
        self.failure = None
        self.open = False
        self.closing = False
        self.closure_polls = 0
        owner = self

        class Element(WebElement):
            def __init__(self, name, classes='', visible=True, enabled=True):
                self.name = name
                self.classes = classes
                self.visible = visible
                self.enabled = enabled
                self.children = []
                self.synthetic_text = 'Invalid address'

            @property
            def text(self):
                return self.synthetic_text

            def find_element(self, by, selector):
                if self.name == 'section':
                    return owner.provider
                if self.name == 'provider' and selector == ".//button[normalize-space()='Validate Address']":
                    return owner.validate
                raise AssertionError(f'Unexpected single lookup: {self.name}, {selector}')

            def find_elements(self, by, selector):
                if self.name == 'driver':
                    owner.events.append(('modal-lookup',))
                    if owner.failure == 'wait':
                        raise RuntimeError('synthetic wait failure')
                    if by != By.CSS_SELECTOR:
                        raise AssertionError('Expected token-based modal selector')
                    selectors = [part.strip().split('.') for part in selector.split(',')]
                    return [element for element in self.children
                            if any(parts[0] == 'div' and set(parts[1:]) <= set(element.classes.split())
                                   for parts in selectors)]
                if by == By.XPATH and selector == ".//button[normalize-space()='Use']":
                    return self.children
                raise AssertionError(f'Unexpected child lookup: {self.name}, {selector}')

            def is_displayed(self):
                if self.name == 'modal':
                    if owner.closing:
                        owner.closure_polls += 1
                        if owner.closure_polls >= 2 and owner.failure != 'still-open':
                            owner.open = False
                    owner.events.append(('modal-visible', owner.open))
                    return owner.open
                return self.visible

            def is_enabled(self):
                return self.enabled

            def click(self):
                owner.events.append(('click', self.name))
                if owner.failure == self.name:
                    raise RuntimeError('synthetic click failure')
                if self.name == 'validate':
                    owner.open = owner.failure != 'modal-timeout'
                elif self.name == 'use':
                    owner.closing = True

        class Wait:
            def __init__(self, target, timeout):
                self.target = target

            def until(self, condition):
                for _ in range(3):
                    value = condition(self.target)
                    if value:
                        return value
                raise TimeoutError('synthetic address timeout')

        self.section = Element('section')
        self.provider = Element('provider')
        self.validate = Element('validate')
        self.modal = Element('modal', classes='modal fade show')
        self.use = Element('use')
        self.modal.children = [self.use]
        self.driver = Element('driver')
        self.driver.children = [self.modal]
        self.driver.execute_script = Mock()
        self.element = Element
        validation = legacy_function('validate_and_complete_task')
        helper, = [node for node in ast.walk(validation)
                   if isinstance(node, ast.FunctionDef) and node.name == 'ValidateAddrPrv']
        env = {'driver': self.driver, 'By': By, 'EC': EC, 'WebDriverWait': Wait}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), '<actual provider address helper>', 'exec'), env)
        self.run_helper = env['ValidateAddrPrv']

    def test_current_and_legacy_modal_tokens_accept_only_after_closure(self):
        for classes in ('modal fade show', 'show extra modal fade', 'modal fade in', 'in fade modal'):
            with self.subTest(classes=classes):
                self.setUp()
                self.modal.classes = classes
                self.assertIs(self.run_helper(self.section), True)
                self.assertEqual([event for event in self.events if event[0] == 'click'],
                                 [('click', 'validate'), ('click', 'use')])
                self.assertEqual(self.events[-1], ('modal-visible', False))
                self.assertEqual(self.closure_polls, 2)

    def test_hidden_and_unrelated_use_controls_are_not_clicked(self):
        hidden = self.element('hidden-modal', classes='modal fade show', visible=False)
        hidden.children = [self.element('hidden-modal-use')]
        hidden_button = self.element('hidden-use', visible=False)
        disabled_button = self.element('disabled-use', enabled=False)
        unrelated = self.element('unrelated', classes='modal-dialog fade show')
        unrelated.children = [self.element('unrelated-use')]
        self.driver.children = [hidden, unrelated, self.element('outside-use'), self.modal]
        self.modal.children = [hidden_button, disabled_button, self.use]
        self.assertIs(self.run_helper(self.section), True)
        self.assertEqual([event for event in self.events if event[0] == 'click'],
                         [('click', 'validate'), ('click', 'use')])

    def test_missing_hidden_disabled_or_ambiguous_confirmation_returns_false(self):
        for case in ('hidden-modal', 'hidden-use', 'disabled-use', 'wrong-class', 'ambiguous'):
            with self.subTest(case=case):
                self.setUp()
                if case == 'hidden-modal':
                    self.modal = self.element('hidden-modal', classes='modal fade show', visible=False)
                    self.modal.children = [self.use]
                    self.driver.children = [self.modal]
                elif case == 'hidden-use':
                    self.use.visible = False
                elif case == 'disabled-use':
                    self.use.enabled = False
                elif case == 'wrong-class':
                    self.modal.classes = 'modal fade showing'
                else:
                    self.modal.children.append(self.element('other-use'))
                self.assertIs(self.run_helper(self.section), False)
                self.assertEqual([event for event in self.events if event[0] == 'click'],
                                 [('click', 'validate')])

    def test_click_wait_and_closure_failures_never_report_acceptance(self):
        for failure in ('validate', 'modal-timeout', 'wait', 'use', 'still-open'):
            with self.subTest(failure=failure):
                self.setUp()
                self.failure = failure
                self.assertIs(self.run_helper(self.section), False)
                self.assertEqual(self.events.count(('click', 'validate')), 1)
                self.assertEqual(self.events.count(('click', 'use')),
                                 int(failure in ('use', 'still-open')))

    def test_already_validated_provider_preserves_existing_fast_path(self):
        self.provider.synthetic_text = 'Validated'
        self.assertIs(self.run_helper(self.section), True)
        self.assertEqual(self.events, [])


class WorkbookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=HERE)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'synthetic.xlsx'
        excel.create_template(self.path)

    def fill(self, data, row=2):
        book = load_workbook(self.path)
        sheet = book[excel.SHEET]
        for index, (key, _, _) in enumerate(excel.COLUMNS, 1):
            if key in data:
                sheet.cell(row, index, data[key])
        book.save(self.path)
        book.close()

    def test_template_styles_and_no_sample(self):
        book = load_workbook(self.path)
        self.addCleanup(book.close)
        sheet = book[excel.SHEET]
        self.assertEqual(sheet.max_column, 35)
        self.assertEqual(sheet.freeze_panes, 'C2')
        self.assertTrue(sheet.auto_filter.ref)
        self.assertEqual(sheet['A1'].fill.fgColor.rgb, '002563EB')
        self.assertTrue(sheet['A1'].comment)
        self.assertEqual(sheet['A2'].number_format, '@')
        self.assertFalse(any(cell.value for row in sheet.iter_rows(min_row=2) for cell in row))
        self.assertEqual(len(sheet.data_validations.dataValidation), 5)
        index = next(i for i, (key, _, _) in enumerate(excel.COLUMNS, 1) if key == 'specialInstructions')
        self.assertIn('32,767 characters', sheet.cell(1, index).comment.text)
        notes = '\n'.join(str(row[0].value) for row in book['Instructions'])
        self.assertIn('Special instructions: up to 32,767 characters', notes)
        self.assertIn('All other fields: up to 1,000 characters', notes)

    def test_synthetic_roundtrip_and_row_numbers(self):
        self.fill(synthetic() | {'zip': '00123', 'dob': '2000-01-02'})
        self.fill({'claimNumber': 'SYNTHETIC-002'}, 4)
        rows = excel.read_workbook(self.path)
        self.assertEqual([r['row'] for r in rows], [2, 4])
        self.assertEqual(rows[0]['data']['zip'], '00123')
        self.assertIn('customer', rows[1]['warning'])

    def test_maximum_multiline_instructions_roundtrip_and_bridge_selection(self):
        instructions = synthetic_instructions(32767)
        self.assertEqual(len(instructions), 32767)
        self.fill(synthetic() | {'specialInstructions': instructions, 'claimID': ' ID '})
        self.fill(synthetic() | {'claimNumber': 'SYNTHETIC-004', 'specialInstructions': ' \n\t '}, 4)
        rows = excel.read_workbook(self.path)
        self.assertEqual([row['row'] for row in rows], [2, 4])
        self.assertEqual(rows[0]['data']['specialInstructions'], instructions)
        self.assertEqual(rows[0]['data']['claimID'], 'ID')
        self.assertEqual(rows[1]['data']['specialInstructions'], ' \n\t ')
        api = backend.UnityAPI(lambda: self.fail('Loading must not create controller callbacks.'))
        with patch.object(api, '_dialog', return_value='OPEN'):
            pdf = Path(self.temp.name) / 'synthetic.pdf'
            pdf.write_bytes(b'%PDF-1.4\n')
            api._window = Mock()
            api._window.create_file_dialog.return_value = [str(pdf)]
            self.assertTrue(api.choose_referral_document()['ok'])
        self.assertTrue(api.load_excel(self.path)['ok'])
        selected = api.select_excel_row(2)['data']['data']
        self.assertEqual(selected['specialInstructions'], instructions)
        checked = api.validate_fields(selected)
        self.assertTrue(checked['ok'], checked)
        self.assertEqual(checked['data']['fields']['specialInstructions'], instructions)
        self.assertEqual(api.select_excel_row(4)['data']['data']['specialInstructions'], ' \n\t ')
        self.assertEqual(api.get_state()['attachment'], {'source': 'local', 'filename': pdf.name})
        self.assertIsNone(api._thread)

    def test_ordinary_oversized_field_loads_for_correction_without_losing_instructions(self):
        instructions = synthetic_instructions(1001)
        self.fill(synthetic() | {'claimID': 'x' * 1001, 'specialInstructions': instructions})
        record = excel.read_workbook(self.path)[0]
        self.assertIn('claimID. Use text up to 1,000 characters', record['warning'])
        self.assertEqual(record['data']['claimID'], 'x' * 1001)
        self.assertEqual(record['data']['specialInstructions'], instructions)

    def test_excel_dates_and_zero_formatted_identifiers(self):
        from datetime import datetime, time as clocktime
        self.fill(synthetic() | {'dob': datetime(2000, 1, 2), 'nextApptTime': clocktime(14, 30)})
        book = load_workbook(self.path)
        index = next(i for i, (key, _, _) in enumerate(excel.COLUMNS, 1) if key == 'zip')
        cell = book[excel.SHEET].cell(2, index, 123)
        cell.number_format = '00000'
        book.save(self.path)
        book.close()
        data = excel.read_workbook(self.path)[0]['data']
        self.assertEqual((data['dob'], data['nextApptTime'], data['zip']), ('01/02/2000', '02:30 PM', '00123'))

    def test_formulas_and_errors_rejected(self):
        for value in ('=1+1', '#DIV/0!'):
            self.fill(synthetic() | {'claimID': value})
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'plain values'):
                excel.read_workbook(self.path)

    def test_bad_schema_empty_extension_duplicate(self):
        with self.assertRaisesRegex(ValueError, 'No filled rows'):
            excel.read_workbook(self.path)
        with self.assertRaisesRegex(ValueError, '.xlsx'):
            excel.read_workbook(self.path.with_suffix('.csv'))
        book = load_workbook(self.path)
        sheet = book[excel.SHEET]
        sheet['B1'] = sheet['A1'].value
        book.save(self.path)
        book.close()
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            excel.read_workbook(self.path)
        book = load_workbook(self.path)
        book[excel.SHEET].title = 'Wrong sheet'
        book.save(self.path)
        book.close()
        with self.assertRaisesRegex(ValueError, 'Missing'):
            excel.read_workbook(self.path)

    def test_malformed_optional_row_loads_with_warning(self):
        self.fill(synthetic() | {'zip': 'wrong'})
        record = excel.read_workbook(self.path)[0]
        self.assertIn('five-digit ZIP', record['warning'])
        self.assertEqual(record['data']['zip'], 'wrong')


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.calls = {'list_attachments': Mock(return_value=['synthetic-referral.pdf']),
                      'run_unity': Mock(), 'record_assignment': Mock(), 'complete_assignment': Mock()}
        self.api = backend.UnityAPI(lambda: self.calls)

    def wait(self, predicate):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            state = self.api.get_state()
            if predicate(state):
                return state
            time.sleep(.005)
        self.fail('Synthetic worker did not reach expected state.')

    def finish(self):
        state = self.wait(lambda s: not s['busy'])
        self.api._thread.join(1)
        return state

    def test_unity_stage_and_injected_derived_data(self):
        data = synthetic() | {'customer': 'Synthetic Continental Tire', 'claimType': 'Auto'}
        self.assertTrue(self.api.start(data, 'unity', True, 'MI')['ok'])
        state = self.finish()
        self.assertEqual(state['status'], 'completed')
        self.assertEqual(self.calls['run_unity'].call_args.args[2]['serviceType'], 'Medical Task')
        self.calls['complete_assignment'].assert_not_called()
        self.assertIsNone(state['prompt'])

    def test_long_instructions_reach_callbacks_exactly_and_keep_approval_gate(self):
        for length in (1001, 32767):
            with self.subTest(length=length):
                instructions = synthetic_instructions(length)
                data = synthetic() | {'specialInstructions': instructions}
                checked = self.api.validate_fields(data)
                self.assertTrue(checked['ok'], checked)
                self.assertEqual(checked['data']['fields']['specialInstructions'], instructions)
                self.assertTrue(self.api.start(data)['ok'])
                state = self.wait(lambda s: s['prompt'])
                passed = self.calls['run_unity'].call_args.args[2]
                self.assertEqual(passed['specialInstructions'], instructions)
                self.assertEqual(passed['claimNumber'], data['claimNumber'])
                self.calls['complete_assignment'].assert_not_called()
                self.assertTrue(self.api.answer_prompt(state['prompt']['id'], True)['ok'])
                self.assertEqual(self.finish()['status'], 'completed')
                self.calls['complete_assignment'].assert_called_once_with(data['claimNumber'])
                for call in self.calls.values():
                    call.reset_mock()

    def test_oversized_instructions_rejected_before_any_side_effect(self):
        factory = Mock(return_value=self.calls)
        self.api = backend.UnityAPI(factory)
        data = synthetic() | {'specialInstructions': synthetic_instructions(32768)}
        for stage in ('all', 'unity', 'assign'):
            with self.subTest(stage=stage):
                for reply in (self.api.validate_fields(data, stage), self.api.start(data, stage)):
                    self.assertFalse(reply['ok'])
                    self.assertIn('specialInstructions. Use text up to 32,767 characters', reply['error'])
                self.assertEqual(self.api.get_state()['status'], 'idle')
                self.assertIsNone(self.api._thread)
        factory.assert_not_called()
        for callback in self.calls.values():
            callback.assert_not_called()

    def test_blocking_confirm_polling_and_stale_answer(self):
        self.assertTrue(self.api.start(synthetic())['ok'])
        state = self.wait(lambda s: s['prompt'])
        identifier = state['prompt']['id']
        for _ in range(30):
            self.assertTrue(self.api.get_state()['busy'])
        self.assertFalse(self.api.answer_prompt('stale', True)['ok'])
        self.assertFalse(self.api.answer_prompt(identifier, 'yes')['ok'])
        self.assertFalse(self.api.start(synthetic())['ok'])
        self.assertTrue(self.api.answer_prompt(identifier, True)['ok'])
        self.assertFalse(self.api.answer_prompt(identifier, False)['ok'])
        self.assertEqual(self.finish()['status'], 'completed')
        self.calls['complete_assignment'].assert_called_once_with('SYNTHETIC-001')

    def test_assign_decline(self):
        self.api.start({'claimNumber': 'SYNTHETIC-001'}, 'assign')
        state = self.wait(lambda s: s['prompt'])
        self.api.answer_prompt(state['prompt']['id'], False)
        state = self.finish()
        self.assertEqual((state['status'], state['result']['reason']), ('stopped', 'icasemanager_declined'))
        for call in self.calls.values():
            call.assert_not_called()

    def test_attachment_stops_acknowledged(self):
        for files, reason in [([], 'attachment_missing'), (['synthetic-a.pdf', 'synthetic-b.pdf'], 'attachment_ambiguous')]:
            with self.subTest(reason=reason):
                self.setUp()
                self.calls['list_attachments'].return_value = files
                self.api.start(synthetic())
                state = self.wait(lambda s: s['prompt'])
                self.assertEqual(state['prompt']['kind'], 'notify')
                self.assertFalse(self.api.answer_prompt(state['prompt']['id'], False)['ok'])
                self.api.answer_prompt(state['prompt']['id'], True)
                state = self.finish()
                self.assertEqual((state['status'], state['result']['reason']), ('stopped', reason))
                self.calls['run_unity'].assert_not_called()

    def test_failures_and_tracking_preference(self):
        for tracking in (True, False):
            self.setUp()
            self.calls['run_unity'].side_effect = SystemExit(7)
            self.api.start(synthetic(), 'unity', tracking)
            state = self.finish()
            self.assertEqual(state['result']['error']['exit_code'], 7)
            self.assertEqual(state['status'], 'failed')
            self.assertEqual(self.calls['record_assignment'].call_count, int(tracking))

    def test_preflight_no_side_effects(self):
        for data, stage, jurisdiction in [({}, 'all', ''), (synthetic(), 'invalid', ''), (synthetic(), 'all', 'ZZ')]:
            self.assertFalse(self.api.start(data, stage, True, jurisdiction)['ok'])
        self.assertFalse(self.api.start(synthetic(), 'all', 'yes')['ok'])
        self.assertEqual(self.api.get_state()['status'], 'idle')
        for call in self.calls.values():
            call.assert_not_called()

    def test_worker_factory_error_and_new_run_resets_result(self):
        self.api._factory = Mock(side_effect=RuntimeError('Synthetic connection failure'))
        self.api.start(synthetic(), 'unity')
        self.assertEqual(self.finish()['result']['reason'], 'desktop_worker_failed')
        self.api._factory = lambda: self.calls
        self.api.start(synthetic(), 'unity')
        self.assertEqual(self.finish()['status'], 'completed')
        state = self.api.get_state()
        state['result']['steps'].clear()
        self.assertTrue(self.api.get_state()['result']['steps'])

    def test_default_factory_com_lifecycle(self):
        com = Mock()
        self.api = backend.UnityAPI()
        with patch.dict(sys.modules, {'pythoncom': com}), patch.object(backend, 'live_callbacks', return_value=self.calls) as live:
            self.api.start(synthetic(), 'unity')
            self.assertEqual(self.finish()['status'], 'completed')
            live.assert_called_once()
            com.CoInitialize.assert_called_once()
            com.CoUninitialize.assert_called_once()

    def test_swallowed_legacy_failure_marker_is_failed(self):
        unity = SimpleNamespace(validate_and_complete_task=lambda *args: print('error occurred: synthetic failure (line 123)'))
        with self.assertRaisesRegex(RuntimeError, 'Legacy Unity reported failure'):
            backend.checked_validate(unity, Mock(), 'Synthetic Customer', 'Invented Example', {})
        unity.validate_and_complete_task = lambda *args: print('Synthetic successful operation')
        backend.checked_validate(unity, Mock(), 'Synthetic Customer', 'Invented Example', {})

    def test_checked_flag_failure_keeps_exception_identity_and_original_type(self):
        from selenium.common.exceptions import TimeoutException

        original = TimeoutException('SYNTHETIC-PRIVATE page details')
        error = UnityFlagError('waiting for the visible flag dialog')

        def fail(*args):
            raise error from original

        unity = SimpleNamespace(validate_and_complete_task=fail)
        with self.assertRaises(UnityFlagError) as caught:
            backend.checked_validate(unity, Mock(), 'Synthetic', 'Example', {})
        self.assertIs(caught.exception, error)
        self.assertIs(caught.exception.__cause__, original)
        self.assertIs(type(caught.exception.__cause__), TimeoutException)
        self.assertNotIn('SYNTHETIC-PRIVATE', str(caught.exception))

    def test_live_portal_is_lazy_and_closes_driver_on_unrelated_failure(self):
        unity = Mock()
        loader = Mock(return_value=unity)
        config = SimpleNamespace(ATTACHMENT_FOLDER=str(HERE / 'nonexistent-synthetic-folder'), UNITY_SCRIPT='synthetic-script.py')
        with patch.dict(sys.modules, {'fcm_intake.config': config,
                                     'fcm_intake.legacy_loader': SimpleNamespace(load_module_from_path=loader)}):
            calls = backend.live_callbacks()
            loader.assert_not_called()
            self.assertEqual(calls['list_attachments'](), [])
            unity.validate_and_complete_task.side_effect = SystemExit(7)
            with self.assertRaises(SystemExit):
                calls['run_unity']('Synthetic Customer', 'Invented Example', synthetic())
            unity.validate_and_complete_task.assert_called_once_with(
                unity.create_driver.return_value, 'Synthetic Customer', 'Invented Example', synthetic())
            unity.create_driver.return_value.quit.assert_called_once()
            unity.create_driver.assert_called_once_with(detach=True)

    def test_live_flag_failure_releases_service_but_preserves_browser_and_chain(self):
        for release_failure in (None, 'service', 'connection'):
            with self.subTest(release_failure=release_failure):
                unity = Mock()
                driver = unity.create_driver.return_value
                original = ValueError('SYNTHETIC-PRIVATE Selenium details')
                flag_error = UnityFlagError('submitting the flag')

                def fail(*args):
                    raise flag_error from original

                unity.validate_and_complete_task.side_effect = fail
                if release_failure == 'service':
                    driver.service.stop.side_effect = RuntimeError('SYNTHETIC-PRIVATE service')
                if release_failure == 'connection':
                    driver.command_executor.close.side_effect = RuntimeError('SYNTHETIC-PRIVATE connection')
                config = SimpleNamespace(ATTACHMENT_FOLDER='synthetic', UNITY_SCRIPT='synthetic.py')
                with patch.dict(sys.modules, {
                        'fcm_intake.config': config,
                        'fcm_intake.legacy_loader': SimpleNamespace(load_module_from_path=lambda *args: unity)}):
                    calls = backend.live_callbacks()
                    with self.assertRaises(UnityFlagError) as caught:
                        calls['run_unity']('Synthetic', 'Example', synthetic())
                self.assertIs(caught.exception, flag_error)
                self.assertIs(caught.exception.__cause__, original)
                self.assertIn('Browser left open for manual recovery', str(caught.exception))
                self.assertIn('do not blindly retry submission', str(caught.exception))
                self.assertNotIn('SYNTHETIC-PRIVATE', str(caught.exception))
                self.assertIs(caught.exception.service_release_failed, release_failure is not None)
                unity.create_driver.assert_called_once_with(detach=True)
                unity.validate_and_complete_task.assert_called_once()
                driver.service.stop.assert_called_once()
                driver.command_executor.close.assert_called_once()
                driver.quit.assert_not_called()

    def test_live_success_and_nonflag_failures_still_quit(self):
        for failure in (None, ValueError('synthetic unrelated'), SystemExit(7)):
            with self.subTest(failure=failure):
                unity = Mock()
                unity.validate_and_complete_task.side_effect = failure
                config = SimpleNamespace(ATTACHMENT_FOLDER='synthetic', UNITY_SCRIPT='synthetic.py')
                with patch.dict(sys.modules, {
                        'fcm_intake.config': config,
                        'fcm_intake.legacy_loader': SimpleNamespace(load_module_from_path=lambda *args: unity)}):
                    calls = backend.live_callbacks()
                    if failure is None:
                        calls['run_unity']('Synthetic', 'Example', synthetic())
                    else:
                        with self.assertRaises(type(failure)):
                            calls['run_unity']('Synthetic', 'Example', synthetic())
                driver = unity.create_driver.return_value
                driver.quit.assert_called_once()
                driver.service.stop.assert_not_called()

    def test_excel_bridge_and_busy_guard(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            path = Path(directory) / 'synthetic.xlsx'
            self.assertTrue(self.api.generate_workbook(str(path))['ok'])
            book = load_workbook(path)
            for i, (key, _, _) in enumerate(excel.COLUMNS, 1):
                book[excel.SHEET].cell(2, i, synthetic()[key])
            book.save(path)
            book.close()
            self.assertTrue(self.api.load_excel(str(path))['ok'])
            self.assertEqual(self.api.select_excel_row(2)['data']['data'], synthetic())
            self.assertFalse(self.api.select_excel_row(3)['ok'])
            self.api.start(synthetic())
            state = self.wait(lambda s: s['prompt'])
            self.assertFalse(self.api.select_excel_row(2)['ok'])
            self.assertFalse(self.api.load_excel(str(path))['ok'])
            self.assertFalse(self.api.generate_workbook(str(path))['ok'])
            self.api.answer_prompt(state['prompt']['id'], False)
            self.finish()

    def pick(self, paths):
        self.api._window = Mock()
        self.api._window.create_file_dialog.return_value = paths
        with patch.object(self.api, '_dialog', return_value='OPEN'):
            return self.api.choose_referral_document()

    def test_document_picker_validation_cancel_and_session_state(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            from webview.util import parse_file_type
            for extension in ('.pDf', '.MsG', '.eMl'):
                document = Path(directory) / ('synthetic' + extension)
                document.touch()
                self.assertTrue(self.pick([str(document)])['ok'])
                state = self.api.initialize()['state']['attachment']
                self.assertEqual(state, {'source': 'local', 'filename': document.name})
                self.assertEqual(self.api._attachment_path, document.resolve())
                self.api._window.create_file_dialog.assert_called_once_with(
                    'OPEN', allow_multiple=False,
                    file_types=('Referral document (*.pdf;*.msg;*.eml;*.PDF;*.MSG;*.EML)',))
                _, patterns = parse_file_type(self.api._window.create_file_dialog.call_args.kwargs['file_types'][0])
                self.assertEqual(set(patterns.split(';')),
                                 {'*.pdf', '*.msg', '*.eml', '*.PDF', '*.MSG', '*.EML'})
                self.assertEqual(self.pick(None), {'ok': True, 'data': None})
                for suffix in ('.txt', '.zip'):
                    wrong = document.with_suffix(suffix)
                    wrong.touch()
                    self.assertFalse(self.pick([str(wrong)])['ok'])
                folder = Path(directory) / ('folder' + extension)
                folder.mkdir()
                for paths in ([str(document.with_name('missing' + extension))],
                              [str(folder)], [str(document), str(document)]):
                    with self.subTest(paths=paths):
                        self.assertFalse(self.pick(paths)['ok'])
                        self.assertEqual(self.api.get_state()['attachment'], state)
                self.assertTrue(self.api.validate_fields(synthetic())['ok'])
                self.assertEqual(self.api.get_state()['attachment'], state)
            self.assertTrue(self.api.use_rrs_export_folder()['ok'])
            self.assertIsNone(self.api._attachment_path)
            self.assertEqual(self.api.get_state()['attachment'], {'source': 'rrs', 'filename': ''})
            self.api.start(synthetic(), 'unity')
            self.assertEqual(self.finish()['result']['attachment'], 'synthetic-referral.pdf')
            self.calls['list_attachments'].assert_called_once()

    def test_document_picker_busy_and_dialog_race(self):
        self.api._state['busy'] = True
        self.assertFalse(self.pick(None)['ok'])
        self.api._window.create_file_dialog.assert_not_called()
        self.assertFalse(self.api.use_rrs_export_folder()['ok'])
        self.api._state['busy'] = False
        self.api._window.create_file_dialog.side_effect = lambda *a, **kw: self.api._state.update(busy=True)
        with patch.object(self.api, '_dialog', return_value='OPEN'):
            self.assertFalse(self.api.choose_referral_document()['ok'])
        self.assertIsNone(self.api._attachment_path)

    def test_selected_document_overrides_exports_failure_policy_and_approval(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            for extension in ('.PDF', '.mSg', '.EmL'):
                document = Path(directory) / ('synthetic' + extension)
                document.touch()
                for exports in ([], ['old-a.pdf', 'old-b.pdf']):
                    for tracking in (True, False):
                        self.calls['list_attachments'].return_value = exports
                        self.assertTrue(self.pick(str(document))['ok'])
                        self.calls['run_unity'].side_effect = RuntimeError('synthetic upload failure')
                        self.assertTrue(self.api.start(synthetic(), 'all', tracking)['ok'])
                        state = self.finish()
                        self.assertEqual(state['result']['attachment'], str(document.resolve()))
                        self.assertEqual(state['result']['reason'], 'run_unity_failed')
                        self.assertEqual(self.calls['record_assignment'].call_count, int(tracking))
                        self.calls['list_attachments'].assert_not_called()
                        self.calls['complete_assignment'].assert_not_called()
                        for call in self.calls.values():
                            call.reset_mock()
            self.calls['run_unity'].side_effect = None
            self.assertTrue(self.api.start(synthetic(), 'all')['ok'])
            state = self.wait(lambda s: s['prompt'])
            self.assertFalse(self.api.use_rrs_export_folder()['ok'])
            self.calls['complete_assignment'].assert_not_called()
            self.api.answer_prompt(state['prompt']['id'], False)
            self.assertEqual(self.finish()['result']['reason'], 'icasemanager_declined')

    def test_deleted_selected_document_never_falls_back_and_assign_ignores_it(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            for extension in ('.PDF', '.MsG', '.EmL'):
                self.setUp()
                document = Path(directory) / ('synthetic' + extension)
                document.touch()
                self.assertTrue(self.pick([str(document)])['ok'])
                document.unlink()
                for stage in ('unity', 'all'):
                    self.assertFalse(self.api.start(synthetic(), stage)['ok'])
                    self.assertIsNone(self.api._thread)
                for call in self.calls.values():
                    call.assert_not_called()
                self.assertTrue(self.api.start({'claimNumber': 'SYNTHETIC-001'}, 'assign')['ok'])
                state = self.wait(lambda s: s['prompt'])
                self.api.answer_prompt(state['prompt']['id'], True)
                self.assertEqual(self.finish()['status'], 'completed')
                self.calls['list_attachments'].assert_not_called()
                self.calls['run_unity'].assert_not_called()
                self.calls['record_assignment'].assert_not_called()
                self.calls['complete_assignment'].assert_called_once()

    def test_live_selected_document_is_exact_and_checked_before_upload(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            for name in ('old-a.pdf', 'old-b.pdf'):
                (Path(directory) / name).touch()
            for extension in ('.pDf', '.mSg', '.eML'):
                document = Path(directory) / ('synthetic' + extension)
                document.touch()
                unity = Mock()
                config = SimpleNamespace(ATTACHMENT_FOLDER=directory, UNITY_SCRIPT='synthetic-script.py')
                loader = SimpleNamespace(load_module_from_path=Mock(return_value=unity))
                with patch.dict(sys.modules, {'fcm_intake.config': config, 'fcm_intake.legacy_loader': loader}):
                    calls = backend.live_callbacks(document.resolve())
                    self.assertEqual(calls['list_attachments'](), [document.resolve()])
                    payload = synthetic()
                    calls['run_unity']('Synthetic Customer', 'Invented Example', payload)
                    unity.validate_and_complete_task.assert_called_once_with(
                        unity.create_driver.return_value, 'Synthetic Customer', 'Invented Example', payload,
                        attachment_path=str(document.resolve()))
                    unity.create_driver.return_value.quit.assert_called_once()
                    document.unlink()
                    with self.assertRaisesRegex(ValueError, 'existing referral document'):
                        calls['list_attachments']()
                    unity.create_driver.reset_mock()
                    with self.assertRaisesRegex(ValueError, 'existing referral document'):
                        calls['run_unity']('Synthetic', 'Example', {})
                    unity.create_driver.assert_not_called()
                    with self.assertRaisesRegex(ValueError, 'existing referral document'):
                        backend.checked_validate(unity, Mock(), 'Synthetic', 'Example', {}, attachment_path=document)
                    self.assertEqual(unity.validate_and_complete_task.call_count, 1)

    def test_document_disappearing_after_start_fails_controller_preflight(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            for extension in ('.PDF', '.MsG', '.eMl'):
                self.setUp()
                document = Path(directory) / ('synthetic' + extension)
                document.touch()
                self.assertTrue(self.pick([str(document)])['ok'])
                def factory():
                    document.unlink()
                    return self.calls
                self.api._factory = factory
                self.assertTrue(self.api.start(synthetic(), 'unity')['ok'])
                self.assertEqual(self.finish()['result']['reason'], 'resolve_attachment_failed')
                for call in self.calls.values():
                    call.assert_not_called()

    def test_actual_legacy_upload_ast_binds_manual_path_and_propagates_failure(self):
        function = legacy_function('validate_and_complete_task')
        upload_block, = [node for node in function.body[0].body if isinstance(node, ast.Try)
                         and any(isinstance(child, ast.ImportFrom)
                                 and child.module == 'AI.referral_attachments'
                                 for child in ast.walk(node))]
        tree = ast.Module(body=[upload_block], type_ignores=[])
        code = compile(tree, '<actual legacy upload block>', 'exec')
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            upload, globber = Mock(), Mock()
            env = {'os': os, 'glob': globber,
                   'ATTACHMENT_FOLDER': directory, 'driver': Mock(), 'time': Mock(),
                   'WebDriverWait': Mock(return_value=SimpleNamespace(until=Mock(return_value=upload))),
                   'EC': Mock(), 'By': SimpleNamespace(XPATH='xpath')}
            for extension in ('.pDf', '.MsG', '.eMl'):
                document = Path(directory) / ('synthetic' + extension)
                document.touch()
                env['attachment_path'] = str(document.resolve())
                upload.reset_mock(side_effect=True)
                exec(code, env)
                upload.send_keys.assert_called_once_with(str(document.resolve()))
                globber.glob.assert_not_called()
                upload.send_keys.side_effect = RuntimeError('synthetic selenium upload failure')
                with self.assertRaisesRegex(RuntimeError, 'synthetic selenium'):
                    exec(code, env)
                document.unlink()
                with self.assertRaisesRegex(ValueError, 'existing referral document'):
                    exec(code, env)
            for suffix in ('.txt', '.zip', '.msg'):
                invalid = Path(directory) / ('invalid' + suffix)
                if suffix == '.msg':
                    invalid.mkdir()
                else:
                    invalid.touch()
                env['attachment_path'] = str(invalid)
                with self.assertRaises(ValueError):
                    exec(code, env)
            globber.glob.assert_not_called()
            # Original four-argument/export mode retains its legacy skip behavior.
            env['attachment_path'] = None
            upload.reset_mock(side_effect=True)
            globber.glob.return_value = ['synthetic-first.pdf', 'synthetic-second.msg']
            with patch('builtins.print'):
                exec(code, env)
            upload.send_keys.assert_called_once_with('synthetic-first.pdf')
            upload.send_keys.side_effect = RuntimeError('synthetic export upload failure')
            with patch('builtins.print'):
                exec(code, env)
            globber.glob.return_value = []
            with patch('builtins.print'):
                exec(code, env)


if __name__ == '__main__':
    unittest.main()
