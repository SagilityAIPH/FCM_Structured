"""Attended, session-only pywebview bridge. No live imports until Start."""
from copy import deepcopy
from dataclasses import replace
from functools import wraps
import os
from pathlib import Path
import sys
import threading
import time
import uuid

ROOT = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[3]


class _InputError(ValueError):
    """Fixed, operator-safe input messages; never wrap external exception text."""


def _read_excel(path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from AI.cms_registration_excel import ExcelValidationError, read_workbook
    try:
        return read_workbook(path)
    except ExcelValidationError as error:
        raise _InputError(str(error)) from None


def _validate_excel_edits(values):
    from AI.cms_registration_excel import ExcelValidationError, validate_setup_edits
    try:
        return validate_setup_edits(values)
    except ExcelValidationError as error:
        raise _InputError(str(error)) from None


def _coherent_provider_edits(providers, originals):
    """Keep edited search identity and tab-readback identity in agreement."""
    for index, provider in enumerate(providers):
        original = originals[index] if index < len(originals) else {}
        name_changed = 'name' in provider and provider['name'] != original.get('name', '')
        parts_changed = any(key in provider and provider[key] != original.get(key, '')
                            for key in ('first_name', 'last_name'))
        if not name_changed and not parts_changed:
            continue  # Preserve untouched imported display names, including suffixes.
        first = provider.get('first_name', original.get('first_name', '')).strip()
        last = provider.get('last_name', original.get('last_name', '')).strip()
        if provider.get('type', original.get('type', '')) == 'facility':
            if parts_changed and (first or last):
                raise _InputError('Use the provider name for facilities, not doctor name parts.')
            provider.update(first_name='', last_name='')
        elif name_changed:
            parts_name = ' '.join(filter(None, (first, last)))
            if parts_changed and parts_name:
                if not first or not last or parts_name.casefold() != provider['name'].strip().casefold():
                    raise _InputError('Provider name and edited doctor name parts disagree. Edit one identity consistently.')
                provider.update(first_name=first, last_name=last)
            else:
                provider.update(first_name='', last_name='')
        elif parts_changed:
            if bool(first) != bool(last):
                raise _InputError('Enter both doctor name parts, or edit the provider name instead.')
            provider.update(name=' '.join(filter(None, (first, last))), first_name=first, last_name=last)
    return providers


def _load_env_files():
    """Load the same external .env files as the rest of the solution (no overrides)."""
    sys.path.insert(0, str(ROOT / 'src'))
    try:
        import fcm_intake.config  # noqa: F401  (loads .env on import)
    except Exception:
        pass


def _reference_dir():
    """FCM_CMS_REFERENCE_DIR if set, else the repo's docs/ folder (office matrix)."""
    configured = os.environ.get('FCM_CMS_REFERENCE_DIR', '').strip()
    return configured or str(ROOT / 'docs')


def response(fn):
    @wraps(fn)
    def call(*args, **kwargs):
        try:
            return {'ok': True, 'data': fn(*args, **kwargs)}
        except _InputError as error:
            return {'ok': False, 'error': str(error)}
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
    'preview_only': 'Preview stopped before CMS setup. No CMS fields were filled, no emails sent and no RRS registration submitted.',
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
        self._preset = None
        self._generation = 0
        self._input_revision = 0
        self._records = []
        self._selected = None
        self._window = None
        self._state = {'status': 'idle', 'busy': False, 'stage': '', 'elapsed': 0,
                       'form': dict(DEFAULT_FORM), 'prompt': None, 'review': None,
                       'steps': [], 'result': None, 'error': '', 'preview_only': bool(live),
                       'data_source': 'rrs', 'excel': None}

    def initialize(self):
        _load_env_files()
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from AI.cms_registration_excel import EDITABLE_SETUP_FIELDS, EDITABLE_PROVIDER_FIELDS
        # Same convention as Reopen-Check: prefill from the external .env / environment.
        credentials = {'username': os.environ.get('FCM_CMS_USERNAME', ''),
                       'password': os.environ.get('FCM_CMS_PASSWORD', '')} if self._live else {'username': '', 'password': ''}
        return {'state': self.get_state(), 'live': self._live, 'credentials': credentials,
                'setup_fields': deepcopy(EDITABLE_SETUP_FIELDS),
                'provider_fields': deepcopy(EDITABLE_PROVIDER_FIELDS)}

    def get_state(self):
        with self._lock:
            state = deepcopy(self._state)
            if state['busy'] and self._started:
                state['elapsed'] = round(time.monotonic() - self._started, 1)
            return _redact(state, self._secrets)

    def _idle(self):
        if self._state['busy']:
            raise _InputError('Finish the current run before changing its data source.')

    def _begin_import(self):
        with self._lock:
            self._idle()
            self._input_revision += 1
            return self._input_revision

    def _check_import(self, revision):
        self._idle()
        if revision != self._input_revision:
            raise _InputError('The data source changed. Open the workbook again.')

    def _load_excel(self, path, revision):
        if not isinstance(path, str) or not path.strip() or Path(path).suffix.lower() != '.xlsx':
            raise _InputError('Select an Excel .xlsx workbook.')
        with self._lock:
            self._check_import(revision)
        try:
            records = _read_excel(path)
        except _InputError:
            raise
        except (Exception, SystemExit):
            raise _InputError('Excel workbook could not be read. Use the CMS Registration template and check its values.') from None
        with self._lock:
            self._check_import(revision)
            self._records = deepcopy(records)
            self._selected = None
            self._state['excel'] = {
                'id': str(uuid.uuid4()), 'filename': Path(path).name, 'selected_row': None,
                'rows': [{'row': r['row'], 'label': r['label'], 'warning': r['warning']} for r in records],
                'data': None, 'warning': '',
            }
            if self._state['data_source'] == 'excel':
                self._state['form'] = dict(DEFAULT_FORM, referral_type='')
            self._state.update(result=None, error='')
            return deepcopy(self._state['excel'])

    @response
    def load_excel(self, path):
        return self._load_excel(path, self._begin_import())

    @response
    def open_excel(self):
        revision = self._begin_import()
        if self._window is None:
            raise _InputError('Open Excel is available in the desktop window only.')
        import webview
        enum = getattr(webview, 'FileDialog', None)
        dialog = getattr(enum, 'OPEN') if enum is not None else webview.OPEN_DIALOG
        paths = self._window.create_file_dialog(
            dialog, allow_multiple=False, file_types=('Excel workbook (*.xlsx)',))
        with self._lock:
            self._check_import(revision)
        if not paths:
            return None
        if not isinstance(paths, str):
            if len(paths) != 1:
                raise _InputError('Select one Excel .xlsx workbook.')
            paths = paths[0]
        return self._load_excel(paths, revision)

    @response
    def select_excel_row(self, row, workbook_id):
        with self._lock:
            self._idle()
            excel = self._state['excel']
            if excel is None or excel['id'] != workbook_id:
                raise _InputError('The workbook changed. Select a row from the current workbook.')
            record = next((r for r in self._records if type(row) is int and r['row'] == row), None)
            if record is None:
                raise _InputError('Select a row from the loaded workbook.')
            self._input_revision += 1
            self._selected = deepcopy(record)
            # Whole replacement prevents values from a previous row surviving.
            self._state['form'] = {k: record['form'][k] for k in DEFAULT_FORM}
            self._state['data_source'] = 'excel'
            excel.update(selected_row=row, data=deepcopy(record['data']), warning=record['warning'])
            self._state.update(result=None, error='')
            return deepcopy(self._state['form'])

    @response
    def use_rrs_data(self):
        with self._lock:
            self._idle()
            self._input_revision += 1
            self._selected = None
            self._state.update(data_source='rrs', form=dict(DEFAULT_FORM), result=None, error='')
            if self._state['excel'] is not None:
                self._state['excel'].update(selected_row=None, data=None, warning='')
            return deepcopy(self._state['form'])

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
    def start(self, form, username='', password='', preview_only=True, excel_edits=None):
        from run import request_from_form, load_contract
        if not isinstance(form, dict):
            raise ValueError('Supply a form.')
        if not isinstance(username, str) or not isinstance(password, str):
            raise ValueError('Credentials must be text.')
        if type(preview_only) is not bool:
            raise ValueError('preview_only must be boolean.')
        preview_only = self._live and preview_only
        request = request_from_form(form, load_contract())
        with self._lock:
            if self._state['busy']:
                raise ValueError('A registration is already running.')
            if excel_edits is not None and self._state['data_source'] != 'excel':
                raise _InputError('Excel edits require a loaded Excel row.')
            selected = None
            if self._state['data_source'] == 'excel':
                if self._selected is None:
                    raise _InputError('Load an Excel row before starting, or choose Use RRS data.')
                for key in ('claim_number', 'claimant_first_name', 'claimant_last_name'):
                    if str(form.get(key, '')).strip().casefold() != str(self._selected['form'][key]).strip().casefold():
                        raise _InputError('Claim or claimant differs from the loaded Excel row. Reload the correct row before starting.')
                selected = deepcopy(self._selected['data'])
                if excel_edits is not None:
                    excel = self._state['excel']
                    if (not isinstance(excel_edits, dict)
                            or set(excel_edits) != {'workbook_id', 'row', 'values'}
                            or not isinstance(excel_edits['workbook_id'], str)
                            or type(excel_edits['row']) is not int):
                        raise _InputError('Supply Excel edits with the current workbook and row.')
                    if (excel_edits['workbook_id'] != excel['id']
                            or excel_edits['row'] != self._selected['row']):
                        raise _InputError('The Excel selection changed. Reload the current row before starting.')
                    edits = _validate_excel_edits(excel_edits['values'])
                    if ('providers' in selected or 'providers' in edits) and any(
                            key in edits for key in ('xlProvider', 'provType', 'xlProviderPhone')):
                        raise _InputError('Edit the individual providers for this row, not the single-provider fields.')
                    if 'providers' in edits:
                        edits['providers'] = _coherent_provider_edits(
                            edits['providers'], selected.get('providers', []))
                    if 'apptDate' in edits:
                        edits['reviewAppointmentDate'] = edits['apptDate']
                    selected.update(edits)
                selected['registration_excel_referral_type'] = selected.get('refType', '')
                selected['refType'] = request.referral_type
                if request.cem_employer_request is not None:
                    selected['cem_employer_request'] = request.cem_employer_request
                selected['registration_data_source'] = 'Excel'
                selected['registration_excel_row'] = self._selected['row']
            if self._live:
                _load_env_files()
                missing = [name for name in ('FCM_RRS_DB_CONNECTION',)
                           if selected is None and not os.environ.get(name, '').strip()]
                if missing:
                    # Names only: never include environment values in state.
                    self._state['error'] = 'Missing setting: ' + ', '.join(missing)
                    return False
            # Held in memory only for this run; blank falls back to the sign-in prompt.
            self._preset = (username.strip(), password) if username.strip() and password else None
            self._state.update(status='running', busy=True, stage='START', elapsed=0,
                               form={k: form.get(k, default) for k, default in DEFAULT_FORM.items()},
                               result=None, review=None, prompt=None, steps=[], error='',
                               preview_only=preview_only)
            self._generation += 1
            self._input_revision += 1
            generation = self._generation
            self._started = time.monotonic()
            self._thread = threading.Thread(target=self._run, args=(request, generation, preview_only, selected), daemon=True)
        self._thread.start()  # Never start a worker while holding the state lock.
        return True

    def _stage(self, stage):
        with self._lock:
            self._state['stage'] = stage

    def _step(self, step):
        with self._lock:
            self._state['steps'].append(_redact({'step': step.step, 'status': step.status, 'detail': step.detail}, self._secrets))

    def _run(self, request, generation, preview_only, selected=None):
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
                with self._lock:
                    answer, self._preset = self._preset, None
                if answer is None:
                    answer = self._pending('credentials', 'CMS sign-in', 'Enter CMS username and password for this run only.')
                if answer is None:
                    result = {'outcome': 'cancelled', 'reason': 'operator_cancelled', 'stage': 'START',
                              'stages': [], 'case_id': '', 'candidates': [], 'steps': [],
                              'registration': None, 'cem': None, 'problems': [], 'error': None,
                              'preview_only': preview_only}
                    with self._lock:
                        self._state.update(status='cancelled', result=result)
                    return
                user, password = answer
                # Keep the adapter's historical key, but use RRS explicitly for
                # this stored-procedure lookup only, never a CMS fallback.
                settings = {'preview_only': preview_only,
                            'reference_dir': _reference_dir(),
                            'reference_fallback_dirs': [str(ROOT / 'docs'), str(ROOT / 'Processes' / 'sample')],
                            'cms_user': user, 'cms_password': password,
                            'notify': self.notify, 'confirm': self.confirm}
                if selected is None:
                    settings['cms_db_connection'] = os.environ['FCM_RRS_DB_CONNECTION']
                else:
                    settings['load_data'] = lambda request, case: deepcopy(selected)
                secrets = [password, user, settings.get('cms_db_connection', '')]
                with self._lock:
                    self._secrets = list(secrets)
                session = (self._session_factory or load_live)(settings)
                # Drop the worker's reference to settings after opening the session.
                del settings, user, password, answer
                stages = replace(session.stages, review=self.review)
            else:
                stages = (self._stages_factory(contract) if self._stages_factory else _offline_stages(contract))
                stages = replace(stages, review=self.review)
                if selected is not None:
                    stages = replace(stages, load_data=lambda request, case: deepcopy(selected))
            flow = self._flow or load_core().run_flow
            options = {'preview_only': preview_only} if self._live else {}
            result = flow(request, stages=stages, on_stage=self._stage, on_step=self._step, **options)
            result['preview_only'] = preview_only
            result = _redact(result, secrets)
            with self._lock:
                published = deepcopy(self._state['steps'])
                returned = deepcopy(result['steps'])
                self._state.update(status=result['outcome'], result=result,
                                   steps=returned if returned else published)
        except (Exception, SystemExit) as error:
            # Driver messages may contain only part of a connection string or
            # claimant data, which exact-value credential redaction cannot catch.
            message = 'Desktop worker failed; registration is not verified.'
            with self._lock:
                self._state.update(status='failed', result={
                    'outcome': 'failed', 'reason': 'desktop_worker_failed', 'stage': self._state['stage'],
                    'stages': [], 'case_id': '', 'candidates': [], 'steps': [],
                    'registration': None, 'cem': None, 'problems': [], 'preview_only': preview_only,
                    'error': {'type': type(error).__name__, 'stage': self._state['stage'], 'message': message}})
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
