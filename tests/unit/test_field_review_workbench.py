"""Synthetic workbench edit revalidation and flag persistence."""
import json
from AI import referral_schema
from AI.workbench.backend import WorkbenchAPI


def test_save_fields_clears_edited_disagreement_rechecks_format(tmp_path, monkeypatch):
    monkeypatch.setenv('FCM_REFERRALS_DIR', str(tmp_path))
    api = WorkbenchAPI(memory_only=True)
    api._enrich = lambda fields: (fields, [])
    identifier = api._import_text('synthetic capture', 'Claimant Information\nZip: 2001-01-02\nClaim Information\nCase Manager Information')
    from tests.unit.test_referral_schema import complete_payload
    data = complete_payload()
    data['Zip'] = '12345'
    fields = referral_schema.parse_field_block(json.dumps(data), 'Claimant Information\nZip: 2001-01-02\nClaim Information\nCase Manager Information')
    assert any(flag['field'] == 'Zip' and flag['kind'] == 'disagreement' for flag in fields.review_flags)
    assert api.start_processing([identifier], prepared_fields=fields)['ok']
    before = api.get_document(identifier)['value']
    assert before['review_flags']
    assert api.save_fields(identifier, [{'key': 'Zip', 'provider_index': None, 'value': 'Bad Zip'}], before['revision'])['ok']
    api._thread.join(10)
    assert not api._thread.is_alive()
    after = api.get_document(identifier)['value']
    zip_flags = [flag for flag in after['review_flags'] if flag['field'] == 'Zip']
    assert [flag['kind'] for flag in zip_flags] == ['format']
    assert after['validation']['status'] == before['validation']['status']
    records = list(tmp_path.glob('*.json'))
    assert len(records) == 1
    record = json.loads(records[0].read_text(encoding='utf-8'))
    assert any(flag['kind'] == 'disagreement' and flag['field'] == 'Zip' for flag in record['ai_extracted']['review_flags'])
    assert [flag['kind'] for flag in record['current']['review_flags'] if flag['field'] == 'Zip'] == ['format']
    assert [save['reason'] for save in record['saves']] == ['after_extraction', 'save_changes', 'address_check']
