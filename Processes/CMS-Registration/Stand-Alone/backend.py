"""Attended, session-only pywebview bridge. No live imports until Start."""
from copy import deepcopy
from dataclasses import replace
from functools import wraps
import os
import threading
import time
import uuid


def response(fn):
    @wraps(fn)
    def call(*args, **kwargs):
        try:
            return {'ok': True, 'data': fn(*args, **kwargs)}
        except (Exception, SystemExit) as error:
            # Do not relay arbitrary live exception text (may contain credentials).
            return {'ok': False, 'error': f'{type(error).__name__}: action unavailable'}
    return call


DEFAULT_FORM = {'claim_number': '', 'claimant_first_name': '', 'claimant_last_name': '',
                'referral_type': 'Medical', 'cms_case_id': '', 'referral_number': '',
                'cem_employer_request': 'auto'}
REASONS = {
    'registered': 'Registration verified against the selected CMS case.',
    'invalid_request': 'Correct the required claim, claimant and referral type fields.',
    'no_matching_case': 'No CMS case matches this referral type. Check the handoff.',
    'case_ambiguous': 'Several cases or missing assignment dates prevent safe selection. Choose a verified case and press Start again.',
    'case_not_confirmed': 'The entered CMS case ID was not uniquely confirmed. Choose a verified case and press Start again.',
    'cem_status_unknown': 'Confirm whether this is a CEM employer request before registration.',
    'operator_cancelled': 'Review cancelled by the operator. Registration was not attempted.',
    'cms_step_failed': 'CMS setup failed. Registration was not attempted.',
    'registration_not_verified': 'The registration option, case ID entry or case ID readback did not match.',
    'exception': 'The process encountered an error. Registration is not verified.',
    'desktop_worker_failed': 'The desktop worker stopped unexpectedly. Registration is not verified.',
}


