"""Regression coverage for the single-doctor ALLEN,JULIA referral pattern."""
import json

import pytest

from AI import referral_schema as schema
from AI.daily_output import save_daily_output, read_record
from tests.unit.test_referral_schema import payload, provider


def visit(**changes):
    values = {'Provider Address': '721 W Robertson St', 'Provider Address Line 2': 'Suite 102',
              'Provider City': 'Brandon', 'Provider State': 'FL', 'Provider Zip': '33511',
              'Appointment Date': '2025-09-04', 'Appointment Time': '08:30 am'}
    values.update(changes)
    return provider(**values)


def doctor(**changes):
    values = {'Doctor First Name': 'Shaan', 'Doctor Last Name': 'Mehta',
              'Provider Phone': '(813) 684- 3707', 'Determining if Doctor or Provider Name': 'Doctor'}
    values.update(changes)
    return visit(**values)


def parse(records):
    data = payload()
    data['Provider Information'] = records
    return schema.parse_field_block(json.dumps(data))


def test_allen_single_doctor_not_doctor_and_empty_facility(tmp_path):
    data = payload()
    data['Special Instruction Fields'] = {'Provider Information': [doctor()]}
    data['Referral Instruction Providers'] = [visit()]
    data['Provider Information'] = [provider(**{'Doctor First Name': 'Shaan', 'Doctor Last Name': 'Mehta',
                                               'Determining if Doctor or Provider Name': 'Doctor'})]
    fields = schema.parse_field_block(json.dumps(data))
    assert fields.providers == [doctor()]
    text = schema.format_field_block(fields)
    assert 'Doctor First Name: Shaan\n' in text
    assert 'Doctor Last Name: Mehta\n' in text
    assert 'Provider / Facility: Not found\n' in text
    assert all(' & ' not in fields[key] for key in schema.PROVIDER_FIELDS)
    assert len(schema.export_payload(fields)['Provider Information']) == 1
    path, record_id = save_daily_output(fields, 'regression.pdf', directory=tmp_path)
    loaded, _ = read_record(path, record_id)
    assert loaded.providers == fields.providers


@pytest.mark.parametrize('anonymous_first', [False, True])
@pytest.mark.parametrize('time', ['8:30am', '08:30'])
def test_unnamed_visit_matches_after_all_sources_collected(anonymous_first, time):
    partial = visit(**{'Appointment Date': '09/04/2025', 'Appointment Time': time})
    records = [partial, doctor()] if anonymous_first else [doctor(), partial]
    assert len(parse(records).providers) == 1


@pytest.mark.parametrize('change', [
    {'Appointment Date': '2025-09-05'}, {'Appointment Time': '10:30 am'},
    {'Provider Address': '722 W Robertson St'}, {'Provider Address Line 2': 'Suite 202'},
    {'Doctor First Name': 'Another'},
])
def test_conflicting_unnamed_records_are_not_attached(change):
    assert len(parse([doctor(), visit(**change)]).providers) == 2


def test_two_doctors_same_location_and_appointment_remain_ambiguous():
    fields = parse([doctor(), visit(), doctor(**{'Doctor First Name': 'Jane', 'Doctor Last Name': 'Doe'})])
    assert len(fields.providers) == 3
    assert sum(schema.provider_identity(record) is None for record in fields.providers) == 1


def test_doctors_sharing_a_facility_are_not_merged():
    fields = parse([doctor(**{'Provider Name (First Name / Last Name)': 'Same Clinic'}),
                    doctor(**{'Provider Name (First Name / Last Name)': 'Same Clinic',
                              'Doctor First Name': 'Jane', 'Doctor Last Name': 'Doe'})])
    assert len(fields.providers) == 2


def test_date_alone_is_not_enough_to_identify_provider():
    assert len(parse([doctor(), provider(**{'Appointment Date': '2025-09-04'})]).providers) == 2


def test_anonymous_special_details_retain_priority_over_named_section():
    data = payload()
    data['Special Instruction Fields'] = {'Provider Information': [visit(**{'Provider Phone': '111'})]}
    data['Provider Information'] = [doctor()]
    fields = schema.parse_field_block(json.dumps(data))
    assert len(fields.providers) == 1
    assert fields['Provider Phone'] == '111'


def test_no_identity_anywhere_is_retained_for_missing_information_review():
    fields = parse([visit(), visit()])
    assert len(fields.providers) == 1
    assert 'Provider 1 / Facility name or doctor first and last names' in schema.completeness(fields)['missing_fields']
