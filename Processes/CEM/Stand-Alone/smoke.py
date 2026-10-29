"""Exercise the real desktop bridge with synthetic stages and explicit operator answers."""
import importlib.util
from pathlib import Path
import sys
import time


def main():
    name = '_cem_standalone_smoke_backend'
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name('backend.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    api = module.CEMAPI()
    assert api.get_state()['status'] == 'idle'
    form = dict(module.DEFAULT_FORM, employer_name='Synthetic Example Works', claim_number='SYN-001',
        claim_id='SYN-ID-002', claimant_first_name='Testy', claimant_last_name='Example',
        address1='100 Imaginary Lane', city='Exampletown', state='ZZ', postal_code='00001')
    assert api.start(form)['data'] is True
    assert not api.start(form)['ok']
    seen = set()
    for _ in range(400):
        state = api.get_state()
        if state['review'] and 'review' not in seen:
            seen.add('review')
            assert api.answer_review(state['review']['id'], True)['ok']
        if state['prompt'] and 'submit' not in seen:
            seen.add('submit')
            assert state['prompt']['environment'] == 'UAT'
            assert api.answer_prompt(state['prompt']['id'], True)['ok']
        if not state['busy']:
            break
        time.sleep(.01)
    state = api.get_state()
    assert seen == {'review', 'submit'}, seen
    assert not state['busy'] and state['result']['reason'] == 'request_submitted', state
    return 'PASS (idle, single start, review, separate submit, completed)'


if __name__ == '__main__':
    print(main())
