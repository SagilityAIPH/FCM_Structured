"""Synthetic iCase-layout regressions for provider identity and visit evidence."""
import json
from datetime import date

import pytest

from AI import referral_schema as schema
from AI.appointment_rules import appointment_checks, confirm_appointments, normalize_appointment
from AI.provider_evidence import _identity
from AI.provider_records import FACILITY, merge_provider_records

MISSING = 'Not found'


def provider(**values):
    return {key: values.get(key, MISSING) for key in schema.PROVIDER_FIELDS}


def parse(providers, *, special=(), referral=(), source='', attorney=MISSING):
    data = {key: MISSING for key in schema.REQUIRED_FIELDS if key not in schema.PROVIDER_FIELDS}
    data['Attorney Phone Number'] = attorney
    data['Provider Information'] = providers
    data['Referral Instruction Providers'] = list(referral)
    data['Special Instruction Fields'] = {'Provider Information': list(special)}
    data['RRS Classification'] = {key: MISSING for key in ('Body Part', 'Injury Type', 'Injury Cause')}
    return schema.force_exact_field_output(json.dumps(data), source_text=source)[1]


def form(*, facility, special, referral):
    return ('Provider Information\nProvider / Facility Name: ' + facility +
            '\nAttorney Information\nReferral Instructions\nNext Provider Appt. Date: ' + referral +
            '\nVendor Name:\nExample Nursing\nSpecial Instructions:\nProvider Name: ' + special +
            '\nReferrer Name:\nTesty Example\n')


@pytest.mark.parametrize('combined,facility,first,last', [
    ('Dr Testy Example with Example Ortho Clinic', 'Example Ortho Clinic', 'Testy', 'Example'),
    ('Testy Example MD with Example Ortho Clinic', 'Example Ortho Clinic', 'Testy', 'Example'),
    ('Testy Example - Example Ortho Clinic', 'Example Ortho Clinic', 'Testy', 'Example'),
    ('Example Ortho Clinic Dr Testy Example', 'Example Ortho Clinic', 'Testy', 'Example'),
    ('Example Ortho Clinic / Dr Testy Example', 'Example Ortho Clinic', 'Testy', 'Example'),
])
def test_one_visit_combined_identity_and_time_formats(combined, facility, first, last):
    full = provider(**{FACILITY: combined, 'Provider Phone': '202-555-0101',
                       'Appointment Date': '2027-03-19', 'Appointment Time': '9:15am'})
    source = form(facility=facility, special=combined, referral='3/19')
    fields = parse([provider(**{FACILITY: facility})], special=[full],
                   referral=[provider(**{'Provider Address': '100 Example St',
                                         'Appointment Date': '2027-03-19', 'Appointment Time': '09:15AM'})],
                   source=source)
    assert len(fields.providers) == 1
    record = fields.providers[0]
    assert (record[FACILITY], record['Doctor First Name'], record['Doctor Last Name']) == (facility, first, last)
    assert record['Appointment Date'] == '2027-03-19'
    assert record['Appointment Time'] == '09:15 AM'
    assert record['Provider Address'] == '100 Example St'
    assert fields[FACILITY] == facility
    assert ' & ' not in fields[FACILITY]


def test_yearless_same_visit_merges_without_matching_address_or_phone():
    fields = parse([provider(**{FACILITY: 'Example Ortho Clinic'})],
                   special=[provider(**{FACILITY: 'Example Ortho Clinic', 'Appointment Date': '3/19',
                                        'Provider Phone': '202-555-0102'})],
                   referral=[provider(**{'Provider Address': '101 Example Rd',
                                         'Appointment Date': '2026-03-19'})])
    assert len(fields.providers) == 1
    assert fields.providers[0]['Appointment Date'] == '2026-03-19'
    assert fields.providers[0]['Provider Phone'] == '202-555-0102'


