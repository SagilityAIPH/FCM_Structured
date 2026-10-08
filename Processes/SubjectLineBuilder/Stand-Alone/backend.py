"""Session-only form and worker bridge for manual Subject Line Builder."""
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Deploy-Ready'))
from manual_flow import defaults, schema, validate, run_manual, Stopped
from excel_input import create_template, read_workbook


class ManualAPI:
    def __init__(self, adapter_factory=None):
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._resume = threading.Event()
        self._thread = None
        self._window = None
        self._factory = adapter_factory
        self._started = None
        self._records = []
        self._state = {'status': 'idle', 'stage': 'Enter the referral details', 'progress': 0,
                       'prompt': '', 'error': '', 'busy': False, 'elapsed': 0, 'review_id': 0}

    def initialize(self):
        return {'schema': schema(), 'defaults': defaults(), 'state': self.get_state()}

    def open_excel(self):
        import webview
        with self._lock:
            if self._state['busy']:
                return {'ok': False, 'error': 'Stop the current run before importing.'}
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False,
                                               file_types=('Excel workbook (*.xlsx)',))
        if not paths:
            return {'ok': True, 'cancelled': True}
        return self._load_excel(paths[0])

    def _load_excel(self, path):
        try:
            records = read_workbook(path)
            with self._lock:
                if self._state['busy']:
                    raise ValueError('Stop the current run before importing.')
                self._records = records
            return {'ok': True, 'filename': Path(path).name,
                    'rows': [{'row': r['row'], 'label': r['label']} for r in records]}
        except Exception as error:
            return {'ok': False, 'error': str(error)}

    def select_excel_row(self, row):
        with self._lock:
            if self._state['busy']:
                return {'ok': False, 'error': 'Stop the current run before replacing fields.'}
            record = next((r for r in self._records if r['row'] == row), None)
            if record is None:
                return {'ok': False, 'error': 'Select a row from the loaded workbook.'}
            return {'ok': True, 'data': dict(record['data']), 'warning': record['warning']}

    def save_excel_template(self):
        import webview
        paths = self._window.create_file_dialog(webview.FileDialog.SAVE,
            save_filename='SubjectLineBuilder-Input.xlsx', file_types=('Excel workbook (*.xlsx)',))
        if not paths:
            return {'ok': True, 'cancelled': True}
        path = paths if isinstance(paths, str) else paths[0]
        try:
            create_template(Path(path).with_suffix('.xlsx'))
            return {'ok': True}
        except Exception as error:
            return {'ok': False, 'error': str(error)}

    def get_state(self):
        with self._lock:
            if self._state['busy'] and self._started:
                self._state['elapsed'] = round(time.monotonic() - self._started)
            return dict(self._state)

    def _update(self, **changes):
        with self._lock:
            self._state.update(changes)

    def _check(self):
        if self._cancel.is_set():
            raise Stopped('Stopped by operator. RRS changes already made remain visible.')

    def _progress(self, stage, percent):
        self._check()
        self._update(stage=stage, progress=percent, status='running', prompt='')

    def _review(self, prompt, final):
        self._check()
        with self._lock:
            self._resume.clear()
            self._state.update(status='review' if final else 'lookup', prompt=prompt,
                               review_id=self._state['review_id'] + 1)
        while not self._resume.wait(.2):
            self._check()
        self._check()
        self._update(status='running', prompt='')

    def start(self, payload):
        try:
            data = validate(payload)
        except ValueError as error:
            return {'ok': False, 'error': str(error)}
        with self._lock:
            if self._state['busy']:
                return {'ok': False, 'error': 'An operation is already active.'}
            self._cancel.clear()
            self._resume.clear()
            self._started = time.monotonic()
            self._state.update(status='running', busy=True, stage='Connecting to RRS', error='', prompt='', progress=0)
            self._thread = threading.Thread(target=self._run, args=(data,), daemon=True)
            self._thread.start()
        return {'ok': True}

    def _run(self, data):
        com = None
        try:
            if self._factory is None:
                import pythoncom
                com = pythoncom
                com.CoInitialize()
                from rrs_ui import RRSAdapter
                adapter = RRSAdapter(self._check)
            else:
                adapter = self._factory(self._check)
            run_manual(data, adapter, self._progress, self._review, self._check)
            self._update(status='completed')
        except Stopped as error:
            self._update(status='stopped', stage=str(error), prompt='')
        except Exception as error:
            self._update(status='failed', stage='Action stopped', error=str(error), prompt='')
        finally:
            if com:
                com.CoUninitialize()
            self._update(busy=False)

    def proceed(self, review_id, create=False):
        with self._lock:
            expected = 'review' if create else 'lookup'
            if self._state['status'] != expected or self._state['review_id'] != review_id or self._cancel.is_set():
                return {'ok': False, 'error': 'This review is no longer active.'}
            self._state['status'] = 'running'
            self._resume.set()
        return {'ok': True}

    def stop(self):
        self._cancel.set()
        self._resume.set()
        return {'ok': True}
