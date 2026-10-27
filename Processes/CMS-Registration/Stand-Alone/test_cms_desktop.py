"""Synthetic desktop bridge tests; no native window, credentials or portal."""
import importlib.util
import json
import os
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

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
                'accidental_secret': settings['cms_password']})
            sessions.append(session)
            return session
        self.api = backend.CMSRegistrationAPI(live=True, session_factory=factory)
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(self.api.start(self.form)['ok'])
            self.assertFalse(self.api.get_state()['busy'])
            self.assertIn('FCM_CMS_DB_CONNECTION', self.api.get_state()['error'])
            self.assertIn('FCM_CMS_REFERENCE_DIR', self.api.get_state()['error'])
        db = 'SYN-DB-SECRET-NEVER-EXPOSE'
        password = 'SYN-PASSWORD-NEVER-EXPOSE'
        with patch.dict(os.environ, {'FCM_CMS_DB_CONNECTION': db, 'FCM_CMS_REFERENCE_DIR': 'SYN-REFERENCE-DIR'}):
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

    def test_live_cancel_credentials_closes_nothing(self):
        self.api = backend.CMSRegistrationAPI(live=True, session_factory=lambda settings: self.fail('should not open'))
        with patch.dict(os.environ, {'FCM_CMS_DB_CONNECTION': 'SYN-DB', 'FCM_CMS_REFERENCE_DIR': 'SYN-REF'}):
            self.api.start(self.form)
            prompt = self.await_state(lambda s: s['prompt'] is not None)['prompt']
            self.assertTrue(self.api.cancel_credentials(prompt['id'])['ok'])
            result = self.await_state(lambda s: not s['busy'])['result']
            self.assertEqual(result['outcome'], 'cancelled')


if __name__ == '__main__':
    unittest.main()