@pytest.mark.parametrize('first,second', [
    (provider(**{FACILITY: 'Example Ortho Clinic', 'Appointment Date': '2027-05-03'}),
     provider(**{FACILITY: 'Different Health Center', 'Appointment Date': '2027-05-03'})),
    (provider(**{FACILITY: 'Example Ortho Clinic', 'Provider Address': '100 Example St'}),
     provider(**{FACILITY: 'Example Ortho Clinic', 'Provider Address': '200 Different Rd'})),
    (provider(**{FACILITY: 'Example Ortho Clinic', 'Appointment Date': '2027-05-03'}),
     provider(**{FACILITY: 'Example Ortho Clinic', 'Appointment Date': '2027-05-04'})),
    (provider(**{FACILITY: 'Example Ortho Clinic', 'Appointment Date': '2027-05-03',
                  'Provider Address': '100 Example St', 'Appointment Time': '9 AM'}),
     provider(**{FACILITY: 'Example Ortho Clinic', 'Appointment Date': '2028-05-03',
                  'Provider Address': '100 Example St', 'Appointment Time': '10 AM'})),
])
def test_distinct_identity_address_date_or_year_remains_separate(first, second):
    assert len(parse([first, second]).providers) == 2


def test_phone_and_time_differences_do_not_identify_distinct_facilities():
    first = provider(**{FACILITY: 'Example Ortho Clinic', 'Provider Phone': '202-555-0101',
                        'Appointment Time': '9 AM'})
    second = provider(**{FACILITY: 'Different Health Center', 'Provider Phone': '202-555-0101',
                         'Appointment Time': '10 AM'})
    assert len(merge_provider_records([first, second])) == 2
    assert len(merge_provider_records([first, dict(first, **{'Provider Phone': '202-555-0102',
                                                              'Appointment Time': '10 AM'})])) == 1


def test_organization_occ_med_not_a_doctor_but_documented_person_is():
    fields = parse([provider(**{FACILITY: 'Example Partners Occ Med'})],
                   special=[provider(**{FACILITY: 'Example Partners Occ Med'})],
                   source=form(facility='Example Partners Occ Med', special='Example Partners Occ Med',
                               referral='5/3/2027'))
    assert fields.providers[0][FACILITY] == 'Example Partners Occ Med'
    assert fields['Doctor First Name'] == fields['Doctor Last Name'] == MISSING
    assert _identity('Dr. Testy Example Occ Med')['Doctor Last Name'] == 'Example'
    assert _identity('Dr. Testy Example')['Doctor First Name'] == 'Testy'


def test_surname_only_acronym_department_never_becomes_given_name():
    label = 'DR Sample EHC Hand'
    fields = parse([provider(**{FACILITY: label, 'Doctor First Name': 'SAMPLE EHC',
                              'Doctor Last Name': 'Hand'})],
                   source=form(facility=label, special=label, referral='5/3/2027'))
    assert len(fields.providers) == 1
    assert fields.providers[0]['Doctor First Name'] == MISSING
    assert fields.providers[0]['Doctor Last Name'].casefold() == 'sample'
    assert fields.providers[0][FACILITY] == 'EHC Hand'


@pytest.mark.parametrize('extension', ['x 1', 'ext. 23', 'extension 4'])
def test_provider_phone_extension_only_base_and_attorney_unchanged(extension):
    phone = '202-555-0101 ' + extension
    fields = parse([provider(**{FACILITY: 'Example Ortho Clinic', 'Provider Phone': phone})],
                   attorney='202-555-0199 Ext. 58911')
    assert fields.providers[0]['Provider Phone'] == fields['Provider Phone'] == '202-555-0101'
    assert fields['Attorney Phone Number'] == '202-555-0199 Ext. 58911'


def test_provider_phone_extension_from_special_source_only_base():
    source = form(facility='Example Ortho Clinic', special='Example Ortho Clinic',
                  referral='05/03/2027').replace('Referrer Name:',
                                               'Phone #: 202-555-0103 extension 4\nReferrer Name:')
    fields = parse([provider(**{FACILITY: 'Example Ortho Clinic'})], source=source)
    assert len(fields.providers) == 1
    assert fields['Provider Phone'] == '202-555-0103'


