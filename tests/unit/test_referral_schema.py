import json

import pytest

from AI import bedrock_core as core


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
    assert fields["Provider Name (First Name / Last Name)"] == "Second Clinic & Second Clinic & First Clinic"
    assert fields["Appointment Date"] == "10/02/2026 & 10/01/2026 & Not found"
    assert fields["Appointment Time"] == "2:30 PM & Not found & Not found"
    assert fields["Provider Phone"] == "212-555-0123 & 212-555-0123 & Not found"
    assert fields["Provider Zip"] == "02110 & 02110 & Not found"
    assert "Provider City: Boston & Boston & Not found" in text
    assert len(core.fields_to_table_df(fields)) == 51


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
