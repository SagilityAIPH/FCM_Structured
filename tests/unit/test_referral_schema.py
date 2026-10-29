import json

import pytest
from datetime import date, timedelta
from AI.appointment_rules import us_holidays

from AI import bedrock_core as core


def future_workday():
    day = date.today() + timedelta(days=30)
    while day.weekday() >= 5 or day in us_holidays(day.year):
        day += timedelta(days=1)
    return day.isoformat()


def payload():
    data = {key: "Not found" for key in core.REQUIRED_FIELDS if key not in core.PROVIDER_FIELDS}
    data["Provider Information"] = []
    return data


def provider(**values):
    return {key: values.get(key, "Not found") for key in core.PROVIDER_FIELDS}


def test_multiple_providers_keep_matching_slots_and_most_complete_first():
    data = payload()
    first = provider(**{"Provider Name (First Name / Last Name)": "First Clinic", "Provider Phone": "wrong@example.com"})
    second = provider(**{"Provider Name (First Name / Last Name)": "Second Clinic", "Provider Phone": "212-555-0123",
                         "Provider City": "Boston", "Provider Zip": "02110", "Appointment Date": "10/01/2026"})
    third = dict(second, **{"Appointment Date": "10/02/2026", "Appointment Time": "2:30 PM"})
    data["Provider Information"] = [first, second, second, third]
    text, fields = core.force_exact_field_output(json.dumps(data))
    assert fields["Provider Name (First Name / Last Name)"] == "Second Clinic & First Clinic"
    assert fields["Appointment Date"] == "2026-10-02 & 2026-10-01"
    assert fields["Appointment Time"] == "02:30 PM"
    assert fields["Provider Phone"] == "212-555-0123"
    assert fields["Provider Zip"] == "02110"
    assert "City: Boston" in text
    assert len(fields.providers) == 3
    assert fields.providers[-1]['Provider Phone'] == 'Not found'
    # Each of the three provider records has its own 11-field section.
    rows = core.fields_to_table_df(fields)
    assert len(rows) == 93
    assert list(rows.loc[rows['Field'] == 'Doctor / Facility', 'Section']) == ['Provider 1', 'Provider 2', 'Provider 3']
    assert list(rows.loc[rows['Field'] == 'Appointment Date', 'Value']) == [record['Appointment Date'] for record in fields.providers]


def test_provider_mentions_split_only_on_distinguishing_identity():
    base = provider(**{'Provider Name (First Name / Last Name)': 'Synthetic Alpha',
                       'Provider Phone': 'SYNTH-FIRST-PHONE',
                       'Appointment Date': '2030-01-02', 'Appointment Time': '9 AM'})
    alternate = dict(base, **{'Provider Phone': 'SYNTH-SECOND-PHONE',
                              'Appointment Time': '10 AM'})
    data = payload()
    data['Special Instruction Fields'] = {'Provider Information': [base]}
    data['Provider Information'] = [alternate]
    fields = core.force_exact_field_output(json.dumps(data))[1]
    assert len(fields.providers) == 1
    assert fields.providers[0]['Provider Phone'] == 'SYNTH-FIRST-PHONE'
    assert fields.providers[0]['Appointment Time'] == '09:00 AM'
    assert len(core.export_payload(fields)['Provider Information']) == 1
    data['Provider Information'] = [dict(alternate, **{'Provider Name (First Name / Last Name)': 'Synthetic Beta'})]
    fields = core.force_exact_field_output(json.dumps(data))[1]
    assert len(fields.providers) == 2
    assert [record['Provider Name (First Name / Last Name)'] for record in fields.providers] == [
        'Synthetic Alpha', 'Synthetic Beta']
    assert len(core.export_payload(fields)['Provider Information']) == 2


def test_optional_absence_does_not_retry_and_roles_are_separate():
    data = payload()
    data.update({"First Name": "Jane", "Phone Number": "212-555-0111", "Zip": "00123",
                 "Claim Number": "0001", "Claim ID": "0002", "NCM": "Nurse Example",
                 "Nurse Case Manager E-mail Address": "nurse@example.com",
                 "Claims Case Manager Name": "Claims Example", "Referral Priority": "Urgent"})
    calls = []
    def invoke(**kwargs):
        calls.append(kwargs)
        return json.dumps(data)
    _, fields, _, _ = core.run_reasoning(None, "stub", "sample", llm_call=invoke)
    assert len(calls) == 1
    assert fields["Attorney Name"] == "Not found"
    assert fields["Referral Priority"] == "Urgent"
    assert fields["Zip"] == "00123"
    assert fields["Claim Number"] != fields["Claim ID"]
    assert fields["NCM"] != fields["Claims Case Manager Name"]


def test_truncated_output_retries_and_does_not_silently_export_missing_data():
    calls = []
    def invoke(**kwargs):
        calls.append(kwargs)
        return '{"First Name":'
    with pytest.raises(ValueError, match="invalid or incomplete JSON"):
        core.run_reasoning(None, "stub", "sample", llm_call=invoke)
    assert len(calls) == 2


def test_incomplete_provider_is_rejected():
    data = payload()
    data["Provider Information"] = [{"Provider City": "Boston"}]
    with pytest.raises(ValueError, match="incomplete provider"):
        core.force_exact_field_output(json.dumps(data))


