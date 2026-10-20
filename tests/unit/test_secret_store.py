"""Synthetic-only credential persistence and bridge isolation tests."""
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from AI.workbench.backend import WorkbenchAPI
from AI.workbench.secret_store import SecretStore
from AI.workbench import backend


@pytest.fixture
def store(tmp_path):
    return SecretStore(tmp_path / 'local-app-data' / 'credentials')


def test_dpapi_roundtrip_for_both_names_and_absence_from_repo(store):
    repo = Path(__file__).resolve().parents[2]
    for name in ('bedrock', 'cms'):
        fake = f'obviously-fake-{name}-only'
        assert store.load(name) is None
        store.save(name, fake)
        assert store.load(name) == fake
        blob = store._path(name)
        assert repo not in blob.resolve().parents
        assert fake.encode() not in blob.read_bytes()
        store.forget(name)
        assert store.load(name) is None
        store.forget(name)


def test_default_location_is_local_app_data_not_repository(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'profile-local'))
    default = SecretStore()
    repo = Path(__file__).resolve().parents[2]
    assert default._path('bedrock').is_relative_to(tmp_path / 'profile-local')
    assert repo not in default._path('bedrock').resolve().parents
    fake = 'obviously-fake-default-location-only'
    default.save('bedrock', fake)
    assert fake.encode() not in default._path('bedrock').read_bytes()
    default.forget('bedrock')


def test_dpapi_invalid_blobs_and_forget_even_when_undecryptable(store, monkeypatch):
    blob = store._path('cms')
    blob.parent.mkdir(parents=True)
    for value in (b'', b'not-a-dpapi-blob', b'\x01'):
        blob.write_bytes(value)
        assert store.load('cms') is None
    def cannot_decrypt(*args, **kwargs):
        raise OSError('raw Win32 diagnostic with obviously-fake-secret-only')
    monkeypatch.setattr(store, '_crypt', cannot_decrypt)
    assert store.load('cms') is None
    store.forget('cms')
    assert not blob.exists()
    with pytest.raises(RuntimeError) as caught:
        store.save('bedrock', 'obviously-fake-secret-only')
    assert 'raw Win32' not in str(caught.value)
    assert 'obviously-fake-secret-only' not in str(caught.value)


def test_bedrock_opt_in_startup_forget_and_bridge_redaction(store, monkeypatch):
    monkeypatch.setattr(backend, 'SecretStore', lambda: store)
    monkeypatch.setattr(backend.core, 'resolve_bedrock_api_key', lambda: '')
    api = WorkbenchAPI()
    fake = 'obviously-fake-bedrock-secret-only'
    settings = api.get_state()['value']['settings']
    model = 'obviously-fake-model-only'
    settings['model'] = model
    assert api.save_settings(settings, fake, True)['ok']
    assert json.loads(store.load('bedrock')) == {'version': 1, 'key': fake, 'model': model}
    assert fake.encode() not in store._path('bedrock').read_bytes()
    assert model.encode() not in store._path('bedrock').read_bytes()
    assert api.get_state()['value']['settings']['model'] == model
    assert fake not in json.dumps(api.save_settings(settings, fake, True))
    assert api.get_state()['value']['key_remembered'] is True
    assert fake not in json.dumps(api.get_state())
    assert fake not in json.dumps(api.save_settings(settings, '', True))
    next_session = WorkbenchAPI()
    assert next_session._key == fake
    assert next_session.get_state()['value']['settings']['model'] == model
    assert next_session.get_state()['value']['remembered_model_needs_test']
    assert fake not in json.dumps(next_session.get_state())
    assert next_session._error(RuntimeError('bad: ' + fake)) == 'bad: [redacted]'
    assert fake not in json.dumps(api.forget_credential('bedrock'))
    assert store.load('bedrock') is None
    assert WorkbenchAPI().get_state()['value']['settings']['model'] == backend.core.DEFAULT_BEDROCK_MODEL
    assert next_session.save_settings(settings, '', False)['ok']
    assert WorkbenchAPI().get_state()['value']['key_configured'] is False
    assert api.save_settings(settings, fake, True)['ok']
    assert api.save_settings(settings, '', False)['ok']
    assert not store.exists('bedrock')
    assert api.get_state()['value']['settings']['model'] == model
    assert WorkbenchAPI().get_state()['value']['settings']['model'] == backend.core.DEFAULT_BEDROCK_MODEL
    assert api.save_settings(settings, '', True)['ok']
    assert json.loads(store.load('bedrock'))['key'] == fake
    monkeypatch.setattr(backend.core, 'resolve_bedrock_api_key', lambda: 'obviously-fake-env-key-only')
    assert WorkbenchAPI()._key == 'obviously-fake-env-key-only'
    assert 'obviously-fake-env-key-only' not in json.dumps(WorkbenchAPI().get_state())


