"""Session-only pywebview bridge. Live automation runs on a COM worker."""
from copy import deepcopy
from contextlib import redirect_stdout
from functools import wraps
import importlib.util
from io import StringIO
from pathlib import Path
import sys
import threading
import time
import uuid

HERE = (Path(sys._MEIPASS) / 'Processes/Unity/Stand-Alone'
        if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent)
sys.path.insert(0, str(HERE))
from unity_model import defaults, schema, validate, warnings, to_controller, adapter
from unity_excel import create_template, read_workbook
from AI.referral_attachments import referral_document
from AI.unity_errors import UnityCustomerFieldsError, UnityEmployerFieldsError, UnityFlagError


def _runner():
    spec = importlib.util.spec_from_file_location('_unity_desktop_runner', HERE / 'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def response(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return {'ok': True, 'data': function(*args, **kwargs)}
        except (Exception, SystemExit) as error:
            return {'ok': False, 'error': f'{type(error).__name__}: {error}'}
    return call


def live_callbacks(attachment_path=None, *, confirm_unity_login=None):
    """Lazy defaults: bypass legacy.main, which swallows automation failures."""
    runner = _runner()
    sys.path.insert(0, str(runner.ROOT))
    sys.path.insert(0, str(runner.ROOT / 'src'))
    from fcm_intake.config import ATTACHMENT_FOLDER, UNITY_SCRIPT
    from fcm_intake.legacy_loader import load_module_from_path
    def portal(customer, claimant, data):
        if attachment_path is not None:
            referral_document(attachment_path)
        unity = load_module_from_path('_desktop_legacy_unity', UNITY_SCRIPT)
        driver = unity.create_driver(detach=True)
        preserve_browser = False
        try:
            unity.login(driver)
            if attachment_path is None:
                checked_validate(unity, driver, customer, claimant, data)
            else:
                checked_validate(unity, driver, customer, claimant, data, attachment_path=attachment_path)
        except (UnityFlagError, UnityCustomerFieldsError, UnityEmployerFieldsError) as error:
            preserve_browser = True
            error.browser_left_open = True
            # Detach keeps the browser alive even when the worker/service is collected.
            try:
                driver.service.stop()
            except Exception:
                error.service_release_failed = True
            try:
                driver.command_executor.close()
            except Exception:
                error.service_release_failed = True
            raise
        finally:
            if not preserve_browser:
                driver.quit()
    return {'list_attachments': (lambda: [referral_document(attachment_path)]) if attachment_path is not None
            else lambda: sorted(p for p in Path(ATTACHMENT_FOLDER).glob('*') if p.is_file()),
            'run_unity': portal,
            'record_assignment': lambda name, claim: runner._record_live(runner.ROOT, name, claim),
            'complete_assignment': (lambda claim: runner._complete_live(runner.ROOT, claim))
            if confirm_unity_login is None else
            (lambda claim: runner._complete_live(runner.ROOT, claim, confirm_unity_login=confirm_unity_login))}


def checked_validate(unity, driver, customer, claimant, data, *, attachment_path=None):
    """The legacy stage also swallows its outer exception. Recognize its marker.

    Capture only during the single portal worker call; never persist legacy
    stdout. Inner handlers that silently continue remain a live limitation.
    """
    captured = StringIO()
    with redirect_stdout(captured):
        if attachment_path is None:
            unity.validate_and_complete_task(driver, customer, claimant, data)
        else:
            unity.validate_and_complete_task(driver, customer, claimant, data,
                                             attachment_path=str(referral_document(attachment_path)))
    errors = [line for line in captured.getvalue().splitlines() if 'error occurred:' in line.lower()]
    if errors:
        raise RuntimeError('Legacy Unity reported failure: ' + errors[-1])


class UnityAPI:
    def __init__(self, callbacks_factory=None):
        self._lock = threading.RLock()
        self._factory = callbacks_factory
        self._window = None
        self._thread = None
        self._waiter = None
        self._records = []
        self._attachment_path = None
        self._state = {'status': 'idle', 'busy': False, 'stage': '', 'elapsed': 0,
                       'prompt': None, 'result': None, 'error': '', 'warnings': [],
                       'attachment': {'source': 'rrs', 'filename': ''}}
        self._started = None

    def _idle(self):
        if self._state['busy']:
            raise ValueError('An operation is already active.')

    def initialize(self):
        return {'schema': schema(), 'defaults': defaults(), 'state': self.get_state(),
                'jurisdictions': ['', *adapter.STATE_NAMES]}

    def get_state(self):
        with self._lock:
            state = deepcopy(self._state)
            if self._started and state['busy']:
                state['elapsed'] = round(time.monotonic() - self._started, 1)
            return state

    @response
    def validate_fields(self, payload, stage='all', jurisdiction=''):
        data = validate(payload, stage)
        if jurisdiction and jurisdiction not in adapter.STATE_NAMES:
            raise ValueError('Choose a valid claim jurisdiction.')
        derived = to_controller(data, claim_jurisdiction=jurisdiction)
        return {'fields': data, 'warnings': warnings(data, jurisdiction),
                'derived': {k: derived[k] for k in ('claimStateAbbr', 'claimStateFull', 'refSource',
                                                   'correctZipCode', 'ServiceType', 'refType', 'CaseObj', 'serviceType')}}

    @response
    def load_excel(self, path):
        with self._lock:
            self._idle()
        records = read_workbook(path)
        with self._lock:
            self._idle()
            self._records = records
        return {'filename': Path(path).name, 'rows': [{k: r[k] for k in ('row', 'label', 'warning')} for r in records]}

    @response
    def select_excel_row(self, row):
        with self._lock:
            self._idle()
            record = next((r for r in self._records if r['row'] == row), None)
            if record is None:
                raise ValueError('Select a row from the loaded workbook.')
            return deepcopy(record)

    @response
    def generate_workbook(self, path):
        with self._lock:
            self._idle()
        return create_template(Path(path).with_suffix('.xlsx'))

    def _dialog(self, kind):
        import webview
        enum = getattr(webview, 'FileDialog', None)
        return getattr(enum, kind) if enum else getattr(webview, kind + '_DIALOG')

    def open_excel(self):
        with self._lock:
            if self._state['busy']:
                return {'ok': False, 'error': 'An operation is already active.'}
        paths = self._window.create_file_dialog(self._dialog('OPEN'), allow_multiple=False,
                                               file_types=('Excel workbook (*.xlsx)',))
        return self.load_excel(paths if isinstance(paths, str) else paths[0]) if paths else {'ok': True, 'data': None}

    def save_excel_template(self):
        paths = self._window.create_file_dialog(self._dialog('SAVE'), save_filename='Unity-Input.xlsx',
                                               file_types=('Excel workbook (*.xlsx)',))
        return self.generate_workbook(paths if isinstance(paths, str) else paths[0]) if paths else {'ok': True, 'data': None}

    @response
    def choose_referral_document(self):
        with self._lock:
            self._idle()
        paths = self._window.create_file_dialog(self._dialog('OPEN'), allow_multiple=False,
                                               file_types=('Referral document (*.pdf;*.msg;*.eml;*.PDF;*.MSG;*.EML)',))
        with self._lock:
            self._idle()
            if not paths:
                return None
            if not isinstance(paths, str) and len(paths) != 1:
                raise ValueError('Choose exactly one referral document file.')
            selected = referral_document(paths if isinstance(paths, str) else paths[0])
            self._attachment_path = selected
            self._state['attachment'] = {'source': 'local', 'filename': selected.name}
            return deepcopy(self._state['attachment'])

    @response
    def use_rrs_export_folder(self):
        with self._lock:
            self._idle()
            self._attachment_path = None
            self._state['attachment'] = {'source': 'rrs', 'filename': ''}
            return deepcopy(self._state['attachment'])

    def _prompt(self, kind, title, message):
        waiter = {'event': threading.Event(), 'answer': False}
        prompt = {'id': str(uuid.uuid4()), 'kind': kind, 'title': str(title), 'message': str(message)}
        with self._lock:
            if self._waiter:
                raise RuntimeError('Another prompt is pending.')
            self._waiter = waiter
            self._state['prompt'] = prompt
        try:
            waiter['event'].wait()  # Never hold the lock while waiting.
            return waiter['answer']
        finally:
            with self._lock:
                if self._waiter is waiter:
                    self._waiter = None
                    self._state['prompt'] = None

    def confirm(self, title, message):
        return self._prompt('confirm', title, message)

    def notify(self, title, message):
        self._prompt('notify', title, message)

    @response
    def answer_prompt(self, identifier, answer):
        with self._lock:
            prompt = self._state['prompt']
            if not prompt or prompt['id'] != identifier:
                raise ValueError('This prompt is no longer pending.')
            if type(answer) is not bool or (prompt['kind'] == 'notify' and not answer):
                raise ValueError('Use a boolean answer; notifications need acknowledgement.')
            waiter = self._waiter
            waiter['answer'] = answer
            self._waiter = None
            self._state['prompt'] = None
            waiter['event'].set()
        return True

    @response
    def start(self, payload, stage='all', record_attempt_on_failure=True, jurisdiction=''):
        checked = self.validate_fields(payload, stage, jurisdiction)
        if not checked['ok']:
            raise ValueError(checked['error'])
        if type(record_attempt_on_failure) is not bool:
            raise ValueError('Tracking preference must be boolean.')
        data = to_controller(checked['data']['fields'], claim_jurisdiction=jurisdiction)
        with self._lock:
            self._idle()
            if self._factory is None and stage != 'assign':
                _runner()._preflight_tracking()
            attachment_path = self._attachment_path if stage != 'assign' else None
            if attachment_path is not None:
                attachment_path = referral_document(attachment_path)
            self._started = time.monotonic()
            self._state.update(status='running', busy=True, stage=stage, result=None, prompt=None,
                               error='', elapsed=0, warnings=checked['data']['warnings'])
            self._thread = threading.Thread(target=self._run, args=(data, stage, record_attempt_on_failure, attachment_path), daemon=True)
            self._thread.start()
        return True

    def _run(self, data, stage, tracking, attachment_path):
        com = None
        try:
            if self._factory is None:
                import pythoncom
                com = pythoncom
                com.CoInitialize()
            calls = (self._factory() if self._factory else
                     live_callbacks(attachment_path, confirm_unity_login=self.confirm))
            if attachment_path is not None:
                calls = {**calls, 'list_attachments': lambda: [referral_document(attachment_path)]}
            result = _runner().load_core().run_flow(data, stage=stage, notify=self.notify,
                       confirm=self.confirm, record_attempt_on_failure=tracking, **calls)
            with self._lock:
                self._state.update(status=result['status'], result=result)
        except (Exception, SystemExit) as error:
            result = {'status': 'failed', 'reason': 'desktop_worker_failed', 'claimantFull': '',
                      'attachment': '', 'steps': [], 'error': {'type': type(error).__name__, 'message': str(error)}}
            with self._lock:
                self._state.update(status='failed', result=result, error=str(error))
        finally:
            if com:
                com.CoUninitialize()
            with self._lock:
                self._state.update(busy=False, elapsed=round(time.monotonic() - self._started, 1))
