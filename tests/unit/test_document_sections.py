import json

import pytest

from AI import bedrock_core as core, referral_schema as schema
from AI.daily_output import read_record, save_daily_output
from AI.document_sections import clean_special_instructions, extract_special_instructions
from tests.unit.test_referral_schema import payload


SOURCE = '''===== PAGE 2 =====
Referral Instructions
Do not include this preceding section.
Special Instructions
Assigned nurse must confirm referral instructions.
Clinical objective: We need an
Page 2 of 3

===== PAGE 3 =====
updated treatment plan based on these MRI Results.
MRI L Spine: 02/24/26 - findings at L2-L3 and L5-S1.
Additional Instructions: Both parties must receive ALL communications.
Referrer Name
Do not include the referrer or the footer.
Page 3 of 3
'''
EXPECTED = '''Assigned nurse must confirm referral instructions.
Clinical objective: We need an
updated treatment plan based on these MRI Results.
MRI L Spine: 02/24/26 - findings at L2-L3 and L5-S1.
Additional Instructions: Both parties must receive ALL communications.'''


def test_page_break_is_not_section_end():
    assert extract_special_instructions(SOURCE) == EXPECTED


@pytest.mark.parametrize('header', ['Special Instructions', 'Special Instructions:', 'SPECIAL INSTRUCTIONS:'])
@pytest.mark.parametrize('ending', ['Referrer Name', 'Referrer Name: Someone'])
def test_section_boundaries_and_windows_newlines(header, ending):
    assert extract_special_instructions(f'{header}\r\nKeep this.\r\n{ending}\r\nExclude this.') == 'Keep this.'


def test_pagination_cleanup_does_not_delete_clinical_numbers_or_sentences():
    assert clean_special_instructions('Read Page 2 of 3 for details.\nL2-L3\nPage 2 / 3\n04/02/26') == (
        'Read Page 2 of 3 for details.\nL2-L3\n04/02/26')


def test_mid_sentence_reference_to_referrer_name_is_not_a_boundary():
    text = 'Ask about the referrer name during the call.\nContinue here.'
    assert extract_special_instructions('Special Instructions:\n' + text) == text


def test_no_heading_keeps_model_text_but_cleans_pagination():
    data = payload()
    data['Special Instructions'] = 'First line\nPage 1 of 2\nSecond line\nReferrer Name: Someone'
    fields = schema.parse_field_block(json.dumps(data), source_text='No recognized section')
    assert fields['Special Instructions'] == 'First line\nSecond line'
    assert extract_special_instructions('Please read Special Instructions later.') is None


@pytest.mark.parametrize('model_value', ['Not found', 'Assigned nurse must confirm referral instructions.'])
def test_source_restores_missing_or_truncated_ai_narrative(model_value, tmp_path):
    data = payload()
    data['Special Instructions'] = model_value
    result, fields, raw, _ = core.run_reasoning(None, 'test', SOURCE, llm_call=lambda **kwargs: json.dumps(data))
    assert fields['Special Instructions'] == EXPECTED
    assert EXPECTED in result
    assert json.loads(raw)['Special Instructions'] == model_value
    assert schema.export_payload(fields)['Other Information']['Special Instructions'] == EXPECTED
    table = core.fields_to_table_df(fields)
    assert table[table['Field'] == 'Special Instructions'].iloc[0]['Value'] == EXPECTED
    path, record_id = save_daily_output(fields, 'regression.pdf', directory=tmp_path)
    loaded, _ = read_record(path, record_id)
    assert loaded['Special Instructions'] == EXPECTED


def test_complete_validation_source_wins_over_shorter_prompt_document():
    data = payload()
    _, fields, _, _ = core.run_reasoning(None, 'test', 'Short document excerpt', SOURCE,
                                       llm_call=lambda **kwargs: json.dumps(data))
    assert fields['Special Instructions'] == EXPECTED


def test_blank_section_does_not_accept_invented_model_text():
    data = payload()
    data['Special Instructions'] = 'Unsupported model narrative'
    fields = schema.parse_field_block(json.dumps(data), 'Special Instructions:\nReferrer Name: Someone')
    assert fields['Special Instructions'] == 'Not found'