def test_legacy_key_only_blob_loads_without_rewriting(store, monkeypatch):
    monkeypatch.setattr(backend, 'SecretStore', lambda: store)
    monkeypatch.setattr(backend.core, 'resolve_bedrock_api_key', lambda: '')
    old_key = 'obviously-fake-old-key-only'
    store.save('bedrock', old_key)
    original = store._path('bedrock').read_bytes()
    api = WorkbenchAPI(memory_only=True)
    state = api.get_state()
    assert api._key == old_key
    assert state['value']['settings']['model'] == backend.core.DEFAULT_BEDROCK_MODEL
    assert state['value']['key_remembered']
    assert old_key not in json.dumps(state)
    assert store._path('bedrock').read_bytes() == original
    updated = dict(state['value']['settings'], model='obviously-fake-next-model')
    assert api.save_settings(updated, '', True)['ok']
    assert json.loads(store.load('bedrock')) == {'version': 1, 'key': old_key, 'model': updated['model']}


def test_corrupt_bedrock_blob_fails_soft_and_can_be_forgotten(store, monkeypatch):
    monkeypatch.setattr(backend, 'SecretStore', lambda: store)
    monkeypatch.setattr(backend.core, 'resolve_bedrock_api_key', lambda: '')
    blob = store._path('bedrock')
    blob.parent.mkdir(parents=True, exist_ok=True)
    for invalid in (b'', b'corrupt', b'\x01'):
        blob.write_bytes(invalid)
        api = WorkbenchAPI()
        assert api._key == ''
        assert api.get_state()['value']['settings']['model'] == backend.core.DEFAULT_BEDROCK_MODEL
    monkeypatch.setattr(store, '_crypt', lambda *_args, **_kw: (_ for _ in ()).throw(OSError('fake undecryptable')))
    assert WorkbenchAPI()._key == ''
    assert WorkbenchAPI().forget_credential('bedrock')['ok']
    assert not blob.exists()


def test_restored_model_is_checked_before_reader_and_final_code_inference(store, monkeypatch):
    monkeypatch.setattr(backend, 'SecretStore', lambda: store)
    monkeypatch.setattr(backend.core, 'resolve_bedrock_api_key', lambda: '')
    key = 'obviously-fake-check-key'
    model = 'obviously-fake-retired-model'
    store.save('bedrock', json.dumps({'version': 1, 'key': key, 'model': model}))
    api = WorkbenchAPI(memory_only=True)
    from contextlib import nullcontext
    monkeypatch.setattr(backend.core, 'create_bedrock_client', lambda *_args: nullcontext(object()))
    checked = []
    def reject(_client, selected):
        checked.append(selected)
        raise RuntimeError('rejected ' + key)
    monkeypatch.setattr(backend.core, 'test_bedrock_connection', reject)
    inference = []
    monkeypatch.setattr(backend.core, 'run_reasoning', lambda *_args, **_kw: inference.append(True))
    document = api._import_text('synthetic capture', 'Only synthetic content.')
    assert api.start_processing([document])['ok']
    api._thread.join(5)
    assert checked == [model] and not inference
    assert api.get_state()['value']['settings']['model'] == backend.core.DEFAULT_BEDROCK_MODEL
    assert api.get_state()['value']['key_configured']
    assert key not in json.dumps(api.get_state())
    assert key not in json.dumps(api.get_document(document))
    assert 'review Settings' in api.get_document(document)['value']['error']
    assert store.exists('bedrock')  # A bad model never wipes a good key.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'Final Code'))
    from finalcode import app
    second = WorkbenchAPI(memory_only=True)
    with pytest.raises(ValueError, match='review Settings'):
        app.make_extract(second)('synthetic document')
    assert checked == [model, model] and not inference
    assert second.get_state()['value']['settings']['model'] == backend.core.DEFAULT_BEDROCK_MODEL
    assert key not in json.dumps(second.get_state())
    assert key not in second._error(RuntimeError('rejected ' + key))


def test_verified_restored_model_is_used_for_reader_inference(store, monkeypatch):
    monkeypatch.setattr(backend, 'SecretStore', lambda: store)
    monkeypatch.setattr(backend.core, 'resolve_bedrock_api_key', lambda: '')
    model = 'obviously-fake-available-model'
    store.save('bedrock', json.dumps({'version': 1, 'key': 'obviously-fake-key', 'model': model}))
    api = WorkbenchAPI(memory_only=True)
    from contextlib import nullcontext
    monkeypatch.setattr(backend.core, 'create_bedrock_client', lambda *_args: nullcontext(object()))
    checked = []
    monkeypatch.setattr(backend.core, 'test_bedrock_connection', lambda _client, selected: checked.append(selected))
    called = []
    def extract(_client, selected, *_args):
        called.append(selected)
        raise RuntimeError('synthetic stop')
    monkeypatch.setattr(backend.core, 'run_reasoning', extract)
    document = api._import_text('synthetic capture', 'Only synthetic content.')
    assert api.start_processing([document])['ok']
    api._thread.join(5)
    assert checked == called == [model]
    assert api.get_state()['value']['remembered_model_needs_test'] is False


