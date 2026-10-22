"""Synthetic desktop regression tests; unique imports coexist with sibling apps."""
import ast
import importlib.util
import json
from itertools import islice
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import textwrap
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from openpyxl import load_workbook

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
        spec_tree = ast.parse((HERE / 'unity_assignment.spec').read_text(encoding='utf-8'))
        hiddenimports = next(ast.literal_eval(node.value) for node in spec_tree.body
                             if isinstance(node, ast.Assign)
                             and any(isinstance(target, ast.Name) and target.id == 'hiddenimports'
                                     for target in node.targets))
        self.assertFalse(required - set(hiddenimports),
                         f'Raw field adapter imports missing from hiddenimports: {required - set(hiddenimports)}')


class ModelTests(unittest.TestCase):
    def test_contract_and_ast(self):
        audit = model.verify_legacy_keys()
        self.assertEqual(audit['count'], 38)
        self.assertEqual(audit['context_only'], ['nextApptTime'])
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

    def test_live_portal_is_lazy_and_always_closes_driver(self):
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
        # Read only the safe upload range, never import legacy automation or sample records.
        legacy = model.ROOT / 'src' / 'fcm_intake' / 'legacy' / 'legacy_unity.py'
        with legacy.open(encoding='utf-8-sig') as stream:
            block = ''.join(islice(stream, 1275, 1310))
        block = block[block.index('        try:'):block.index('        wait = WebDriverWait(driver, 3)')]
        tree = ast.parse(textwrap.dedent(block))
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
