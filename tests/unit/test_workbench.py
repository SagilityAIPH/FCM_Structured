from contextlib import nullcontext
import json
import sys
import threading
from types import SimpleNamespace

import fitz
from openpyxl import load_workbook
import pytest

from AI.workbench.backend import WorkbenchAPI
from AI.workbench import backend
from AI import address_enrichment
from AI.daily_output import read_record
from tests.unit.test_referral_schema import complete_payload


@pytest.fixture
def workbench(tmp_path, monkeypatch):
    api = WorkbenchAPI(tmp_path / 'output')
    api._key = 'test-secret-not-real'
    monkeypatch.setattr(backend.core, 'create_bedrock_client', lambda *args: nullcontext(None))
    monkeypatch.setattr(address_enrichment, 'census_lookup', lambda query: [])
    path = tmp_path / 'synthetic.pdf'
    with fitz.open() as pdf:
        pdf.new_page().insert_text((40, 60), 'Synthetic referral for offline bridge testing.')
        pdf.save(path)
    identifier = api._import_paths([path])[0]
    return api, identifier, path


def extract(monkeypatch, data):
    result, fields = backend.core.force_exact_field_output(json.dumps(data))
    monkeypatch.setattr(backend.core, 'run_reasoning', lambda *args: (result, fields, json.dumps(data), .1))


def finish(api):
    api._thread.join(10)
    assert not api._thread.is_alive()
    return api.get_state()['value']


def test_import_auto_extracts_enriches_and_saves_daily(workbench, monkeypatch):
    api, identifier, path = workbench
    data = complete_payload()
    data.update({'Address-line-1': '123 Summer St', 'City': 'Worcester', 'State': 'Not found', 'Zip': 'Not found'})
    extract(monkeypatch, data)
    monkeypatch.setattr(address_enrichment, 'census_lookup', lambda query: [{
        'matchedAddress': '123 SUMMER ST, WORCESTER, MA, 01608',
        'addressComponents': {'city': 'WORCESTER', 'state': 'MA', 'zip': '01608'},
    }])
    api._window = type('Window', (), {'create_file_dialog': lambda *_args, **_kw: (str(path),)})()
    monkeypatch.setitem(sys.modules, 'webview', SimpleNamespace(FileDialog=SimpleNamespace(OPEN=1)))
    assert api.choose_documents()['value'] == [identifier]  # existing imports aren't duplicated
    state = finish(api)
    assert len(state['documents']) == 1
    doc = api._documents[identifier]
    assert doc['status'] == 'Completed'
    assert doc['fields']['State'] == 'MA'
    assert doc['fields']['Zip'] == '01608'
    saved, checked = read_record(doc['workbook'], doc['record_id'])
    assert checked['status'] == 'Passed'
    assert saved.address_review[0]['applied_automatically']
    assert 'test-secret' not in json.dumps(state)
    assert api.render_page(identifier, 0, .5)['value'].startswith('data:image/png;base64,')
    assert not api.render_page(identifier, 7, .5)['ok']


def test_conflicting_address_is_not_applied_and_failed_result_is_saved(workbench, monkeypatch):
    api, identifier, _ = workbench
    data = complete_payload()
    data.update({'Address-line-1': '123 Summer St', 'City': 'Worcester', 'State': 'MA', 'Zip': 'Not found'})
    extract(monkeypatch, data)
    monkeypatch.setattr(address_enrichment, 'census_lookup', lambda query: [{
        'matchedAddress': '123 OTHER ST, WORCESTER, MA, 01608',
        'addressComponents': {'city': 'WORCESTER', 'state': 'MA', 'zip': '01608'},
    }])
    assert api.start_processing([identifier])['ok']
    finish(api)
    doc = api._documents[identifier]
    assert doc['status'] == 'Needs Review'
    saved, checked = read_record(doc['workbook'], doc['record_id'])
    assert saved['Zip'] == 'Not found'
    assert checked['status'] == 'Failed'
    assert not getattr(saved, 'address_review', [])