def _wait_prompt(api):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        prompt = api.get_state()['value']['pending_prompt']
        if prompt:
            return prompt
        time.sleep(.01)
    raise AssertionError('Credential prompt not published')


def test_cms_remembered_skips_prompt_and_failed_blob_prompts(store, monkeypatch):
    monkeypatch.setattr(backend, 'SecretStore', lambda: store)
    api = WorkbenchAPI(memory_only=True)
    fake = ('obviously-fake-user-only', 'obviously-fake-password-only')
    store.save('cms', json.dumps(fake))
    assert api.request_cms_credentials() == fake
    assert api.get_state()['value']['pending_prompt'] is None
    assert all(part not in json.dumps(api.get_state()) for part in fake)
    blob = store._path('cms')
    blob.write_bytes(b'corrupted')
    returned = []
    worker = threading.Thread(target=lambda: returned.append(api.request_cms_credentials()), daemon=True)
    worker.start()
    prompt = _wait_prompt(api)
    assert 'could not be used' in prompt['message']
    assert all(part not in json.dumps(api.get_state()) for part in fake)
    assert api.forget_credential('cms')['ok']
    assert not store.exists('cms')
    assert api.answer_prompt(prompt['id'], {'username': fake[0], 'password': fake[1], 'remember': False})['ok']
    worker.join(3)
    assert returned == [fake]
    assert all(part not in json.dumps(api.get_state()) for part in fake)
    assert not store.exists('cms')


def test_cms_prompt_opt_in_and_explicit_uncheck(store, monkeypatch):
    monkeypatch.setattr(backend, 'SecretStore', lambda: store)
    api = WorkbenchAPI(memory_only=True)
    fake = ('obviously-fake-user-only', 'obviously-fake-password-only')
    for remember in (True, False):
        returned = []
        worker = threading.Thread(target=lambda: returned.append(api.request_cms_credentials(retry=True)), daemon=True)
        worker.start()
        prompt = _wait_prompt(api)
        payload = {'username': fake[0], 'password': fake[1], 'remember': remember}
        assert api.answer_prompt(prompt['id'], payload) == {'ok': True, 'value': True}
        worker.join(3)
        assert returned == [fake]
        assert store.exists('cms') is remember
        assert all(part not in json.dumps(api.get_state()) for part in fake)
    assert api.forget_credential('cms')['ok']


def test_remembered_cms_rejection_prompts_once_and_clears_session(store, monkeypatch):
    monkeypatch.setattr(backend, 'SecretStore', lambda: store)
    path = Path(__file__).resolve().parents[2] / 'Final Code' / 'finalcode' / 'live_wiring.py'
    spec = importlib.util.spec_from_file_location('synthetic_cms_remember_wiring', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rejected = type('CmsAuthenticationRejected', (RuntimeError,), {})
    calls = []
    session = SimpleNamespace(set_credentials=lambda user, password: calls.append(('set', bool(user), bool(password))), CmsAuthenticationRejected=rejected)
    def run_live(data, **kwargs):
        calls.append(('search',))
        if calls.count(('search',)) == 1:
            raise rejected('obviously-fake-password-only')
        return {'status': 'completed'}
    monkeypatch.setitem(sys.modules, 'fcm_intake.cms.session', session)
    monkeypatch.setitem(sys.modules, 'fcm_intake.workflows.reopen_flow', SimpleNamespace(run_live=run_live))
    api = WorkbenchAPI(memory_only=True)
    fake = ('obviously-fake-user-only', 'obviously-fake-password-only')
    store.save('cms', json.dumps(fake))
    result = []
    worker = threading.Thread(target=lambda: result.append(module.make_cms(notify=api.notify)({'customer': 'SYNTHETIC'})), daemon=True)
    worker.start()
    prompt = _wait_prompt(api)
    assert 'could not be used' in prompt['message']
    assert not store.exists('cms')
    assert api.answer_prompt(prompt['id'], {'username': fake[0], 'password': fake[1], 'remember': False})['ok']
    worker.join(3)
    assert result == [{'status': 'completed'}]
    assert calls.count(('search',)) == 2
    assert calls[-1] == ('set', False, False)
    assert api._cms_secrets == set()
    assert all(part not in json.dumps(api.get_state()) for part in fake)
