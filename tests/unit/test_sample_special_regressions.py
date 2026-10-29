"""Synthetic regression layouts for special-instruction role evidence."""
import json

import pytest

from AI.referral_schema import (FIELD_ONLY_PROMPT, _TEMPLATE,
                                force_exact_field_output)
from AI.bedrock_core import _APPOINTMENT_SOURCE_RULE


def fields(source, **model):
    data = json.loads(json.dumps(_TEMPLATE))
    data.update(model)
    return force_exact_field_output(json.dumps(data), source)[1]


@pytest.mark.parametrize('source, expected', [
    ('Employer name or contact: Testy Example with Example Manufacturing Corporation\nPhone #: 555-010-0111', ('Testy', 'Example')),
    ('Employer name and contact: Example Transit\nPhone #: Avery Sample - avery.sample@example.com', ('Avery', 'Sample')),
    ('Employer name and contact: *please provide updates to CS & NCM only\nPhone #: n/a', ('Not found', 'Not found')),
    ('Employer name and contact: Telephonic NCM to update', ('Not found', 'Not found')),
    ('Employer name and contact: Example Transit\nPhone #: n/a', ('Not found', 'Not found')),
])
def test_employer_person_not_company_or_instructions(source, expected):
    result = fields('Special Instructions:\n' + source + '\nReferrer Name: Test Operator')
    assert (result['Employer First Name'], result['Employer Last Name']) == expected


def test_employer_instructions_cannot_override_missing_model():
    result = fields('Special Instructions:\nEmployer name and contact: Telephonic NCM to update\nReferrer Name: Test Operator',
                    **{'Special Instruction Fields': {'Employer First Name': 'Telephonic', 'Employer Last Name': 'NCM to update'}})
    assert (result['Employer First Name'], result['Employer Last Name']) == ('Not found', 'Not found')


def test_valid_model_employer_survives_company_only_line():
    result = fields('Special Instructions:\nEmployer name and contact: Example Transit\nPhone #: n/a\nReferrer Name: Test Operator',
                    **{'Employer First Name': 'Avery', 'Employer Last Name': 'Sample'})
    assert (result['Employer First Name'], result['Employer Last Name']) == ('Avery', 'Sample')


def test_model_company_split_is_cleared_without_touching_a_real_person():
    result = fields('Special Instructions:\nEmployer name and contact: Example Transit\nPhone #: n/a\nReferrer Name: Test Operator',
                    **{'Employer First Name': 'Example', 'Employer Last Name': 'Transit'})
    assert (result['Employer First Name'], result['Employer Last Name']) == ('Not found', 'Not found')


def test_anatomy_levels_not_diagnoses_and_description_intact():
    result = fields('Special Instructions:\nCompensable Part(s): T12 fracture, L4-L5 and C5 pain\nReferrer Name: Test Operator',
                    **{'Special Instruction Fields': {'Additional Diagnosis Codes': 'T12'}})
    assert result['Additional Diagnosis Codes'] == 'Not found'
    assert result['Compensable Body/Part(s)'] == 'T12 fracture, L4-L5 and C5 pain'


def test_salvo_anatomical_level_remains_body_part_not_code():
    result = fields('Special Instructions:\nCompensable Part(s): T12 fracture, Whiplash\nReferrer Name: Test Operator',
                    **{'Special Instruction Fields': {'Compensable Body/Part(s)': 'T12 fracture, Whiplash',
                                                     'Additional Diagnosis Codes': 'T12'}})
    assert result['Compensable Body/Part(s)'] == 'T12 fracture, Whiplash'
    assert result['Additional Diagnosis Codes'] == 'Not found'


@pytest.mark.parametrize('body', ['L4-L5 disc', 'C5-C6'])
def test_anatomical_levels_in_body_part_prose_are_not_codes(body):
    result = fields(f'Special Instructions:\nCompensable Part(s): {body}\nReferrer Name: Test Operator',
                    **{'Special Instruction Fields': {'Compensable Body/Part(s)': body}})
    assert result['Compensable Body/Part(s)'] == body
    assert result['Additional Diagnosis Codes'] == 'Not found'


def test_bare_level_in_combined_heading_is_not_a_diagnosis():
    result = fields('Special Instructions:\nCOMPENSABLE BODY PART(S) & DIAGNOSIS: T12 fracture\n'
                    'Referrer Name: Test Operator')
    assert result['Compensable Body/Part(s)'] == 'T12 fracture'
    assert result['Additional Diagnosis Codes'] == 'Not found'
    assert result['Diagnosis Code'] == 'Not found'


@pytest.mark.parametrize('label, code', [('Diagnosis', 'R52'), ('ICD-10', 'M54')])
def test_documented_three_character_icd_remains_additional(label, code):
    source = ('Special Instructions:\nCompensable Part(s): lower back\n'
              f'{label}: {code}\nReferrer Name: Test Operator')
    result = fields(source, **{'Diagnosis Code': 'S39.012A',
                                'Special Instruction Fields': {'Compensable Body/Part(s)': 'lower back',
                                                               'Additional Diagnosis Codes': code}})
    assert result['Additional Diagnosis Codes'] == code