def test_edit_preserves_provider_records_revalidates_and_updates_same_excel_row(workbench, monkeypatch):
    api, identifier, _ = workbench
    data = complete_payload()
    data['Claim ID'] = 'Not found'
    extract(monkeypatch, data)
    api.start_processing([identifier]); finish(api)
    doc = api._documents[identifier]
    record_id = doc['record_id']
    revision = doc['revision']
    edits = [{'key': 'Claim ID', 'provider_index': None, 'value': '=literal-claim'},
             {'key': 'Provider City', 'provider_index': 0, 'value': 'Worcester'}]
    assert api.save_fields(identifier, edits, revision)['ok']
    finish(api)
    assert doc['record_id'] == record_id
    assert doc['status'] == 'Completed'
    saved, _ = read_record(doc['workbook'], record_id)
    assert saved['Claim ID'] == '=literal-claim'
    assert saved.providers[0]['Provider City'] == 'Worcester'
    book = load_workbook(doc['workbook'])
    assert book['Referrals'].max_row == 2
    book.close()
    assert not api.save_fields(identifier, edits, revision)['ok']
    assert api.get_document(identifier)['value']['groups'][0]['fields'][0]['confidence'] is None


def test_token_failure_does_not_reuse_old_success(workbench, monkeypatch):
    api, identifier, _ = workbench
    extract(monkeypatch, complete_payload())
    api.start_processing([identifier]); finish(api)
    def fail(*args):
        raise RuntimeError('Token budget exhausted test-secret-not-real')
    monkeypatch.setattr(backend.core, 'run_reasoning', fail)
    api.start_processing([identifier]); finish(api)
    result = api.get_document(identifier)['value']
    assert result['status'] == 'Failed'
    assert result['groups'] == [] and result['next_step'] is None
    assert result['error'] == 'Token budget exhausted [redacted]'


def test_settings_unblock_waiting_imports_and_busy_rejects_edits(workbench, monkeypatch):
    api, identifier, _ = workbench
    extract(monkeypatch, complete_payload())
    gate = threading.Event()
    run = backend.core.run_reasoning
    monkeypatch.setattr(backend.core, 'run_reasoning', lambda *args: (gate.wait(5), run(*args))[1])
    api._key = ''
    api._queue_pending()
    assert not api._busy
    settings = api.get_state()['value']['settings']
    assert settings['max_tokens'] == 16384
    assert api.save_settings(settings, 'test-secret-not-real')['ok']
    assert api._busy
    assert not api.save_settings(settings, '')['ok']
    assert not api.start_processing([identifier])['ok']
    gate.set(); finish(api)


def test_workbook_save_error_is_visible_and_retry_is_idempotent(workbench, monkeypatch):
    api, identifier, _ = workbench
    extract(monkeypatch, complete_payload())
    real_save = backend.save_daily_output
    def locked(*args, **kwargs):
        raise PermissionError('Workbook open in Excel')
    monkeypatch.setattr(backend, 'save_daily_output', locked)
    api.start_processing([identifier]); finish(api)
    assert api.get_document(identifier)['value']['save_error']
    monkeypatch.setattr(backend, 'save_daily_output', real_save)
    assert api.retry_save(identifier)['ok']
    assert api.retry_save(identifier)['ok']
    doc = api._documents[identifier]
    assert not doc['save_error']
    book = load_workbook(doc['workbook'])
    assert book['Referrals'].max_row == 2
    book.close()


def test_empty_provider_can_be_completed_through_form(workbench, monkeypatch):
    api, identifier, _ = workbench
    data = complete_payload()
    provider = data['Provider Information'][0]
    data['Provider Information'] = []
    extract(monkeypatch, data)
    api.start_processing([identifier]); finish(api)
    doc = api.get_document(identifier)['value']
    group = next(g for g in doc['groups'] if g['name'] == 'Provider 1')
    edits = [{'key': f['key'], 'provider_index': 0, 'value': provider[f['key']]} for f in group['fields']]
    assert api.save_fields(identifier, edits, doc['revision'])['ok']
    finish(api)
    assert api.get_document(identifier)['value']['next_step'] == 'Passed'
    assert len(api._documents[identifier]['fields'].providers) == 1


def test_editing_appointment_invalidates_previous_confirmation(workbench, monkeypatch):
    api, identifier, _ = workbench
    data = complete_payload()
    data['Provider Information'][0]['Appointment Date'] = '2020-07-04'
    extract(monkeypatch, data)
    api.start_processing([identifier]); finish(api)
    doc = api.get_document(identifier)['value']
    assert doc['validation']['confirmation_required']
    assert api.confirm_appointment(identifier, 1)['ok']
    doc = api.get_document(identifier)['value']
    assert doc['next_step'] == 'Passed'
    assert api.save_fields(identifier, [{'key': 'Appointment Date', 'provider_index': 0, 'value': '2020-07-05'}], doc['revision'])['ok']
    finish(api)
    assert api.get_document(identifier)['value']['next_step'] == 'Failed'
    assert api.get_document(identifier)['value']['validation']['confirmation_required']