def complete_payload():
    data = payload()
    for key in data:
        if key != "Provider Information" and key not in core.OPTIONAL_FIELDS + core.SUPPLEMENTAL_FIELDS:
            data[key] = "Documented value"
    data["Provider Information"] = [provider(**{key: "Documented value" for key in core.PROVIDER_FIELDS
                                               if key not in core.SUPPLEMENTAL_FIELDS})]
    data['Provider Information'][0]['Appointment Date'] = future_workday()
    data['Provider Information'][0]['Appointment Time'] = 'Not found'
    return data


def test_section_priority_and_allowed_special_instruction_fallback():
    data = payload()
    data["Accident Description"] = "Primary section description"
    data["Claims Case Manager Name"] = "Primary manager"
    data["Special Instructions"] = {
        "Accident Description": "Conflicting special instructions",
        "Claims Case Manager Name": "Different manager",
        "Diagnosis Code": "S00.01XA", "Claims Office Name": "Fallback office",
        "Attorney Name": "Fallback Attorney", "First Name": "Forbidden fallback",
        "Claim Number": "Forbidden number", "Claim ID": "Forbidden id", "Claim Type": "Forbidden type",
        "Employer Name": "Forbidden employer",
    }
    _, fields = core.force_exact_field_output(json.dumps(data))
    assert fields["Accident Description"] == "Primary section description"
    assert fields["Claims Case Manager Name"] == "Primary manager"
    assert fields["Diagnosis Code"] == "S00.01XA"
    assert fields["Claims Office Name"] == "Fallback office"
    assert fields["Attorney Name"] == "Fallback Attorney"
    for key in ["First Name", "Employer Name", "Claim Number", "Claim ID", "Claim Type"]:
        assert fields[key] == "Not found"


def test_special_instruction_provider_fills_only_matching_record():
    data = payload()
    data["Provider Information"] = [provider(**{"Provider Name (First Name / Last Name)": "Example Clinic",
                                                "Provider City": "Boston"})]
    data["Special Instructions"] = {"Provider Information": [provider(**{
        "Provider Name (First Name / Last Name)": "Example Clinic", "Provider City": "Boston",
        "Appointment Date": "09/28/2026", "Appointment Time": "2:30 PM"})]}
    _, fields = core.force_exact_field_output(json.dumps(data))
    assert len(fields.providers) == 1
    assert fields["Appointment Time"] == "02:30 PM"


def test_optional_fields_and_legacy_extras_do_not_fail_next_step():
    _, fields = core.force_exact_field_output(json.dumps(complete_payload()))
    assert core.completeness(fields)["status"] == "Passed"
    assert fields["Address-line-2"] == "Not found"
    assert fields["Nurse Case Manager E-mail Address"] == "Not found"
    fields["Claim ID"] = "Not found"
    result = core.completeness(fields)
    assert result["status"] == "Failed"
    assert result["missing_fields"] == ["Claim Information / Claim ID"]


def test_completeness_requires_one_whole_provider_not_combined_partial_records():
    data = complete_payload()
    one = data["Provider Information"][0]
    one["Provider Name (First Name / Last Name)"] = "Clinic A & B"
    one["Provider Address"] = "Not found"
    two = dict(one, **{"Provider Name (First Name / Last Name)": "Clinic C", "Appointment Time": "2 PM",
                       "Provider Zip": "Not found"})
    data["Provider Information"] = [one, two]
    _, fields = core.force_exact_field_output(json.dumps(data))
    assert core.completeness(fields)["status"] == "Failed"
    one["Provider Address"] = "123 Main St"
    _, fields = core.force_exact_field_output(json.dumps(data))
    assert core.completeness(fields)["status"] == "Passed"
    exported = core.export_payload(fields)
    assert exported["Provider Information"][0]["Doctor / Facility"] == "Documented value Documented value"
    assert exported["Provider Information"][0]["Provider Name (First Name / Last Name)"] == "Clinic A & B"
    assert exported["NEXT STEP"]["status"] == "Passed"
    assert list(exported)[:len(core.FIELD_GROUPS)] == list(core.FIELD_GROUPS)


def test_multi_provider_gate_requires_one_complete_record():
    data = complete_payload()
    data['Provider Information'] = [provider(**{'Provider Name (First Name / Last Name)': 'Synthetic Alpha',
                                                'Appointment Date': future_workday()}),
                                    provider(**{'Provider Name (First Name / Last Name)': 'Synthetic Beta',
                                                'Appointment Date': future_workday()})]
    _, fields = core.force_exact_field_output(json.dumps(data))
    assert core.completeness(fields)['status'] == 'Failed'
    first, second = fields.providers
    for record in (first, second):
        for key in core.PROVIDER_FIELDS:
            if key not in ('Provider Name (First Name / Last Name)', 'Appointment Date', 'Appointment Time'):
                record[key] = 'Synthetic detail'
    assert core.completeness(fields)['status'] == 'Passed'
    second['Provider Address'] = 'Not found'
    assert core.completeness(fields)['status'] == 'Passed'
    first['Provider Address'] = 'Not found'
    assert core.completeness(fields)['status'] == 'Failed'


def test_no_providers_fails_and_output_uses_requested_labels():
    data = complete_payload()
    data["Provider Information"] = []
    text, fields = core.force_exact_field_output(json.dumps(data))
    assert core.completeness(fields)["status"] == "Failed"
    assert len(core.completeness(fields)["missing_fields"]) == 6
    rows = core.fields_to_table_df(fields)
    assert list(rows.columns) == ["Section", "Field", "Value", "Optional"]
    assert rows.iloc[0]["Field"] == "First Name"
    assert "Customer Name:" in text
    assert "NEXT STEP: Failed" in text
