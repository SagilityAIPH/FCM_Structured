import json

from AI import referral_schema as schema
from AI.source_evidence import explicit_form_fields, special_evidence
from AI.address_enrichment import apply_suggestions
from tests.unit.test_referral_schema import payload, provider


FORM = '''Claimant Information
Name:
TEST,CASE
Social Security Number:
***-**-1234
Customer Name:
EXAMPLE COMPANY
Customer Contact Name:
Customer Contact Phone Number:
Extension:
Claim Information
Claim Number:
WC001
Diagnosis Code:
Case Manager Information
'''


def parsed(source, **changes):
    data = payload()
    data.update(changes)
    return schema.parse_field_block(json.dumps(data), source_text=source)


def test_explicit_blank_customer_fields_cannot_be_filled_with_employer_contact():
    source = FORM + '''Special Instructions:
Employer name and contact: Jane Example
Phone #: (727) 362-7200 EXT 7854
Atty name:
Phone #: 111-222-3333
Referrer Name: Someone
'''
    fields = parsed(source, **{'Employer Contact Name': 'Jane Example',
                              'Employer Contact Mobile': '(727) 362-7200 EXT 7854'})
    assert fields['Employer Contact Name'] == fields['Employer Contact Mobile'] == 'Not found'
    assert fields['Employer First Name'] == 'Jane'
    assert fields['Employer Mobile'] == '(727) 362-7200 EXT 7854'
    assert fields['Social Security Number'] == '***-**-1234'


def test_missing_labels_are_not_treated_as_blank_labels():
    assert explicit_form_fields('Claimant Information\nName: TEST,CASE\nClaim Information\n') == {
        'First Name': 'CASE', 'Last Name': 'TEST'}
    assert parsed('', **{'Employer Contact Name': 'Recorded Customer'})['Employer Contact Name'] == 'Recorded Customer'


def test_combined_diagnosis_label_splits_code_and_description():
    source = FORM + '''Special Instructions:
COMPENSABLE BODY PART(S) & DIAGNOSIS: S39.012A Strain of muscle, fascia and tendon of lower back.
WORK STATUS: Full duty
Referrer Name: Someone
'''
    fields = parsed(source)
    assert fields['Diagnosis Code'] == 'S39.012A'
    assert fields['Compensable Body/Part(s)'] == 'Strain of muscle, fascia and tendon of lower back.'
    assert fields['Additional Diagnosis Codes'] == 'Not found'


def test_primary_section_diagnosis_wins_and_remaining_codes_are_preserved():
    source = FORM.replace('Diagnosis Code:\n', 'Diagnosis Code: S09.90XA\n') + '''Special Instructions:
COMPENSABLE BODY PART(S):
Cervical strain (S16.1XXA)
Scalp laceration (S01.01XA)
WORK STATUS: Off work
Referrer Name: Someone
'''
    fields = parsed(source)
    assert fields['Diagnosis Code'] == 'S09.90XA'
    assert fields['Additional Diagnosis Codes'] == 'S16.1XXA; S01.01XA'
    assert fields['Compensable Body/Part(s)'] == 'Cervical strain Scalp laceration'


def test_employer_subsection_and_vendor_nurse_assignment():
    source = '''Vendor Information
Vendor Name: Genex Services Inc.
Special Instructions:
Please send the referral to Tracy Vortman at Genex, we will wait
until she is available.
Provider name: Example Clinic
Ph.#: 222-333-4444
Employer: UPS
Contact name: Sylvia Keller
Ph #: 510-772-7627
CURRENT WORK STATUS: TAW
Referrer Name: Someone
'''
    fields = parsed(source)
    assert (fields['Employer First Name'], fields['Employer Last Name']) == ('Sylvia', 'Keller')
    assert fields['Employer Mobile'] == '510-772-7627'
    assert fields['NCM'] == 'Tracy Vortman'
    assert fields['Employer Contact Name'] == 'Not found'


def test_referral_recipient_at_another_organization_is_not_assumed_to_be_ncm():
    source = '''Vendor Name: Nursing Vendor
Special Instructions:
Please send the referral to Jane Example at AttorneyOffice.
Referrer Name: Someone
'''
    assert parsed(source)['NCM'] == 'Not found'


def test_contiguous_email_uses_documented_surname_anchor_and_keeps_provenance():
    fields = parsed('Special Instructions:\nEmployer name and contact: GT Lomas-georgelomas@ups.com\nPhone #:\nReferrer Name: Someone')
    assert (fields['Employer First Name'], fields['Employer Last Name']) == ('George', 'Lomas')
    assert fields['Employer Contact Email'] == 'georgelomas@ups.com'
    assert fields.name_inference[0]['previous_value'] == 'GT'
    assert 'not verified' in fields.name_inference[0]['method']
    assert schema._email_name('gtlomas@ups.com', 'Lomas') is None
    assert schema._email_name('georgelomas@ups.com') is None
    assert schema._email_name('georgelomas@ups.com; other@example.com', 'Lomas') is None


def test_source_roles_and_other_contact_details_do_not_leak():
    source = '''Special Instructions:
Provider name: Example Clinic
Phone #: 222-333-4444
Employer name and contact: No contact required
Phone #:
Atty name: Attorney Person
Phone #: 555-666-7777
Email: attorney@example.com
Referrer Name: Someone
'''
    values = special_evidence(source)
    assert not any(key.startswith('Employer') for key in values)


def test_provider_facility_is_recovered_only_with_matching_street_and_phone():
    source = '''Special Instructions:
Provider Name: OIB Ortho
Phone: 732-974-0404
Address of Appt. Location: 2315 NJ-34, Manasquan, NJ 08736
Employer name and contact: Not provided
Referrer Name: Someone
'''
    one = provider(**{'Provider Address': '2315 NJ-34', 'Provider Phone': '732-974-0404'})
    two = provider(**{'Provider Address': 'Other street', 'Provider Phone': '732-974-0404'})
    fields = parsed(source, **{'Provider Information': [one, two]})
    assert fields.providers[0]['Provider Name (First Name / Last Name)'] == 'OIB Ortho'
    assert fields.providers[1]['Provider Name (First Name / Last Name)'] == 'Not found'


def test_all_missing_summary_is_single_but_records_and_mixed_slots_stay_aligned():
    fields = parsed('', **{'Provider Information': [
        provider(**{'Provider Name (First Name / Last Name)': 'Clinic A', 'Appointment Date': '2026-12-01'}),
        provider(**{'Provider Name (First Name / Last Name)': 'Clinic B', 'Appointment Date': '2026-12-02', 'Provider City': 'Waco'})]})
    assert fields['Doctor First Name'] == fields['Doctor Last Name'] == 'Not found'
    assert fields['Provider City'] == 'Waco'  # missing slots remain in detailed records only
    assert fields['Provider Name (First Name / Last Name)'] == 'Clinic B & Clinic A'
    assert len(fields.providers) == 2
    assert 'Doctor First Name: Not found & Not found' not in schema.format_field_block(fields)
    assert apply_suggestions(fields, [], [])['Doctor First Name'] == 'Not found'
    assert all(record['Doctor First Name'] == 'Not found' for record in schema.export_payload(fields)['Provider Information'])