class CMSRegistrationAPI:
    def __init__(self, *, flow=None, stages_factory=None, live=False, session_factory=None):
        self._lock = threading.RLock()
        self._flow = flow
        self._stages_factory = stages_factory
        self._session_factory = session_factory
        self._live = live
        self._thread = None
        self._waiter = None
        self._started = None
        self._secrets = []
        self._generation = 0
        self._state = {'status': 'idle', 'busy': False, 'stage': '', 'elapsed': 0,
                       'form': dict(DEFAULT_FORM), 'prompt': None, 'review': None,
                       'steps': [], 'result': None, 'error': ''}

    def initialize(self):
        return {'state': self.get_state(), 'live': self._live}

    def get_state(self):
        with self._lock:
            state = deepcopy(self._state)
            if state['busy'] and self._started:
                state['elapsed'] = round(time.monotonic() - self._started, 1)
            return _redact(state, self._secrets)

    def _pending(self, kind, title, message, *, case=None, data=None):
        waiter = {'event': threading.Event(), 'answer': None}
        identifier = str(uuid.uuid4())
        with self._lock:
            if self._waiter is not None:
                raise RuntimeError('Another operator response is pending.')
            self._waiter = waiter
            if kind == 'review':
                self._state['review'] = {'id': identifier, 'case': _redact({'case_id': case.case_id,
                    'assigned_date': case.assigned_date, 'referral_type': case.referral_type}, self._secrets),
                    'data': _redact(deepcopy(data), self._secrets)}
            else:
                self._state['prompt'] = _redact({'id': identifier, 'kind': kind,
                                          'title': title, 'message': message}, self._secrets)
        try:
            waiter['event'].wait()  # Lock is not held while the operator decides.
            return waiter['answer']
        finally:
            with self._lock:
                if self._waiter is waiter:
                    self._waiter = None
                    self._state['prompt'] = None
                    self._state['review'] = None

    def confirm(self, title, message):
        return self._pending('confirm', title, message)

    def notify(self, title, message):
        self._pending('notify', title, message)

    def review(self, request, case, data):
        return self._pending('review', '', '', case=case, data=data)

    def _answer(self, identifier, kind, answer):
        with self._lock:
            item = self._state['review'] if kind == 'review' else self._state['prompt']
            if not item or item['id'] != identifier or self._waiter is None:
                raise ValueError('This response is no longer pending.')
            waiter = self._waiter
            waiter['answer'] = answer
            self._waiter = None
            self._state['prompt'] = None
            self._state['review'] = None
            waiter['event'].set()
        return True

    @response
    def answer_review(self, identifier, approved):
        if type(approved) is not bool:
            raise ValueError('Review answer must be boolean.')
        return self._answer(identifier, 'review', approved)

    @response
    def answer_prompt(self, identifier, answer):
        if type(answer) is not bool:
            raise ValueError('Prompt answer must be boolean.')
        with self._lock:
            prompt = self._state['prompt']
            if not prompt or prompt['kind'] not in ('confirm', 'notify') or (prompt['kind'] == 'notify' and not answer):
                raise ValueError('No matching prompt.')
        return self._answer(identifier, 'prompt', answer)

    @response
    def answer_credentials(self, identifier, username, password):
        # Credentials are sent in this one reply, not published via get_state.
        with self._lock:
            prompt = self._state['prompt']
            if not prompt or prompt['kind'] != 'credentials' or not isinstance(username, str) or not isinstance(password, str):
                raise ValueError('No sign-in request pending.')
        if not username.strip() or not password:
            raise ValueError('Both sign-in fields are required.')
        return self._answer(identifier, 'prompt', (username, password))

    @response
    def cancel_credentials(self, identifier):
        with self._lock:
            prompt = self._state['prompt']
            if not prompt or prompt['kind'] != 'credentials':
                raise ValueError('No sign-in request pending.')
        return self._answer(identifier, 'prompt', None)

    @response
    def use_case(self, case_id):
        with self._lock:
            if self._state['busy']:
                raise ValueError('Finish the current run first.')
            result = self._state['result']
            if not result or result['reason'] not in ('case_ambiguous', 'case_not_confirmed'):
                raise ValueError('No case selection is available.')
            if not isinstance(case_id, str) or sum(c['case_id'] == case_id for c in result['candidates']) != 1:
                raise ValueError('Select one listed case.')
            self._state['form']['cms_case_id'] = case_id
            return deepcopy(self._state['form'])

    @response
    def start(self, form):
        from run import request_from_form, load_contract
        if not isinstance(form, dict):
            raise ValueError('Supply a form.')
        request = request_from_form(form, load_contract())
        with self._lock:
            if self._state['busy']:
                raise ValueError('A registration is already running.')
            if self._live:
                missing = [name for name in ('FCM_CMS_DB_CONNECTION', 'FCM_CMS_REFERENCE_DIR') if not os.environ.get(name, '').strip()]
                if missing:
                    # Names only: never include environment values in state.
                    self._state['error'] = 'Missing setting: ' + ', '.join(missing)
                    return False
            self._state.update(status='running', busy=True, stage='START', elapsed=0,
                               form={k: form.get(k, default) for k, default in DEFAULT_FORM.items()},
                               result=None, review=None, prompt=None, steps=[], error='')
            self._generation += 1
            generation = self._generation
            self._started = time.monotonic()
            self._thread = threading.Thread(target=self._run, args=(request, generation), daemon=True)
        self._thread.start()  # Never start a worker while holding the state lock.
        return True

    def _stage(self, stage):
        with self._lock:
            self._state['stage'] = stage

    def _step(self, step):
        with self._lock:
            self._state['steps'].append(_redact({'step': step.step, 'status': step.status, 'detail': step.detail}, self._secrets))

    def _run(self, request, generation):
        session = None
        com = None
        secrets = []
        try:
            from run import load_contract, load_core, load_live
            contract = load_contract()
            if self._live and self._session_factory is None:
                import pythoncom
                pythoncom.CoInitialize()
                com = pythoncom
            if self._live:
                answer = self._pending('credentials', 'CMS sign-in', 'Enter CMS username and password for this run only.')
                if answer is None:
                    result = {'outcome': 'cancelled', 'reason': 'operator_cancelled', 'stage': 'START',
                              'stages': [], 'case_id': '', 'candidates': [], 'steps': [],
                              'registration': None, 'cem': None, 'problems': [], 'error': None}
                    with self._lock:
                        self._state.update(status='cancelled', result=result)
                    return
                user, password = answer
                settings = {'cms_db_connection': os.environ['FCM_CMS_DB_CONNECTION'],
                            'reference_dir': os.environ['FCM_CMS_REFERENCE_DIR'],
                            'cms_user': user, 'cms_password': password,
                            'notify': self.notify, 'confirm': self.confirm}
                secrets = [password, user, settings['cms_db_connection']]
                with self._lock:
                    self._secrets = list(secrets)
                session = (self._session_factory or load_live)(settings)
                # Drop the worker's reference to settings after opening the session.
                del settings, user, password, answer
                stages = replace(session.stages, review=self.review)
            else:
                stages = (self._stages_factory(contract) if self._stages_factory else _offline_stages(contract))
                stages = replace(stages, review=self.review)
            flow = self._flow or load_core().run_flow
            result = flow(request, stages=stages, on_stage=self._stage, on_step=self._step)
            result = _redact(result, secrets)
            with self._lock:
                published = deepcopy(self._state['steps'])
                returned = deepcopy(result['steps'])
                self._state.update(status=result['outcome'], result=result,
                                   steps=returned if returned else published)
        except (Exception, SystemExit):
            # Do not expose arbitrary exception text from live plugins.
            with self._lock:
                self._state.update(status='failed', result={
                    'outcome': 'failed', 'reason': 'desktop_worker_failed', 'stage': self._state['stage'],
                    'stages': [], 'case_id': '', 'candidates': [], 'steps': [],
                    'registration': None, 'cem': None, 'problems': [], 'error': None})
        finally:
            if session is not None:
                try:
                    session.close()
                except (Exception, SystemExit):
                    with self._lock:
                        self._state['error'] = 'Live session cleanup failed; inspect the portal manually.'
            if com is not None:
                try:
                    com.CoUninitialize()
                except (Exception, SystemExit):
                    with self._lock:
                        self._state['error'] = 'COM cleanup failed; inspect the desktop manually.'
            with self._lock:
                if self._generation == generation:
                    self._state.update(busy=False, elapsed=round(time.monotonic() - self._started, 1))
                    self._secrets = []


def _redact(value, secrets):
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, '[redacted]')
        return value
    if isinstance(value, dict):
        return {k: _redact(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v, secrets) for v in value]
    return value


def _offline_stages(contract):
    """Desktop preview fixture; actual live work requires --live."""
    case = contract.CaseCandidate('SYN-CASE-1', '2026-01-02', 'Medical')
    def setup(request, selected, data, on_step):
        step = contract.StepResult('synthetic_setup', 'done', 'Offline only')
        on_step(step)
        return [step]
    return contract.RegistrationStages(
        lambda request: [replace(case, referral_type=request.referral_type)],
        lambda request, selected: {'cem_employer_request': False, 'synthetic': 'Testy Example'},
        lambda *_: True, setup,
        lambda request, selected, cem: {'option': '10' if cem else '3', 'case_id_entered': True, 'readback': selected.case_id})
