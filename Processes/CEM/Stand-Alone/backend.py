"""Session-only CEM desktop bridge; nothing runs before explicit Start."""
from copy import deepcopy
from dataclasses import asdict, replace
from functools import wraps
import threading
import time
import uuid
import importlib.util
from pathlib import Path
import sys


def _runner():
    name = '_cem_standalone_runner'
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name('run.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]

FIELDS = ('employer_name', 'claim_number', 'claim_id', 'claimant_first_name', 'claimant_last_name',
          'address1', 'address2', 'city', 'state', 'postal_code', 'country', 'referral_number', 'record_id')
DEFAULT_FORM = {field: ('USA' if field == 'country' else '') for field in FIELDS}


def response(fn):
    @wraps(fn)
    def call(*args, **kwargs):
        try:
            return {'ok': True, 'data': fn(*args, **kwargs)}
        except (Exception, SystemExit) as exc:
            return {'ok': False, 'error': f'{type(exc).__name__}: action unavailable'}
    return call


class CEMAPI:
    def __init__(self, *, flow=None, stages_factory=None, live=False, session_factory=None, settings_factory=None):
        self._lock = threading.RLock()
        self._flow, self._stages_factory = flow, stages_factory
        self._live, self._session_factory, self._settings_factory = live, session_factory, settings_factory
        self._waiter = None
        self._started = None
        self._state = dict(status='idle', busy=False, stage='', elapsed=0,
                           form=dict(DEFAULT_FORM), environment='uat', review=None,
                           prompt=None, steps=[], result=None, error='')

    def initialize(self):
        return {'state': self.get_state(), 'live': self._live}

    def get_state(self):
        with self._lock:
            result = deepcopy(self._state)
            if result['busy'] and self._started is not None:
                result['elapsed'] = round(time.monotonic() - self._started, 1)
            return result

    def _pending(self, kind, request, filled, settings):
        waiter = {'event': threading.Event(), 'answer': None, 'kind': kind}
        identifier = str(uuid.uuid4())
        with self._lock:
            if self._waiter is not None:
                raise RuntimeError('Operator response already pending.')
            self._waiter = waiter
            if kind == 'review':
                self._state['review'] = {'id': identifier, 'values': {
                    **{key: filled.get(key, '') for key in ('employer_name', 'bill_to_name', 'bill_to_code',
                       'address1', 'address2', 'city', 'state', 'postal_code', 'country')},
                    'claim_number': request.claim_number, 'claim_id': request.claim_id,
                    'claimant_first_name': request.claimant_first_name,
                    'claimant_last_name': request.claimant_last_name}}
            else:
                self._state['prompt'] = {'id': identifier, 'kind': 'submit_confirmation',
                    'title': 'Final submit confirmation', 'environment': settings.environment.upper(),
                    'message': 'Irreversible: Submit this employer request once to the '
                               + settings.environment.upper() + ' portal? Do not resubmit if the response is uncertain.'}
        try:
            waiter['event'].wait()  # Never hold state lock while awaiting operator action.
            return waiter['answer']
        finally:
            with self._lock:
                if self._waiter is waiter:
                    self._waiter = None
                    self._state['review'] = None
                    self._state['prompt'] = None

    def review(self, request, filled, settings):
        return self._pending('review', request, filled, settings)

    def confirm_submit(self, request, filled, settings):
        return self._pending('submit_confirmation', request, filled, settings)

    def _answer(self, identifier, kind, answer):
        if type(answer) is not bool:
            raise ValueError('Answer must be boolean.')
        with self._lock:
            item = self._state['review' if kind == 'review' else 'prompt']
            if not item or item['id'] != identifier or not self._waiter or self._waiter['kind'] != kind:
                raise ValueError('Stale operator response.')
            waiter = self._waiter
            waiter['answer'] = answer
            self._waiter = None
            self._state['review'] = None
            self._state['prompt'] = None
            waiter['event'].set()
        return True

    @response
    def answer_review(self, identifier, approved):
        return self._answer(identifier, 'review', approved)

    @response
    def answer_prompt(self, identifier, confirmed):
        return self._answer(identifier, 'submit_confirmation', confirmed)

    @response
    def start(self, form):
        runner = _runner()
        request = runner.request_from_form(form, runner.load_contract())
        with self._lock:
            if self._state['busy']:
                raise ValueError('A CEM request is already running.')
            self._state.update(status='running', busy=True, stage='START', elapsed=0,
                form={key: form.get(key, default) for key, default in DEFAULT_FORM.items()},
                review=None, prompt=None, steps=[], result=None, error='')
            self._started = time.monotonic()
            thread = threading.Thread(target=self._run, args=(request,), daemon=True)
            # Atomic reservation above prevents any second start, including before thread scheduling.
        thread.start()
        return True

    def _stage(self, stage):
        with self._lock:
            self._state['stage'] = stage

    def _step(self, step):
        with self._lock:
            self._state['steps'].append(asdict(step))

    def _run(self, request):
        session = None
        try:
            runner = _runner()
            contract = runner.load_contract()
            settings = (self._settings_factory() if self._settings_factory else
                        runner.live_settings() if self._live else runner.synthetic_settings(contract=contract))
            with self._lock:
                self._state['environment'] = settings.environment.upper()
            # Validate before creating any live browser, including the environment/URL guard.
            valid_config = (settings.environment in ('uat', 'production') and
                bool(settings.employer_search_url and settings.employer_add_url and settings.cem_log_path) and
                all(str(url).startswith('https://') for url in (settings.employer_search_url, settings.employer_add_url)))
            if self._live and not request.validate() and valid_config:
                session = (self._session_factory or runner.load_live)(settings)
                stages = session.stages
            else:
                stages = self._stages_factory(contract) if self._stages_factory else runner.synthetic_stages(contract)
            stages = replace(stages, review=self.review, confirm_submit=self.confirm_submit)
            flow = self._flow or runner.load_core().run
            result = flow(request, stages=stages, settings=settings, on_stage=self._stage, on_step=self._step)
            with self._lock:
                self._state.update(status=result['outcome'], result=deepcopy(result), steps=deepcopy(result['steps']))
        except (Exception, SystemExit):
            with self._lock:
                self._state.update(status='failed', result={
                    'outcome': 'failed', 'reason': 'desktop_worker_failed', 'stage': self._state['stage'],
                    'steps': [], 'warning': 'Inspect before resubmitting; outcome may be uncertain.',
                    'problems': [], 'error': {'message': 'Worker failed; inspect locally.'}})
        finally:
            if session is not None:
                try:
                    session.close()
                except (Exception, SystemExit):
                    with self._lock:
                        self._state['error'] = 'Live session cleanup failed; inspect the portal.'
            with self._lock:
                self._state.update(busy=False, elapsed=round(time.monotonic() - self._started, 1))
