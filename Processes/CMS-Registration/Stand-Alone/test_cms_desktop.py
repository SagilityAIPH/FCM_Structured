"""Synthetic desktop bridge tests; no native window, credentials or portal."""
import importlib.util
import json
import os
from pathlib import Path
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_cms_registration_desktop_test_backend', HERE / 'backend.py')
backend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend)


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.form = dict(backend.DEFAULT_FORM, claim_number='SYN-0001',
                         claimant_first_name='Testy', claimant_last_name='Example')
        self.api = backend.CMSRegistrationAPI()

    def await_state(self, predicate):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = self.api.get_state()
            if predicate(state):
                return state
            time.sleep(.01)
        self.fail('Timed out waiting for synthetic bridge state')

    def excel_records(self):
        return [
            {'row': 2, 'label': 'SYN-0001', 'form': dict(self.form, cms_case_id='SYN-CASE-1'),
             'data': {'cem_employer_request': False, 'dxCode': 'SYN-DX', 'refType': 'Medical',
                      'xlCustomerName': 'Synthetic Customer', 'officeNumber': '',
                      'nested_review': {'value': 'original'}}, 'warning': 'Check missing setup values.'},
            {'row': 3, 'label': 'SYN-0002', 'form': dict(backend.DEFAULT_FORM,
                claim_number='SYN-0002', claimant_first_name='Synthetic', claimant_last_name='Other',
                referral_type=''),
             'data': {'dxCode': '', 'xlCustomerName': '', 'officeNumber': ''}, 'warning': 'CEM is unknown.'},
        ]

    def load_excel_row(self, row=2):
        with patch.object(backend, '_read_excel', return_value=self.excel_records()):
            reply = self.api.load_excel(r'D:\synthetic\CMS-Registration-Input.xlsx')
        self.assertTrue(reply['ok'])
        workbook = reply['data']
        self.assertTrue(self.api.select_excel_row(row, workbook['id'])['ok'])
        return workbook

    def test_excel_import_requires_explicit_row_and_never_starts(self):
        with patch.object(backend, '_read_excel', return_value=self.excel_records()):
            reply = self.api.load_excel(r'D:\synthetic\CMS-Registration-Input.xlsx')
        state = self.api.get_state()
        self.assertTrue(reply['ok'])
        self.assertEqual(state['data_source'], 'rrs')
        self.assertIsNone(state['excel']['selected_row'])
        self.assertIsNone(state['excel']['data'])
        self.assertIsNone(self.api._thread)
        self.assertEqual(state['excel']['filename'], 'CMS-Registration-Input.xlsx')
        self.assertNotIn(r'D:\synthetic', json.dumps(state))
        self.assertFalse(self.api.select_excel_row(2, 'stale-workbook')['ok'])
        self.assertFalse(self.api.select_excel_row(1, reply['data']['id'])['ok'])
        self.assertTrue(self.api.select_excel_row(2, reply['data']['id'])['ok'])
        self.assertEqual(self.api.get_state()['data_source'], 'excel')
        self.assertIsNone(self.api._thread)

    def test_shared_excel_reader_contract_imports_request_and_setup_in_memory(self):
        from AI import cms_registration_excel as excel
        from openpyxl import Workbook
        book = Workbook()
        book.active.title = excel.SHEET
        book.active.append(['Claim - Claim number', 'Claimant - First name',
                            'Claimant - Last name', 'CMS - Referral type',
                            'CMS - CEM employer request', 'CMS - Diagnosis code'])
        book.active.append(['SYN-0001', 'Testy', 'Example', 'Medical', 'no', 'SYN-DX'])
        with patch.object(excel, '_open', return_value=book):
            reply = self.api.load_excel(r'D:\synthetic\input.xlsx')
        self.assertTrue(reply['ok'])
        self.assertIsNone(self.api._thread)
        self.api.select_excel_row(2, reply['data']['id'])
        state = self.api.get_state()
        self.assertEqual(state['form']['claim_number'], 'SYN-0001')
        self.assertEqual(state['form']['cem_employer_request'], 'no')
        self.assertEqual(state['excel']['data']['dxCode'], 'SYN-DX')
        self.assertEqual(state['excel']['data']['officeNumber'], '')

    def test_excel_row_replaces_all_fields_and_source_switch_clears_setup(self):
        workbook = self.load_excel_row()
        self.assertTrue(self.api.select_excel_row(3, workbook['id'])['ok'])
        state = self.api.get_state()
        self.assertEqual(state['form']['claim_number'], 'SYN-0002')
        self.assertEqual(state['form']['cms_case_id'], '')
        self.assertEqual(state['form']['referral_type'], '')
        self.assertEqual(state['form']['cem_employer_request'], 'auto')
        self.assertEqual(state['excel']['data']['xlCustomerName'], '')
        self.assertNotIn('cem_employer_request', state['excel']['data'])
        self.assertNotIn('nested_review', state['excel']['data'])
        self.assertTrue(self.api.use_rrs_data()['ok'])
        state = self.api.get_state()
        self.assertEqual(state['form'], backend.DEFAULT_FORM)
        self.assertEqual(state['data_source'], 'rrs')
        self.assertIsNone(state['excel']['data'])
        self.assertIsNone(state['excel']['selected_row'])
        self.assertIsNone(self.api._selected)
        self.api.start(self.form)
        review = self.await_state(lambda s: s['review'] is not None)['review']
        self.assertEqual(review['data']['synthetic'], 'Testy Example')
        self.assertNotIn('dxCode', review['data'])
        self.api.answer_review(review['id'], False)
        self.await_state(lambda s: not s['busy'])

    def test_excel_identity_edits_rejected_but_operator_corrections_allowed(self):
        self.load_excel_row()
        form = self.api.get_state()['form']
        for key in ('claim_number', 'claimant_first_name', 'claimant_last_name'):
            with self.subTest(key=key):
                reply = self.api.start(dict(form, **{key: 'SYN-DIFFERENT'}))
                self.assertFalse(reply['ok'])
                self.assertIn('Reload the correct row', reply['error'])
                self.assertIsNone(self.api._thread)
        form.update(referral_type='Vocational', cem_employer_request='yes',
                    cms_case_id='', referral_number='SYN-REF')
        self.assertTrue(self.api.start(form)['data'])
        review = self.await_state(lambda s: s['review'] is not None)['review']
        self.assertEqual(review['case']['referral_type'], 'Vocational')
        self.assertEqual(review['data']['refType'], 'Vocational')
        self.assertEqual(review['data']['registration_excel_referral_type'], 'Medical')
        self.api.answer_review(review['id'], True)
        result = self.await_state(lambda s: not s['busy'])['result']
        self.assertTrue(result['cem'])
        self.assertEqual(result['registration']['option'], '10')

    def test_excel_data_snapshot_reaches_review_and_setup_without_default_loader(self):
        captured = []
        def stages_factory(contract):
            base = backend._offline_stages(contract)
            from dataclasses import replace
            def setup(request, case, data, on_step):
                captured.append(data)
                return base.setup_cms(request, case, data, on_step)
            return replace(base, load_data=Mock(side_effect=AssertionError('DB loader forbidden')),
                           setup_cms=setup)
        self.api = backend.CMSRegistrationAPI(stages_factory=stages_factory)
        self.load_excel_row()
        form = self.api.get_state()['form']
        self.api.start(form)
        review = self.await_state(lambda s: s['review'] is not None)['review']
        self.assertEqual(review['data']['dxCode'], 'SYN-DX')
        self.assertEqual(review['data']['registration_data_source'], 'Excel')
        self.assertEqual(review['data']['registration_excel_row'], 2)
        # Neither a UI snapshot nor the private selected-row store can change a running snapshot.
        review['data']['nested_review']['value'] = 'ui mutation'
        with self.api._lock:
            self.api._selected['data']['nested_review']['value'] = 'later mutation'
        self.assertFalse(self.api.select_excel_row(3, self.api.get_state()['excel']['id'])['ok'])
        self.assertFalse(self.api.use_rrs_data()['ok'])
        with patch.object(backend, '_read_excel') as reader:
            self.assertFalse(self.api.load_excel(r'D:\synthetic\other.xlsx')['ok'])
            reader.assert_not_called()
        self.api._window = types.SimpleNamespace(create_file_dialog=Mock())
        self.assertFalse(self.api.open_excel()['ok'])
        self.api._window.create_file_dialog.assert_not_called()
        self.api.answer_review(review['id'], True)
        result = self.await_state(lambda s: not s['busy'])['result']
        self.assertEqual(result['reason'], 'registered')
        self.assertEqual(captured[0]['nested_review']['value'], 'original')

    def test_unknown_excel_cem_stops_without_default_data_fallback(self):
        self.load_excel_row(3)
        form = dict(self.api.get_state()['form'], referral_type='Medical')
        self.api.start(form)
        state = self.await_state(lambda s: not s['busy'])
        self.assertEqual(state['result']['reason'], 'cem_status_unknown')
        self.assertIsNone(state['review'])

    def test_setup_descriptors_exclude_request_credentials_and_source_metadata(self):
        with patch.object(backend, '_load_env_files'):
            initialized = self.api.initialize()
        keys = {field['key'] for field in initialized['setup_fields']}
        self.assertIn('Special_Instructions', keys)
        self.assertIn('apptDate', keys)
        self.assertTrue(keys.isdisjoint({'review_fields', 'source_reviews', 'refType', 'cem_employer_request',
                                        'claim_number', 'username', 'password'}))
        self.assertIn('name', {field['key'] for field in initialized['provider_fields']})

    def test_excel_edits_reach_review_and_setup_without_mutating_selected_row(self):
        captured = []
        def stages_factory(contract):
            from dataclasses import replace
            base = backend._offline_stages(contract)
            def setup(request, case, data, on_step):
                captured.append(data)
                return base.setup_cms(request, case, data, on_step)
            return replace(base, load_data=Mock(side_effect=AssertionError('RRS forbidden')),
                           setup_cms=setup)
        self.api = backend.CMSRegistrationAPI(stages_factory=stages_factory)
        workbook = self.load_excel_row()
        baseline = self.api.get_state()['excel']['data']
        values = {'dxCode': '', 'xlCustomerName': 'Synthetic corrected customer',
                  'Special_Instructions': 'Synthetic line one\nSynthetic line two',
                  'apptDate': '11/04/2026', 'xlProvider': 'Synthetic Doctor',
                  'provType': 'doctor', 'xlProviderPhone': '555-0100'}
        payload = {'workbook_id': workbook['id'], 'row': 2, 'values': values}
        form = dict(self.api.get_state()['form'], referral_type='Vocational',
                    cem_employer_request='yes')
        self.assertTrue(self.api.start(form, '', '', True, payload)['data'])
        review = self.await_state(lambda s: s['review'] is not None)['review']
        for key, value in values.items():
            self.assertEqual(review['data'][key], value)
        self.assertEqual(review['data']['reviewAppointmentDate'], values['apptDate'])
        self.assertEqual(review['data']['refType'], 'Vocational')
        self.assertIs(review['data']['cem_employer_request'], True)
        values['xlCustomerName'] = 'SYN-late-mutation'
        self.assertEqual(self.api.get_state()['excel']['data'], baseline)
        self.api.answer_review(review['id'], True)
        self.assertEqual(self.await_state(lambda s: not s['busy'])['result']['reason'], 'registered')
        self.assertEqual(captured[0], review['data'])
        self.assertEqual(self.api._selected['data'], baseline)
        self.assertTrue(self.api.select_excel_row(3, workbook['id'])['ok'])
        self.assertEqual(self.api.get_state()['excel']['data']['xlCustomerName'], '')
        self.assertNotIn('Special_Instructions', self.api.get_state()['excel']['data'])
        self.assertFalse(self.api.start(self.api.get_state()['form'], excel_edits=payload)['ok'])

    def test_excel_provider_list_edits_are_the_setup_snapshot(self):
        from dataclasses import replace
        setup = Mock(return_value=[])
        self.api = backend.CMSRegistrationAPI(stages_factory=lambda contract:
            replace(backend._offline_stages(contract), setup_cms=setup))
        records = self.excel_records()
        records[0]['data']['providers'] = [
            {'name': 'Synthetic original facility', 'type': 'facility', 'phone': '555-0100'},
            {'name': 'Synthetic original doctor', 'type': 'doctor', 'phone': '555-0101'}]
        with patch.object(backend, '_read_excel', return_value=records):
            workbook = self.api.load_excel(r'D:\synthetic\input.xlsx')['data']
        self.api.select_excel_row(2, workbook['id'])
        edited = [{'name': 'Synthetic corrected facility', 'type': 'facility', 'phone': ''},
                  {'name': 'Synthetic corrected doctor', 'type': 'doctor', 'city': 'Synthetic City'}]
        payload = {'workbook_id': workbook['id'], 'row': 2, 'values': {'providers': edited}}
        form = self.api.get_state()['form']
        competing = dict(payload, values={'xlProvider': 'SYN-ignored'})
        self.assertFalse(self.api.start(form, excel_edits=competing)['ok'])
        self.assertIsNone(self.api._thread)
        self.assertTrue(self.api.start(form, excel_edits=payload)['data'])
        review = self.await_state(lambda s: s['review'] is not None)['review']
        self.assertEqual(review['data']['providers'],
                         [dict(provider, first_name='', last_name='') for provider in edited])
        edited[0]['name'] = 'SYN-late-mutation'
        self.api.answer_review(review['id'], True)
        self.await_state(lambda s: not s['busy'])
        self.assertEqual(setup.call_args.args[2]['providers'], review['data']['providers'])
        self.assertEqual(self.api._selected['data']['providers'], records[0]['data']['providers'])

    def test_edited_provider_identity_matches_existing_search_and_tab_readback_rules(self):
        from dataclasses import replace
        import run
        rules = run._load('_cms_desktop_identity_test_rules', run.CORE / 'cms_rules.py')
        steps = run._load('_cms_desktop_identity_test_steps', run.CORE / 'cms_steps.py')
        original = {'name': 'Dr. Synthetic Original, MD', 'first_name': 'Synthetic',
                    'last_name': 'Original', 'type': 'doctor', 'phone': '555-0100'}
        for edits, expected_name, expected_parts in (
            ({'name': 'Updated Doctor'}, 'Updated Doctor', ('Updated', 'Doctor')),
            ({'first_name': 'New', 'last_name': 'Person'}, 'New Person', ('New', 'Person')),
            ({'name': 'Fresh Person', 'first_name': 'Fresh', 'last_name': 'Person'},
             'Fresh Person', ('Fresh', 'Person')),
            ({'phone': ''}, original['name'], ('Synthetic', 'Original')),
        ):
            with self.subTest(edits=edits):
                setup = Mock(return_value=[])
                self.api = backend.CMSRegistrationAPI(stages_factory=lambda contract:
                    replace(backend._offline_stages(contract), setup_cms=setup))
                records = self.excel_records()
                records[0]['data']['providers'] = [dict(original)]
                with patch.object(backend, '_read_excel', return_value=records):
                    workbook = self.api.load_excel(r'D:\synthetic\input.xlsx')['data']
                self.api.select_excel_row(2, workbook['id'])
                payload = {'workbook_id': workbook['id'], 'row': 2,
                           'values': {'providers': [dict(original, **edits)]}}
                self.assertTrue(self.api.start(self.api.get_state()['form'], excel_edits=payload)['data'])
                review = self.await_state(lambda s: s['review'] is not None)['review']
                effective = review['data']['providers'][0]
                self.assertEqual(steps._provider_name(effective), expected_name)
                plan = rules.provider_search_plan(effective)[0]
                self.assertEqual((plan['first_name'], plan['last_name']), expected_parts)
                if 'name' in edits and 'first_name' not in edits:
                    self.assertEqual((effective['first_name'], effective['last_name']), ('', ''))
                self.api.answer_review(review['id'], True)
                self.await_state(lambda s: not s['busy'])
                self.assertEqual(setup.call_args.args[2]['providers'][0], effective)
                self.assertEqual(self.api._selected['data']['providers'][0], original)

    def test_contradictory_provider_identity_edits_rejected_before_worker(self):
        original = {'name': 'Dr. Synthetic Original, MD', 'first_name': 'Synthetic',
                    'last_name': 'Original', 'type': 'doctor'}
        records = self.excel_records()
        records[0]['data']['providers'] = [original]
        with patch.object(backend, '_read_excel', return_value=records):
            workbook = self.api.load_excel(r'D:\synthetic\input.xlsx')['data']
        self.api.select_excel_row(2, workbook['id'])
        for changes in (
            {'name': 'Updated Doctor', 'first_name': 'Different', 'last_name': 'Person'},
            {'first_name': '', 'last_name': 'Person'},
            {'type': 'facility', 'first_name': 'Different'},
        ):
            with self.subTest(changes=changes):
                payload = {'workbook_id': workbook['id'], 'row': 2,
                           'values': {'providers': [dict(original, **changes)]}}
                self.assertFalse(self.api.start(self.api.get_state()['form'], excel_edits=payload)['ok'])
                self.assertIsNone(self.api._thread)
                self.assertEqual(self.api._selected['data']['providers'], [original])

    def test_excel_edit_payload_rejected_before_worker_for_invalid_or_stale_values(self):
        workbook = self.load_excel_row()
        valid = {'workbook_id': workbook['id'], 'row': 2, 'values': {'dxCode': ''}}
        invalid = [
            [], {}, dict(valid, workbook_id='stale'), dict(valid, workbook_id=1),
            dict(valid, row=3), dict(valid, row=True), dict(valid, row='2'),
            dict(valid, unexpected='SYN-PRIVATE'), dict(valid, values=[]),
            dict(valid, values={'dxCode': False}),
            dict(valid, values={'review_fields': {'Claim': 'SYN-PRIVATE'}}),
            dict(valid, values={'source_reviews': {'Providers': []}}),
            dict(valid, values={'registration_excel_row': '3'}),
            dict(valid, values={'refType': 'Medical'}),
            dict(valid, values={'cem_employer_request': 'yes'}),
            dict(valid, values={'provType': 'SYN-PRIVATE'}),
            dict(valid, values={'providers': [{'name': 7}]}),
            dict(valid, values={'providers': []}),
            dict(valid, values={'providers': [{'source_row': '3'}]}),
        ]
        baseline = self.api.get_state()
        for payload in invalid:
            with self.subTest(payload=payload):
                reply = self.api.start(baseline['form'], excel_edits=payload)
                self.assertFalse(reply['ok'])
                self.assertNotIn('SYN-PRIVATE', reply['error'])
                self.assertIsNone(self.api._thread)
                self.assertEqual(self.api.get_state(), baseline)
        self.api.use_rrs_data()
        self.assertFalse(self.api.start(self.form, excel_edits=valid)['ok'])
        self.assertIsNone(self.api._thread)

    def test_new_workbook_invalidates_loaded_excel_row_without_silent_rrs_switch(self):
        self.load_excel_row()
        with patch.object(backend, '_read_excel', return_value=self.excel_records()):
            self.assertTrue(self.api.load_excel(r'D:\synthetic\other.xlsx')['ok'])
        self.assertEqual(self.api.get_state()['data_source'], 'excel')
        self.assertIsNone(self.api.get_state()['excel']['selected_row'])
        reply = self.api.start(self.form)
        self.assertFalse(reply['ok'])
        self.assertIn('Load an Excel row', reply['error'])
        self.assertIsNone(self.api._thread)

    def test_excel_bad_imports_expose_fixed_safe_errors_and_preserve_selection(self):
        self.load_excel_row()
        before = self.api.get_state()
        with patch.object(backend, '_read_excel', side_effect=ValueError(r'SYN-SECRET D:\private\claim.xlsx')):
            reply = self.api.load_excel(r'D:\private\claim.xlsx')
        self.assertFalse(reply['ok'])
        self.assertEqual(reply['error'], 'Excel workbook could not be read. Use the CMS Registration template and check its values.')
        self.assertEqual(before, self.api.get_state())
        self.assertEqual(self.api.load_excel('wrong.csv')['error'], 'Select an Excel .xlsx workbook.')
        self.assertIsNone(self.api._thread)

    def test_excel_known_validation_errors_are_displayed_without_cell_values(self):
        from AI import cms_registration_excel as excel
        from openpyxl import Workbook
        for header, value, message in (
            ('CMS - CEM employer request', 'SYN-PRIVATE', 'A2: CEM employer request must be yes, no or auto.'),
            ('Claim - Claim number', '="SYN-PRIVATE"', 'A2: replace formulas or Excel errors with plain values.'),
        ):
            with self.subTest(header=header):
                book = Workbook()
                book.active.title = excel.SHEET
                book.active.append([header])
                book.active.append([value])
                with patch.object(excel, '_open', return_value=book):
                    reply = self.api.load_excel(r'D:\private\claim.xlsx')
                self.assertEqual(reply, {'ok': False, 'error': message})
                self.assertNotIn('SYN-PRIVATE', reply['error'])
                self.assertNotIn(r'D:\private', reply['error'])
                self.assertIsNone(self.api._thread)

    def test_excel_native_picker_compatibility_cancel_and_stale_guard(self):
        for modern in (False, True):
            with self.subTest(modern=modern):
                webview = types.ModuleType('webview')
                if modern:
                    webview.FileDialog = types.SimpleNamespace(OPEN='modern-open')
                else:
                    webview.OPEN_DIALOG = 'legacy-open'
                self.api._window = types.SimpleNamespace(create_file_dialog=Mock(
                    return_value=[r'D:\synthetic\input.xlsx']))
                with patch.dict('sys.modules', {'webview': webview}), \
                     patch.object(backend, '_read_excel', return_value=self.excel_records()):
                    reply = self.api.open_excel()
                self.assertTrue(reply['ok'])
                self.api._window.create_file_dialog.assert_called_once_with(
                    'modern-open' if modern else 'legacy-open', allow_multiple=False,
                    file_types=('Excel workbook (*.xlsx)',))
                self.assertEqual(self.api.get_state()['data_source'], 'rrs')
                self.assertIsNone(self.api._thread)
                self.api._window.create_file_dialog.return_value = None
                with patch.dict('sys.modules', {'webview': webview}):
                    self.assertIsNone(self.api.open_excel()['data'])
                def stale(*args, **kwargs):
                    self.api.use_rrs_data()
                    return [r'D:\synthetic\input.xlsx']
                self.api._window.create_file_dialog.side_effect = stale
                with patch.dict('sys.modules', {'webview': webview}), \
                     patch.object(backend, '_read_excel') as reader:
                    self.assertFalse(self.api.open_excel()['ok'])
                    reader.assert_not_called()

    def test_excel_picker_cannot_apply_after_run_started_even_if_run_finished(self):
        webview = types.ModuleType('webview')
        webview.OPEN_DIALOG = 'open'
        def picker(*args, **kwargs):
            # Invalid request finishes immediately, while the picker remains open.
            self.api.start(backend.DEFAULT_FORM)
            self.await_state(lambda s: not s['busy'])
            return [r'D:\synthetic\input.xlsx']
        self.api._window = types.SimpleNamespace(create_file_dialog=picker)
        with patch.dict('sys.modules', {'webview': webview}), \
             patch.object(backend, '_read_excel') as reader:
            self.assertFalse(self.api.open_excel()['ok'])
            reader.assert_not_called()
        self.assertIsNone(self.api.get_state()['excel'])

    def test_excel_read_race_cannot_replace_newer_source(self):
        def reader(path):
            self.api.use_rrs_data()
            return self.excel_records()
        with patch.object(backend, '_read_excel', side_effect=reader):
            self.assertFalse(self.api.load_excel(r'D:\synthetic\input.xlsx')['ok'])
        self.assertIsNone(self.api.get_state()['excel'])

    def test_live_excel_needs_no_db_and_preserves_preview_and_explicit_normal_mode(self):
        sessions = []
        def factory(settings):
            base = backend._offline_stages(__import__('run').load_contract())
            from dataclasses import replace
            session = types.SimpleNamespace(settings=settings, close=Mock())
            session.setup = Mock(wraps=base.setup_cms)
            session.complete = Mock(wraps=base.complete_registration)
            session.stages = replace(base, load_data=settings['load_data'],
                                     setup_cms=session.setup, complete_registration=session.complete)
            sessions.append(session)
            return session
        self.api = backend.CMSRegistrationAPI(live=True, session_factory=factory)
        workbook = self.load_excel_row()
        form = self.api.get_state()['form']
        edits = {'workbook_id': workbook['id'], 'row': 2,
                 'values': {'dxCode': 'SYN-EDITED-DX', 'reviewOtherNotes': 'Synthetic review note'}}
        with patch.object(backend, '_load_env_files'), patch.dict(os.environ, {}, clear=True):
            for preview in (True, False):
                self.assertTrue(self.api.start(form, 'SYN-USER', 'SYN-PASSWORD', preview, edits)['data'])
                review = self.await_state(lambda s: s['review'] is not None)['review']
                self.assertEqual(review['data']['dxCode'], 'SYN-EDITED-DX')
                self.assertNotIn('cms_db_connection', sessions[-1].settings)
                self.api.answer_review(review['id'], True)
                result = self.await_state(lambda s: not s['busy'])['result']
                if preview:
                    self.assertEqual(result['reason'], 'preview_only')
                    sessions[-1].setup.assert_not_called()
                    sessions[-1].complete.assert_not_called()
                else:
                    self.assertEqual(result['reason'], 'registered')
                    self.assertEqual(sessions[-1].setup.call_args.args[2]['dxCode'], 'SYN-EDITED-DX')
                    sessions[-1].complete.assert_called_once()
                sessions[-1].close.assert_called_once()
        self.assertTrue(self.api.use_rrs_data()['ok'])
        with patch.object(backend, '_load_env_files'), patch.dict(os.environ, {}, clear=True):
            self.assertFalse(self.api.start(self.form, 'SYN-USER', 'SYN-PASSWORD')['data'])
        self.assertEqual(self.api.get_state()['error'], 'Missing setting: FCM_RRS_DB_CONNECTION')

    def test_idle_start_double_start_and_review_approve(self):
        self.assertEqual(self.api.get_state()['status'], 'idle')
        self.assertIsNone(self.api._thread)
        self.assertTrue(self.api.start(self.form)['ok'])
        review = self.await_state(lambda s: s['review'] is not None)
        self.assertFalse(self.api.start(self.form)['ok'])
        self.assertEqual(review['review']['case']['case_id'], 'SYN-CASE-1')
        self.assertEqual(review['review']['data']['synthetic'], 'Testy Example')
        identifier = review['review']['id']
        self.assertFalse(self.api.answer_review('stale-id', True)['ok'])
        self.assertTrue(self.api.answer_review(identifier, True)['ok'])
        self.assertFalse(self.api.answer_review(identifier, True)['ok'])
        result = self.await_state(lambda s: not s['busy'])['result']
        self.assertEqual((result['outcome'], result['reason']), ('completed', 'registered'))
        self.assertEqual(result['steps'][0]['status'], 'done')

    def test_cancel_review_and_new_start(self):
        self.assertTrue(self.api.start(self.form)['ok'])
        identifier = self.await_state(lambda s: s['review'] is not None)['review']['id']
        self.assertTrue(self.api.answer_review(identifier, False)['ok'])
        result = self.await_state(lambda s: not s['busy'])['result']
        self.assertEqual((result['outcome'], result['reason']), ('cancelled', 'operator_cancelled'))
        self.assertTrue(self.api.start(self.form)['ok'])
        identifier = self.await_state(lambda s: s['review'] is not None)['review']['id']
        self.api.answer_review(identifier, True)
        self.await_state(lambda s: not s['busy'])

    def test_confirm_round_trip_releases_worker_without_lock(self):
        results = []
        thread = threading.Thread(target=lambda: results.append(self.api.confirm('Synthetic check', 'Continue?')))
        thread.start()
        prompt = self.await_state(lambda s: s['prompt'] is not None)['prompt']
        self.assertEqual(prompt['kind'], 'confirm')
        self.assertFalse(self.api.answer_prompt('old-id', True)['ok'])
        self.assertTrue(self.api.answer_prompt(prompt['id'], False)['ok'])
        thread.join(5)
        self.assertEqual(results, [False])
        self.assertFalse(self.api.answer_prompt(prompt['id'], True)['ok'])

    def test_use_case_fills_form_without_restart(self):
        def make_stages(contract):
            base = backend._offline_stages(contract)
            from dataclasses import replace
            return replace(base, find_cases=lambda req: [contract.CaseCandidate('SYN-CASE-1', '2026-01-02', 'Medical'),
                                                          contract.CaseCandidate('SYN-CASE-2', '2026-01-02', 'Medical')])
        self.api = backend.CMSRegistrationAPI(stages_factory=make_stages)
        self.api.start(self.form)
        result = self.await_state(lambda s: not s['busy'])['result']
        self.assertEqual(result['reason'], 'case_ambiguous')
        self.assertEqual(len(result['candidates']), 2)
        self.assertTrue(self.api.use_case('SYN-CASE-2')['ok'])
        self.assertEqual(self.api.get_state()['form']['cms_case_id'], 'SYN-CASE-2')
        self.assertFalse(self.api.get_state()['busy'])
        self.assertFalse(self.api.use_case('SYN-OTHER')['ok'])

    def test_injected_flow_live_step_progress_and_result(self):
        def fake_flow(request, *, stages, on_stage, on_step):
            on_stage('CMS_SETUP')
            from run import load_contract
            on_step(load_contract().StepResult('synthetic_manual', 'manual', 'operator confirmed'))
            return {'outcome': 'stopped', 'reason': 'cem_status_unknown', 'stage': 'DATA',
                    'stages': ['START', 'CASE'], 'case_id': 'SYN-CASE-1', 'candidates': [],
                    'steps': [], 'registration': None, 'cem': None, 'problems': [], 'error': None}
        self.api = backend.CMSRegistrationAPI(flow=fake_flow)
        self.assertTrue(self.api.start(self.form)['ok'])
        state = self.await_state(lambda s: not s['busy'])
        self.assertEqual((state['status'], state['result']['reason']), ('stopped', 'cem_status_unknown'))
        self.assertEqual(state['stage'], 'CMS_SETUP')
        self.assertEqual(state['steps'][0]['status'], 'manual')

    def test_start_rejection_is_atomic_across_threads(self):
        responses = []
        gate = threading.Barrier(3)
        def start():
            gate.wait()
            responses.append(self.api.start(self.form))
        a, b = threading.Thread(target=start), threading.Thread(target=start)
        a.start(); b.start(); gate.wait()
        a.join(5); b.join(5)
        self.assertEqual(sorted(x['ok'] for x in responses), [False, True])
        prompt = self.await_state(lambda s: s['review'] is not None)['review']
        self.api.answer_review(prompt['id'], False)
        self.await_state(lambda s: not s['busy'])

    def test_repeated_starts_never_overlap_workers(self):
        calls = []
        def flow(request, *, stages, on_stage, on_step):
            calls.append('entered')
            on_stage('REVIEW')
            stages.review(request, type('Case', (), {'case_id': 'SYN-CASE-1',
                'assigned_date': '2026-01-01', 'referral_type': 'Medical'})(), {})
            return {'outcome': 'cancelled', 'reason': 'operator_cancelled', 'stage': 'REVIEW',
                    'stages': ['START', 'CASE', 'DATA'], 'case_id': 'SYN-CASE-1',
                    'candidates': [], 'steps': [], 'registration': None, 'cem': False,
                    'problems': [], 'error': None}
        self.api = backend.CMSRegistrationAPI(flow=flow)
        self.api.start(self.form)
        first = self.await_state(lambda s: s['review'] is not None)['review']['id']
        self.api.answer_review(first, False)
        self.await_state(lambda s: not s['busy'])
        self.api.start(self.form)
        second = self.await_state(lambda s: s['review'] is not None)['review']['id']
        self.assertNotEqual(first, second)
        self.assertFalse(self.api.answer_review(first, True)['ok'])
        self.assertEqual(len(calls), 2)
        self.api.answer_review(second, False)
        self.await_state(lambda s: not s['busy'])

    def test_result_shapes_all_outcomes(self):
        import run
        for name, expected, result, ok in run.scenario_rows():
            with self.subTest(name=name):
                self.assertTrue(ok)
                self.assertEqual(set(result), {'outcome', 'reason', 'stage', 'stages', 'case_id', 'candidates', 'steps', 'registration', 'cem', 'problems', 'error'})
                self.assertIn(result['outcome'], ('completed', 'stopped', 'cancelled', 'failed'))

    def test_live_configuration_names_only_and_secret_isolation(self):
        class Session:
            def __init__(self, settings):
                self.settings = settings
                self.closed = 0
                self.stages = backend._offline_stages(__import__('run').load_contract())
            def close(self):
                self.closed += 1
        sessions = []
        def factory(settings):
            session = Session(settings)
            from dataclasses import replace
            session.stages = replace(session.stages, load_data=lambda req, case: {
                'cem_employer_request': False, 'synthetic': 'Testy Example',
                'accidental_secret': settings['cms_password'],
                'accidental_lookup_setting': settings['cms_db_connection']})
            sessions.append(session)
            return session
        self.api = backend.CMSRegistrationAPI(live=True, session_factory=factory)
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(self.api.start(self.form)['ok'])
            self.assertFalse(self.api.get_state()['busy'])
            self.assertIn('FCM_RRS_DB_CONNECTION', self.api.get_state()['error'])
            self.assertNotIn('FCM_CMS_REFERENCE_DIR', self.api.get_state()['error'])
        db = 'SYN-DB-SECRET-NEVER-EXPOSE'
        password = 'SYN-PASSWORD-NEVER-EXPOSE'
        with patch.dict(os.environ, {'FCM_RRS_DB_CONNECTION': db, 'FCM_CMS_REFERENCE_DIR': 'SYN-REFERENCE-DIR'}):
            self.assertTrue(self.api.start(self.form)['ok'])
            prompt = self.await_state(lambda s: s['prompt'] is not None)['prompt']
            self.assertEqual(prompt['kind'], 'credentials')
            snapshots = [self.api.get_state()]
            self.assertFalse(self.api.answer_credentials('stale', 'SYN-USER', password)['ok'])
            self.assertTrue(self.api.answer_credentials(prompt['id'], 'SYN-USER', password)['ok'])
            review = self.await_state(lambda s: s['review'] is not None)
            snapshots.append(review)
            self.assertTrue(self.api.answer_review(review['review']['id'], True)['ok'])
            snapshots.append(self.await_state(lambda s: not s['busy']))
            self.assertEqual(sessions[0].closed, 1)
            self.assertEqual(sessions[0].settings['cms_password'], password)
            for snapshot in snapshots:
                text = json.dumps(snapshot)
                for secret in (password, 'SYN-USER', db):
                    self.assertNotIn(secret, text)
            report = '\n'.join(__import__('run').report_rows(__import__('run').scenario_rows()))
            self.assertNotIn(password, report)
            self.assertNotIn(db, report)

    def test_live_ui_credentials_skip_prompt(self):
        sessions = []
        def factory(settings):
            sessions.append(settings['cms_user'])
            session = type('S', (), {'closed': 0, 'close': lambda s: None})()
            session.stages = backend._offline_stages(__import__('run').load_contract())
            return session
        self.api = backend.CMSRegistrationAPI(live=True, session_factory=factory)
        with patch.dict(os.environ, {'FCM_RRS_DB_CONNECTION': 'SYN-DB'}):
            self.assertTrue(self.api.start(self.form, 'SYN-USER', 'SYN-PASSWORD')['ok'])
            review = self.await_state(lambda s: s['review'] is not None)
            self.assertIsNone(review['prompt'])
            self.assertEqual(sessions, ['SYN-USER'])
            self.assertNotIn('SYN-PASSWORD', json.dumps(review))
            self.assertTrue(self.api.answer_review(review['review']['id'], True)['ok'])
            self.await_state(lambda s: not s['busy'])

    def test_live_cancel_credentials_closes_nothing(self):
        self.api = backend.CMSRegistrationAPI(live=True, session_factory=lambda settings: self.fail('should not open'))
        with patch.dict(os.environ, {'FCM_RRS_DB_CONNECTION': 'SYN-DB', 'FCM_CMS_REFERENCE_DIR': 'SYN-REF'}):
            self.api.start(self.form)
            prompt = self.await_state(lambda s: s['prompt'] is not None)['prompt']
            self.assertTrue(self.api.cancel_credentials(prompt['id'])['ok'])
            result = self.await_state(lambda s: not s['busy'])['result']
            self.assertEqual(result['outcome'], 'cancelled')

    def test_live_requires_rrs_without_cms_fallback(self):
        from unittest.mock import Mock
        factory = Mock()
        self.api = backend.CMSRegistrationAPI(live=True, session_factory=factory)
        with patch.object(backend, '_load_env_files'), patch.dict(
                os.environ, {'FCM_CMS_DB_CONNECTION': 'SYN-CMS-UNUSED'}, clear=True):
            reply = self.api.start(self.form, 'SYN-USER', 'SYN-PASSWORD')
        self.assertTrue(reply['ok'])
        self.assertFalse(reply['data'])
        self.assertEqual(self.api.get_state()['error'], 'Missing setting: FCM_RRS_DB_CONNECTION')
        factory.assert_not_called()
        self.assertIsNone(self.api._thread)

    def test_live_preview_defaults_safe_and_explicit_registration_is_per_run(self):
        from dataclasses import replace
        from unittest.mock import Mock
        sessions = []
        def factory(settings):
            base = backend._offline_stages(__import__('run').load_contract())
            session = type('Session', (), {})()
            session.settings = settings
            session.close = Mock()
            session.setup = Mock(wraps=base.setup_cms)
            session.complete = Mock(wraps=base.complete_registration)
            session.stages = replace(base, setup_cms=session.setup,
                                     complete_registration=session.complete)
            sessions.append(session)
            return session
        self.api = backend.CMSRegistrationAPI(live=True, session_factory=factory)
        self.assertTrue(self.api.get_state()['preview_only'])
        with patch.object(backend, '_load_env_files'), patch.dict(os.environ, {
                'FCM_RRS_DB_CONNECTION': 'SYN-RRS-LOOKUP',
                'FCM_CMS_DB_CONNECTION': 'SYN-CMS-MUST-NOT-BE-USED'}, clear=True):
            for flag in (None, False, None):
                with self.subTest(preview_only=flag, run=len(sessions)):
                    args = () if flag is None else (flag,)
                    self.assertTrue(self.api.start(self.form, 'SYN-USER', 'SYN-PASSWORD', *args)['data'])
                    review = self.await_state(lambda s: s['review'] is not None)
                    expected_preview = flag is not False
                    self.assertEqual(review['preview_only'], expected_preview)
                    session = sessions[-1]
                    self.assertEqual(session.settings['cms_db_connection'], 'SYN-RRS-LOOKUP')
                    self.assertEqual(session.settings['preview_only'], expected_preview)
                    self.api.answer_review(review['review']['id'], True)
                    state = self.await_state(lambda s: not s['busy'])
                    result = state['result']
                    self.assertEqual(result['preview_only'], expected_preview)
                    self.assertEqual(state['preview_only'], expected_preview)
                    if expected_preview:
                        self.assertEqual((result['outcome'], result['reason'], result['stage']),
                                         ('stopped', 'preview_only', 'REVIEW'))
                        self.assertIsNone(result['registration'])
                        self.assertEqual(result['steps'], [])
                        session.setup.assert_not_called()
                        session.complete.assert_not_called()
                    else:
                        self.assertEqual((result['outcome'], result['reason']), ('completed', 'registered'))
                        session.setup.assert_called_once()
                        session.complete.assert_called_once()
                    session.close.assert_called_once()

    def test_live_worker_failure_never_exposes_driver_details(self):
        sensitive = 'SYN-CLAIMANT-PRIVATE SYN-PASSWORD-COMPONENT SYN-DB-SERVER'
        def broken(settings):
            raise RuntimeError(sensitive)
        self.api = backend.CMSRegistrationAPI(live=True, session_factory=broken)
        with patch.object(backend, '_load_env_files'), patch.dict(
                os.environ, {'FCM_RRS_DB_CONNECTION': 'SYN-DB'}, clear=True):
            self.api.start(self.form, 'SYN-USER', 'SYN-PASSWORD')
            state = self.await_state(lambda s: not s['busy'])
        self.assertEqual(state['result']['reason'], 'desktop_worker_failed')
        self.assertTrue(state['result']['preview_only'])
        self.assertNotIn(sensitive, json.dumps(state))
        self.assertEqual(state['result']['error']['message'],
                         'Desktop worker failed; registration is not verified.')

    def test_preview_flag_requires_boolean_without_starting_worker(self):
        self.assertFalse(self.api.start(self.form, preview_only='false')['ok'])
        self.assertIsNone(self.api._thread)


if __name__ == '__main__':
    unittest.main()
