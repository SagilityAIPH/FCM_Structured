"""Source-reading regressions use synthetic examples, never referral PHI."""
import pytest

from AI.provider_evidence import appointment, recover_provider_records, FACILITY
from AI.referral_schema import PROVIDER_FIELDS
from AI.source_evidence import special_evidence, enforce_source_roles


def record(**values):
    return dict.fromkeys(PROVIDER_FIELDS, 'Not found') | values


def source(text):
    return 'Vendor Name:\nNursing Services\nSpecial Instructions:\n' + text + '\nReferrer Name:\nTest User'


@pytest.mark.parametrize('text,expected', [
    ('Next appt 02/23/26.', '2026-02-23'),
    ('NOV 3/17', '3/17'),
    ('Appt. Date: Time: 03/03 @ 1:30 pm', '03/03'),
    ('Appt. Date/Time: NOV 3/11/26 @11 AM', '2026-03-11'),
    ('Appt. Date: Time: Pending scheduling', None),
    ('LOV 3/3/26\nPT starts 4/2/26', None),
    ('Injury Date: 3/3/26', None),
    ('NOV 3/3/26\nNOV 4/4/26', None),
])
def test_appointment_evidence(text, expected):
    assert appointment(text).get('Appointment Date') == expected


def test_attorney_phone_does_not_cross_roles():
    values = special_evidence(source('Atty name: Alex Smith\nPhone #: 212-555-0100\nCompensable Part(s): knee\nPhone #: 212-555-0199'))
    assert values['Attorney Name'] == 'Alex Smith'
    assert values['Attorney Phone Number'] == '212-555-0100'
    assert 'Attorney Phone Number' not in special_evidence(source('Atty name:\nPhone #:\nProvider Name: Clinic\nPhone #: 212-555-0199'))


def test_facility_and_doctor_same_record():
    initial = record(**{'Doctor First Name': 'Alex', 'Doctor Last Name': 'Smith', 'Provider Phone': '212-555-0100'})
    result = recover_provider_records([initial], source('Provider Name: Alex Smith FNP/ Example Urgent Care\nPhone #: 212-555-0100'), PROVIDER_FIELDS)
    assert len(result) == 1
    assert result[0][FACILITY] == 'Example Urgent Care'


def test_reverse_doctor_facility_label():
    initial = record(**{FACILITY: 'Example Ortho', 'Doctor Last Name': 'Smith'})
    result = recover_provider_records([initial], source('PROVIDER: Example Ortho / Dr. Smith\nPhone: 212-555-0100'), PROVIDER_FIELDS)
    assert len(result) == 1
    assert result[0][FACILITY] == 'Example Ortho'
    assert result[0]['Determining if Doctor or Provider Name'] == 'Doctor'


def test_two_clinics_recovered_without_crossing_addresses():
    initial = [record(**{'Provider Phone': '212-555-0100'}), record(**{'Provider Phone': '212-555-0200'})]
    text = source('Provider Name: (include all providers IW is actively treating with) Clinic One\nPhone 212-555-0100\nAddress of Appt. location: 10 Main St\nProvider Name: Clinic Two\nPhone 212-555-0200\nAddress: 20 Other St')
    result = recover_provider_records(initial, text, PROVIDER_FIELDS)
    assert [r[FACILITY] for r in result] == ['Clinic One', 'Clinic Two']
    assert [r['Provider Address'] for r in result] == ['10 Main St', '20 Other St']


def test_no_unassigned_date_when_multiple_providers():
    initial = [record(**{FACILITY: 'Clinic One'}), record(**{FACILITY: 'Clinic Two'})]
    result = recover_provider_records(initial, source('NOV 3/17'), PROVIDER_FIELDS)
    assert all(r['Appointment Date'] == 'Not found' for r in result)


def test_company_is_not_a_contact_and_language_narrative():
    fields = {'Employer Name': 'Example Wholesale Corporation', 'Employer First Name': 'Example', 'Employer Last Name': 'Wholesale'}
    text = source('EMPLOYER: Example Wholesale\nPatient speaks Spanish')
    enforce_source_roles(fields, text)
    assert fields['Employer First Name'] == fields['Employer Last Name'] == 'Not found'
    assert special_evidence(text)['Language'] == 'Spanish'


def test_multiple_contacts_remain_aligned():
    fields = {'Employer Contact Email': 'jane_doe@example.com, alex_smith@example.com'}
    enforce_source_roles(fields, source('Employer name or contact: Alex and Jane'))
    assert fields['Employer First Name'] == 'Alex & Jane'
    assert fields['Employer Last Name'] == 'Smith & Doe'


def test_special_instructions_not_duplicated_into_referral_column():
    fields = {'Referral Instructions': 'long unrelated narrative'}
    text = 'Referral Instructions\nReferral Type:\nFull Case Management\nVendor Information\n' + source('Some instructions')
    enforce_source_roles(fields, text)
    assert fields['Referral Instructions'] == 'Not found'


def test_bare_doctor_surname_is_not_a_first_name():
    initial = record(**{'Doctor First Name': 'Smith'})
    result = recover_provider_records([initial], source('ORIF with Dr Smith\nNOV 3/17'), PROVIDER_FIELDS)
    assert result[0]['Doctor First Name'] == 'Not found'
    assert result[0]['Doctor Last Name'] == 'Smith'


def test_dr_prefix_is_not_promoted_to_first_name():
    initial = record(**{FACILITY: 'Smith', 'Doctor Last Name': 'Smith'})
    result = recover_provider_records([initial], source('Provider Name: Dr. Smith\nPhone: 212-555-0100'), PROVIDER_FIELDS)
    assert result[0]['Doctor First Name'] == 'Not found'
    assert result[0][FACILITY] == 'Not found'