def test_bare_model_code_is_not_inferred_from_dotted_source_prefix():
    result = fields('Special Instructions:\nCompensable Part(s): wrist\nDiagnosis: R52.1\n'
                    'Referrer Name: Test Operator',
                    **{'Diagnosis Code': 'S39.012A',
                       'Special Instruction Fields': {'Additional Diagnosis Codes': 'R52'}})
    assert result['Additional Diagnosis Codes'] == 'R52.1'


def test_diagnosis_codes_line_recovers_dotted_codes():
    source = ('Special Instructions:\nCompensable Part(s): left wrist\n'
              'Diagnosis codes: S62.101A, M25.531\nReferrer Name: Test Operator')
    result = fields(source, **{'Diagnosis Code': 'R52',
                               'Special Instruction Fields': {'Compensable Body/Part(s)': 'left wrist'}})
    assert result['Additional Diagnosis Codes'] == 'S62.101A; M25.531'


def test_dotted_icd_in_body_part_is_removed_but_bare_level_is_retained():
    source = ('Special Instructions:\nCompensable Part(s): T12 fracture, left wrist (S62.101A)\n'
              'Referrer Name: Test Operator')
    result = fields(source, **{'Diagnosis Code': 'R52',
                               'Special Instruction Fields': {'Compensable Body/Part(s)': 'T12 fracture, left wrist (S62.101A)'}})
    assert result['Compensable Body/Part(s)'] == 'T12 fracture, left wrist'
    assert result['Additional Diagnosis Codes'] == 'S62.101A'


def test_body_part_dotted_code_stripped_without_diagnosis_label():
    source = ('Special Instructions:\nCompensable Part(s): left wrist (S62.101A)\n'
              'Referrer Name: Test Operator')
    result = fields(source, **{'Special Instruction Fields': {'Compensable Body/Part(s)': 'left wrist (S62.101A)'}})
    assert result['Compensable Body/Part(s)'] == 'left wrist'
    assert result['Diagnosis Code'] == 'S62.101A'
    assert result['Additional Diagnosis Codes'] == 'Not found'


def test_explicit_icd_diagnoses_are_captured():
    result = fields('Special Instructions:\nCOMPENSABLE BODY PART(S) & DIAGNOSIS: S39.012A lumbar strain\nICD: S16.1XXA\nReferrer Name: Test Operator',
                    **{'Diagnosis Code': 'S39.012A'})
    assert result['Additional Diagnosis Codes'] == 'S16.1XXA'
    assert 'lumbar strain' in result['Compensable Body/Part(s)']


@pytest.mark.parametrize('name, first, last', [('ZX91-Q04217', 'Not found', 'Not found'),
                                                ('Example, Taylor', 'Taylor', 'Example')])
def test_case_manager_person_not_identifier(name, first, last):
    result = fields('', **{'Claims Case Manager Name': name,
                           'Claims Case Manager First Name': name if first == 'Not found' else 'Not found'})
    assert (result['Claims Case Manager First Name'], result['Claims Case Manager Last Name']) == (first, last)


def test_attorney_name_section_wins_and_extension_survives():
    source = ('Attorney Information\nAttorney Name:\nTaylor Example\nPhone Number: 555-010-0155\n'
              'Extension: 123\nReferral Instructions\nSpecial Instructions:\n'
              'Atty name: Example & Sons - T. Taylor Exampel\nPhone #: 555-010-0155\nReferrer Name: Test Operator')
    result = fields(source, **{'Attorney Name': 'Taylor Example', 'Attorney Phone Number': '555-010-0155 Ext. 123'})
    assert result['Attorney Name'] == 'Taylor Example'
    assert result['Attorney Phone Number'] == '555-010-0155 Ext. 123'


def test_attorney_without_firm_remains_unchanged():
    result = fields('Special Instructions:\nAtty name: Taylor Example\nPhone #: 555-010-0155\nReferrer Name: Test Operator')
    assert result['Attorney Name'] == 'Taylor Example'


@pytest.mark.parametrize('email,expected', [('azure.goodhart@example.com', 'Azure Goodhart'),
                                             ('AZURE_goodhart@example.com', 'Azure Goodhart'),
                                             ('other.goodhart@example.com', 'Azure')])
def test_ncm_given_name_completed_only_with_matching_nurse_email(email, expected):
    result = fields('Special Instructions:\nINSTRUCTIONS: contact NCM Azure\nReferrer Name: Test Operator',
                    **{'NCM': 'Azure', 'Nurse Case Manager E-mail Address': email})
    assert result['NCM'] == expected


def test_prompt_rules_and_contract_preserved():
    for rule in ('employer CONTACT PERSON', 'one provider record even when repeated',
                 'named organization ending in Occ Med', 'Attorney Name is the individual person',
                 'Claims Case Manager Name must be a person', 'Additional Diagnosis Codes require explicitly stated',
                 'only the base number, without an extension', '01/01/2099 is a placeholder',
                 'different year; do not correct a suspected typo',
                 'Return only a JSON object matching this template', '{DOCUMENT_TEXT}',
                 'SOURCE SEPARATION:', 'Special Instruction Fields', 'Provider Information'):
        assert rule in FIELD_ONLY_PROMPT
    assert _APPOINTMENT_SOURCE_RULE in FIELD_ONLY_PROMPT
