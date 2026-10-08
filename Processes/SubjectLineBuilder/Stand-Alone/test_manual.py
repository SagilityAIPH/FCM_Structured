import ast
import importlib.util
from pathlib import Path
import time
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('manual_subject_backend', HERE / 'backend.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
from manual_flow import defaults, validate, run_manual, Stopped


def payload():
    return defaults() | {'customer': 'Synthetic', 'claimNumber': 'TEST-001',
        'claimantFirst': 'Alex', 'claimantLast': 'Example', 'providerLast': 'Doctor'}


class Adapter:
    def __init__(self): self.events = []
    def open(self): self.events.append('open')
    def identity(self, data): self.events.append('identity')
    def lookup(self, kind, data): self.events.append(kind)
    def ensure_lookup_closed(self): pass
    def details(self, data): self.events.append('details')
    def create(self, data): self.events.append('create')


class ManualTests(unittest.TestCase):
    def test_validation_and_date_only_appointment(self):
        data = validate(payload() | {'nextApptDate': '2027-03-04'})
        self.assertEqual(data['nextApptDate'], '03/04/2027')
        self.assertEqual(data['nextApptTime'], '')
        for bad in ({'claimNumber': ''}, {'nextApptDate': '3/4'}, {'state': '{ENTER}'}, {'nextApptTime': 'noon'}, {'refSource': 'unknown'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError): validate(payload() | bad)

    def test_scope_and_final_create_gate(self):
        a = Adapter()
        reviews = []
        def review(message, final):
            self.assertNotIn('create', a.events)
            reviews.append(final)
        run_manual(validate(payload()), a, lambda *_:None, review, lambda:None)
        self.assertEqual(a.events, ['open', 'identity', 'claimant', 'like_items', 'provider', 'details', 'create'])
        self.assertEqual(reviews, [False, False, False, True])

    def test_stop_at_review_does_not_create(self):
        a = Adapter()
        def stop(*_): raise Stopped()
        with self.assertRaises(Stopped): run_manual(validate(payload()), a, lambda *_:None, stop, lambda:None)
        self.assertNotIn('create', a.events)

    def test_lookup_failure_does_not_create(self):
        a = Adapter()
        def fail(): raise RuntimeError('Lookup still open')
        a.ensure_lookup_closed = fail
        with self.assertRaises(RuntimeError): run_manual(validate(payload()), a, lambda *_:None, lambda *_:None, lambda:None)
        self.assertNotIn('create', a.events)

    def test_bridge_blocks_duplicate_start_and_stale_review(self):
        a = Adapter()
        api = module.ManualAPI(lambda _:a)
        self.assertTrue(api.start(payload())['ok'])
        self.assertFalse(api.start(payload())['ok'])
        deadline = time.monotonic()+3
        while api.get_state()['status'] != 'lookup' and time.monotonic()<deadline: time.sleep(.01)
        state = api.get_state()
        self.assertEqual(state['status'], 'lookup')
        self.assertFalse(api.proceed(state['review_id'], True)['ok'])
        self.assertFalse(api.proceed(state['review_id']-1, False)['ok'])
        api.stop()
        api._thread.join(3)
        self.assertEqual(api.get_state()['status'], 'stopped')
        self.assertNotIn('create', a.events)

    def test_no_legacy_or_upstream_imports(self):
        for file in ('manual_flow.py', 'rrs_ui.py'):
            tree = ast.parse((HERE.parent/'Deploy-Ready'/file).read_text())
            names = [n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
            self.assertFalse(any(any(word in name for word in ('legacy', 'bedrock', 'reopen', 'daily_output')) for name in names))


if __name__ == '__main__': unittest.main()
