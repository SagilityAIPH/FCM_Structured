"""Synthetic owner-decision regressions; no external services or claim data."""
import json

import pytest
from openpyxl import load_workbook

from AI.address_normalization import canonical_address
from AI.appointment_rules import appointment_checks, confirm_appointments
from AI.daily_output import save_daily_output, read_record
from AI.provider_records import FACILITY, merge_provider_records, provider_display_name
from AI import referral_schema as schema
from tests.unit.test_referral_schema import payload, provider


@pytest.mark.parametrize('short,expanded', [
    ('100 Example Street Suite 5', '100 Example St Ste 5'),
    *[(f'100 Example {short}', f'100 Example {long}') for short, long in zip(
        'Str Ave Rd Blvd Ln Ct Pl Pkwy Hwy Cir Ste Apt Fl Bldg Rm N S E W NE NW SE SW'.split(),
        'Street Avenue Road Boulevard Lane Court Place Parkway Highway Circle Suite Apartment Floor Building Room North South East West Northeast Northwest Southeast Southwest'.split())],
    (' 100  N. Example St., Ste. 5 ', '100 North Example Street Suite 5'),
    ('100 Example Dr.', '100 Example Drive'),
])
def test_canonical_address(short, expanded):
    assert canonical_address(short) == canonical_address(expanded)


def test_dr_expands_only_at_trailing_street_suffix():
    assert canonical_address('Dr Example St') == 'dr example street'
    assert canonical_address('Dr') == 'dr'
    assert canonical_address('100 Dr Example St') == '100 dr example street'
    assert canonical_address('100 Example Dr Suite 5') == '100 example dr suite 5'


def cases():
    clinic = {FACILITY: 'Synthetic Clinic', 'Provider Address': '100 Example St'}
    return {
        'A': [provider(**clinic, **{'Appointment Date': date}) for date in ('2026-11-03', '2026-12-01')],
        'B': [provider(**{FACILITY: 'Synthetic Clinic', 'Provider Address': address}) for address in
              ('100 Example Street Suite 5', '100 Example St Ste 5')],
        'C': [provider(**{'Doctor First Name': 'Alex', 'Doctor Last Name': 'Sample',
                         'Provider Address': '100 Example St', 'Appointment Date': '2026-11-03'}),
              provider(**clinic, **{'Provider Phone': '555-0100'})],
        'D': [provider(**{FACILITY: 'Synthetic Clinic'}),
              provider(**{'Provider Address': '100 Example St', 'Provider City': 'Boston',
                         'Provider State': 'MA', 'Provider Zip': '02101', 'Appointment Date': '2026-11-03'})],
    }


def parsed(records):
    data = payload()
    data['Provider Information'] = records
    return schema.parse_field_block(json.dumps(data))


@pytest.mark.parametrize('case,count', [('A', 2), ('B', 1), ('C', 1), ('D', 1)])
def test_owner_merge_cases(case, count):
    records = cases()[case]
    original = json.dumps(records)
    merged = merge_provider_records(records)
    assert len(merged) == count
    assert json.dumps(records) == original
    fields = parsed(records)
    assert len(fields.providers) == count
    if case == 'C':
        record = fields.providers[0]
        assert record['Determining if Doctor or Provider Name'] == 'Doctor'
        assert record[FACILITY] == 'Synthetic Clinic'
        assert record['Provider Phone'] == '555-0100'
        assert provider_display_name(record) == 'Alex Sample'
        assert next(row for row in schema.field_rows(fields) if row['Field'] == 'Doctor / Facility')['Value'] == 'Alex Sample'
    if case == 'D':
        assert schema.completeness(fields)['provider_missing_fields'] == [[]]


def test_doctor_display_keeps_facility_in_json_and_workbook(tmp_path):
    fields = parsed(cases()['C'])
    exported = json.loads(json.dumps(schema.export_payload(fields)))['Provider Information'][0]
    assert exported['Doctor / Facility'] == 'Alex Sample'
    assert exported[FACILITY] == 'Synthetic Clinic'
    assert fields[FACILITY] == 'Synthetic Clinic'
    path, record_id = save_daily_output(fields, 'synthetic.pdf', directory=tmp_path)
    loaded, _ = read_record(path, record_id)
    assert loaded.providers[0][FACILITY] == 'Synthetic Clinic'
    book = load_workbook(path)
    rows = list(book['Providers'].values)
    assert rows[1][rows[0].index(FACILITY)] == 'Synthetic Clinic'
    book.close()


def test_surname_display_and_label_alias():
    assert provider_display_name(provider(**{'Doctor Last Name': 'Sample', FACILITY: 'Synthetic Clinic'})) == 'Sample'
    assert schema.output_key('Provider Information', 'Doctor / Facility') == FACILITY
    assert schema.output_key('Provider Information', 'Provider / Facility Name') == FACILITY


def test_phone_and_time_keep_source_priority_and_address_line2_canonicalizes():
    records = [provider(**{FACILITY: 'Synthetic Clinic', 'Provider Phone': '555-0100',
                           'Appointment Time': '9 AM', 'Provider Address Line 2': 'Ste 5'}),
               provider(**{FACILITY: 'Synthetic Clinic', 'Provider Phone': '555-0101',
                           'Appointment Time': '10 AM', 'Provider Address Line 2': 'Suite 5'})]
    merged = merge_provider_records(records)
    assert len(merged) == 1
    assert merged[0]['Provider Phone'] == '555-0100'
    assert merged[0]['Appointment Time'] == '9 AM'


def test_merged_appointment_confirmation_is_bound_to_visit():
    fields = parsed(cases()['C'])
    from datetime import date
    today = date(2027, 1, 1)
    fields = confirm_appointments(fields, [1], today=today)
    assert appointment_checks(fields, today=today)[0]['confirmed']
    fields.providers[0]['Appointment Date'] = '2026-12-01'
    assert not appointment_checks(fields, today=today)[0]['confirmed']
