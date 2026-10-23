"""Synthetic regression for the ten captured-text orderings and review metadata."""
import json
from pathlib import Path
import pytest
from AI import referral_schema as schema
from AI.field_review import format_reason, merge_form_fields, review_formats
from AI.referral_json import ReferralRecord

FIXTURES = Path(__file__).parent / 'fixtures' / 'field_orderings.json'
SCENARIOS = json.loads(FIXTURES.read_text(encoding='utf-8'))

@pytest.mark.parametrize('name', sorted(SCENARIOS))
def test_perfect_model_survives_ordering(name):
    item = SCENARIOS[name]
    fields = schema.parse_field_block(json.dumps(item['model_json']), source_text=item['synthetic_source'])
    wrong = [row['field'] for row in item['field_comparison'] if fields[row['field']] != row['correct']]
    assert not wrong, (name, wrong)
    disagreements = {flag['field'] for flag in fields.review_flags if flag['kind'] == 'disagreement'}
    if name.split('_')[0] in {'S1', 'S2'}:
        assert not disagreements, (name, disagreements)
    if name.split('_')[0] in {'S3', 'S4', 'S5', 'S8', 'S9', 'S10'}:
        assert disagreements, name

@pytest.mark.parametrize('name', ['S1', 'S2'])
def test_blank_ai_fills_well_ordered_evidence(name):
    item = SCENARIOS[name]
    model = item['model_json']
    model = {**model, **{key: 'Not found' for key in ('First Name', 'Last Name', 'Zip', 'Claim Number')}}
    fields = schema.parse_field_block(json.dumps(model), source_text=item['synthetic_source'])
    assert all(fields[key] == item['model_json'][key] for key in ('First Name', 'Last Name', 'Zip', 'Claim Number'))

@pytest.mark.parametrize('key,good,bad', [
    ('Zip','00000','2001-01-02'), ('Zip','12345-6789','1234'),
    ('Provider Zip','123456789','ABC123'),
    ('Date of Birth','2000-02-29','2001-02-29'),
    ('Date of Birth','2000-02-29','2999-01-01'),
    ('Date of Injury/Accident/Illness','2000-02-29','Feb 30, 2020'),
    ('Social Security Number','XXX-XX-1234','123-12-12'),
    ('Social Security Number','***-**-1234','XXXXXX1234'),
    ('Phone Number','(202) 555-0199 ext 2','555-0199'),
    ('Provider Phone','+1 202-555-0199','1234'),
    ('Gender','u','Other'),
])
def test_field_formats(key,good,bad):
    assert format_reason(key, good) is None
    assert format_reason(key, bad) is not None


def test_frozen_app_versions(monkeypatch):
    import sys
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    assert ReferralRecord('FinalCode')._data['app_version'] == '1.0.9'
    assert ReferralRecord('AIPDFReader')._data['app_version'] == '1.1.1'


def test_equal_malformed_evidence_is_format_only():
    from AI.referral_schema import ReferralFields
    fields = ReferralFields({'Phone Number': '555-0100'}, [])
    disagreements = merge_form_fields(fields, {'Phone Number': '555-0100'})
    flags = review_formats(fields, disagreements)
    assert disagreements == []
    assert flags == [{'field': 'Phone Number', 'provider_index': None,
                      'kind': 'format', 'reason': 'Not a valid phone number'}]


@pytest.mark.parametrize('key,ai,reader', [
    ('Phone Number', '555-0100', '555-0101'),
    ('Date of Birth', 'bad date', 'other bad date'),
])
def test_different_malformed_evidence_disagrees(key, ai, reader):
    fields = {key: ai}
    flags = merge_form_fields(fields, {key: reader})
    assert len(flags) == 1 and flags[0]['kind'] == 'disagreement'
    assert flags[0]['reader_value'] == reader
    assert fields[key] == ai


def test_merge_format_precedence_and_nonblocking(tmp_path, monkeypatch):
    fields = {'Zip': 'Not found'}
    flags = merge_form_fields(fields, {'Zip': '2001-01-02'})
    assert fields['Zip'] == 'Not found' and flags[0]['reader_value'] == '2001-01-02'
    fields['Zip'] = '12345'
    assert merge_form_fields(fields, {'Zip':'2001-01-02'}) and fields['Zip'] == '12345'
    fields['Zip'] = '2001-01-02'
    assert merge_form_fields(fields, {'Zip':'00000'}) and fields['Zip'] == '00000'
    fields['Zip'] = '1234'
    assert merge_form_fields(fields, {'Zip':'bad'}) and fields['Zip'] == '1234'
    item = SCENARIOS['S9_targeted_column_stream']
    result = schema.parse_field_block(json.dumps(item['model_json']), source_text=item['synthetic_source'])
    gate = schema.completeness(result)
    baseline = schema.completeness(schema.parse_field_block(json.dumps(item['model_json'])))
    assert gate['status'] == baseline['status']
    assert gate['missing_fields'] == baseline['missing_fields']
    monkeypatch.setenv('FCM_REFERRALS_DIR', str(tmp_path))
    record = ReferralRecord('AIPDFReader')
    target = record.save('after_extraction', ai_extracted=result, current=result)
    data = json.loads(target.read_text(encoding='utf-8'))
    assert data['schema_version'] == 2
    assert data['ai_extracted']['review_flags'] == data['current']['review_flags']
    assert data['current']['review_flags']
    previous = result.review_flags
    result['Zip'] = '00000'
    cleared = review_formats(result, previous, edited={('Zip', None)})
    assert not any(flag['field'] == 'Zip' and flag['kind'] == 'disagreement' for flag in cleared)
