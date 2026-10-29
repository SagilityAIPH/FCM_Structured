"""Operator gate, review and confirmation bridge regressions (synthetic only)."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('_cem_standalone_test_backend', HERE / 'backend.py')
backend = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = backend
spec.loader.exec_module(backend)
FORM = dict(backend.DEFAULT_FORM, employer_name='Synthetic Example Works', claim_number='SYN-001',
    claim_id='SYN-ID-002', claimant_first_name='Testy', claimant_last_name='Example',
    address1='100 Imaginary Lane', city='Exampletown', state='ZZ', postal_code='00001')


def until(api, key):
    for _ in range(500):
        state = api.get_state()
        if state[key]:
            return state[key]
        if not state['busy']:
            raise AssertionError(state)
        time.sleep(.01)
    raise AssertionError('Timed out waiting for ' + key)


def finished(api):
    for _ in range(500):
        state = api.get_state()
        if not state['busy']:
            return state['result']
        time.sleep(.01)
    raise AssertionError('Worker did not finish')


class DesktopTests(unittest.TestCase):
    def test_idle_and_single_start_atomic(self):
        api = backend.CEMAPI()
        self.assertEqual(api.initialize()['state']['status'], 'idle')
        self.assertTrue(api.start(FORM)['ok'])
        self.assertFalse(api.start(FORM)['ok'])
        review = until(api, 'review')
        self.assertEqual(review['values']['claim_id'], 'SYN-ID-002')
        self.assertEqual(review['values']['bill_to_code'], 'C02283')
        self.assertFalse(api.answer_review('stale', True)['ok'])
        self.assertTrue(api.answer_review(review['id'], True)['ok'])
        self.assertFalse(api.answer_review(review['id'], True)['ok'])
        prompt = until(api, 'prompt')
        self.assertEqual(prompt['environment'], 'UAT')
        self.assertIn('Irreversible', prompt['message'])
        self.assertFalse(api.answer_prompt('stale', True)['ok'])
        self.assertTrue(api.answer_prompt(prompt['id'], True)['ok'])
        self.assertFalse(api.answer_prompt(prompt['id'], True)['ok'])
        self.assertEqual(finished(api)['reason'], 'request_submitted')

    def test_review_cancel(self):
        api = backend.CEMAPI()
        api.start(FORM)
        review = until(api, 'review')
        self.assertTrue(api.answer_review(review['id'], False)['ok'])
        self.assertEqual(finished(api)['reason'], 'operator_cancelled')
        self.assertIsNone(api.get_state()['prompt'])

    def test_submit_decline(self):
        api = backend.CEMAPI()
        api.start(FORM)
        self.assertTrue(api.answer_review(until(api, 'review')['id'], True)['ok'])
        self.assertTrue(api.answer_prompt(until(api, 'prompt')['id'], False)['ok'])
        result = finished(api)
        self.assertEqual((result['outcome'], result['reason']), ('cancelled', 'submit_declined'))
        self.assertEqual(result['request_status'], 'not_submitted')

    def test_offline_import_purity_in_fresh_subprocess(self):
        code = "import importlib.util,sys; p=r'" + str(HERE / 'backend.py') + "'; s=importlib.util.spec_from_file_location('_cem_purity_backend',p); m=importlib.util.module_from_spec(s);s.loader.exec_module(m);a=m.CEMAPI();assert a.get_state()['status']=='idle'; assert not any(x in sys.modules for x in ('selenium','webview','_cem_standalone_steps'))"
        done = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=15)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_invalid_live_configuration_never_opens_session(self):
        from unittest.mock import Mock
        runner = backend._runner()
        factory = Mock(side_effect=AssertionError('Browser must stay closed'))
        api = backend.CEMAPI(live=True, session_factory=factory,
            settings_factory=lambda: runner.load_contract().CEMSettings())
        self.assertTrue(api.start(FORM)['ok'])
        self.assertEqual(finished(api)['reason'], 'configuration_required')
        factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