@pytest.mark.parametrize('written', ['01/01/2099', '2099-01-01', 'January 1, 2099', '01-01-2099'])
def test_placeholder_date_missing_with_nonblocking_review(written):
    fields = parse([provider(**{FACILITY: 'Example Ortho Clinic', 'Appointment Date': written,
                              'Appointment Time': '9:15 AM'})])
    assert fields.providers[0]['Appointment Date'] == fields['Appointment Date'] == MISSING
    assert fields.providers[0]['Appointment Time'] == MISSING
    assert any(flag['kind'] == 'placeholder' and flag['field'] == 'Appointment Date' and
               flag['reason'] == 'placeholder appointment date 01/01/2099 -- no appointment scheduled'
               for flag in fields.review_flags)
    check = appointment_checks(fields, today=date(2026, 10, 30))[0]
    assert not check['can_confirm'] and not check['date_only'] and not check['confirmed']
    with pytest.raises(ValueError):
        confirm_appointments(fields, [1], today=date(2026, 10, 30))
    assert 'Appointment Date' in str(schema.completeness(fields, today=date(2026, 10, 30))['missing_fields'])


def test_conflicting_year_same_address_identity_and_time_special_date_wins():
    source = form(facility='Example Spine Clinic', special='Dr Testy Example - Example Spine Clinic',
                  referral='03/12/2026')
    fields = parse([provider(**{FACILITY: 'Example Spine Clinic'})],
                   special=[provider(**{FACILITY: 'Example Spine Clinic',
                                        'Doctor First Name': 'Testy', 'Doctor Last Name': 'Example',
                                        'Provider Address': '101 Example Road',
                                        'Appointment Date': '3/12/16', 'Appointment Time': '10:00 AM'})],
                   referral=[provider(**{FACILITY: 'Example Spine Clinic',
                                         'Provider Address': '101 Example Rd',
                                         'Appointment Date': '03/12/2026', 'Appointment Time': '10:00am'})],
                   source=source)
    assert len(fields.providers) == 1
    assert fields.providers[0]['Appointment Date'] == '2016-03-12'
    assert fields.providers[0]['Appointment Time'] == '10:00 AM'
    assert 'Appointment is in the past' in appointment_checks(fields, date(2026, 10, 30))[0]['reasons']


def test_two_distinct_visits_keep_different_years_even_when_identity_matches():
    fields = parse([], special=[provider(**{FACILITY: 'Example Spine Clinic',
                                          'Provider Address': '101 Example Road',
                                          'Appointment Date': '3/12/16', 'Appointment Time': '10:00 AM'})],
                   referral=[provider(**{FACILITY: 'Example Spine Clinic',
                                         'Provider Address': '202 Other Road',
                                         'Appointment Date': '03/12/2026', 'Appointment Time': '10:00am'})])
    assert len(fields.providers) == 2
    assert {p['Appointment Date'] for p in fields.providers} == {'2016-03-12', '2026-03-12'}


def test_normal_future_date_survives_and_has_no_placeholder_flag():
    fields = parse([provider(**{FACILITY: 'Example Ortho Clinic', 'Appointment Date': '2027-05-03'})])
    assert fields.providers[0]['Appointment Date'] == '2027-05-03'
    assert not any(flag['kind'] == 'placeholder' for flag in fields.review_flags)
    assert normalize_appointment('May 3, 2027', MISSING)[0] == '2027-05-03'


def test_placeholder_review_survives_recheck_until_date_is_edited():
    from AI.field_review import review_formats

    fields = parse([provider(**{FACILITY: 'Example Ortho Clinic',
                              'Appointment Date': '01/01/2099'})])
    assert len([f for f in review_formats(fields, fields.review_flags) if f['kind'] == 'placeholder']) == 1
    fields.providers[0]['Appointment Date'] = '2027-05-03'
    assert not any(f['kind'] == 'placeholder' for f in review_formats(
        fields, fields.review_flags, edited={('Appointment Date', 0)}))
