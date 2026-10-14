"""Synthetic desktop regression tests; unique imports coexist with sibling apps."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import time
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

    def test_synthetic_roundtrip_and_row_numbers(self):
        self.fill(synthetic() | {'zip': '00123', 'dob': '2000-01-02'})
        self.fill({'claimNumber': 'SYNTHETIC-002'}, 4)
        rows = excel.read_workbook(self.path)
        self.assertEqual([r['row'] for r in rows], [2, 4])
        self.assertEqual(rows[0]['data']['zip'], '00123')
        self.assertIn('customer', rows[1]['warning'])

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


if __name__ == '__main__':
    unittest.main()
