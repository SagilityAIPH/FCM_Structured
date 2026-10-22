"""Synthetic-only durable audit contract; never touches operator documents."""
from datetime import date
import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Final Code"))
from finalcode import app, audit
from AI.referral_schema import REQUIRED_FIELDS, PROVIDER_FIELDS, force_exact_field_output

TODAY = date(2030, 1, 2)


class FakeApi:
    _memory_only = True

    def __init__(self):
        import threading
        self._lock = threading.RLock()
        self._key = "SYNTHETIC-BEDROCK-SECRET"
        self._cms_secrets = {"SYNTHETIC-CMS-SECRET", "SYNTHETIC-CMS-USER"}
        self._audit_redactions = set(self._cms_secrets)
        self._documents = {"synthetic-id": {"edits": [
            {"key": "First Name", "provider_index": None, "before": "Synthetic Before",
             "after": "Synthetic After", "at": "2030-01-02T00:00:00+00:00"},
            {"key": "Provider Phone", "provider_index": 1, "before": "Synthetic Before",
             "after": "Synthetic After", "at": "2030-01-02T00:00:00+00:00"}]}}
        self.stages = []
        self.results = []

    def set_stage(self, name):
        self.stages.append(name)
        return {"ok": True, "value": True}

    def set_workflow_result(self, result):
        self.results.append(result)
        return {"ok": True, "value": True}


def setup(tmp_path, monkeypatch):
    monkeypatch.setenv(audit.ENV_DIRECTORY, str(tmp_path / "audit"))
    api = FakeApi()
    holder = app.CaptureHolder()
    holder.document_id = "synthetic-id"
    holder.model_id = "synthetic-model-id"
    return api, holder


@pytest.fixture
def complete_fields():
    data = {key: "Synthetic" for key in REQUIRED_FIELDS if key not in PROVIDER_FIELDS}
    provider = {key: "Synthetic" for key in PROVIDER_FIELDS}
    provider.update({"Appointment Date": "01/03/2030", "Appointment Time": "10:00 AM",
                     "Provider Phone": "202-555-0100", "Provider Zip": "00000"})
    second = dict(provider, **{"Provider Phone": "202-555-0101",
                               "Provider Name (First Name / Last Name)": "Synthetic second facility"})
    data.update({"Provider Information": [provider, second], "Phone Number": "202-555-0100",
                 "Zip": "00000", "Claims Office Number": "Not found"})
    fields = force_exact_field_output(json.dumps(data))[1]
    # The synthetic parser may consolidate two matching facility records; retain
    # distinct authoritative records to test the audit, not provider matching.
    fields.providers = [provider, second]
    for key in REQUIRED_FIELDS:
        if key not in PROVIDER_FIELDS and fields.get(key) == "Not found":
            fields[key] = "Synthetic"
    return fields


def run(api, holder, fields, *, change=None, capture_error=None, extract_error=None):
    text = "Synthetic referral capture. Nothing relates to a real person."
    def capture():
        if capture_error:
            raise capture_error
        return holder.record({"attachment_name": None if change == "no_attachment" else "synthetic-referral.txt",
                              "document_text": "" if change == "no_attachment" else text,
                              "claimant_row_value": "synthetic"})
    def extract(document_text):
        holder.sent_characters = len(document_text)
        if extract_error:
            raise extract_error
        return fields
    def review(value):
        if change == "cancel":
            return None
        if change == "incomplete":
            value["First Name"] = "Not found"
        return value
    def cms(data):
        if change == "cms_stop":
            return {"status": "stopped", "reason": "user_declined", "customer": "Synthetic", "cases": []}
        if change == "cms_failed":
            return {"status": "failed", "reason": "cms_failed", "error": "SYNTHETIC-CMS-SECRET",
                    "customer": "Synthetic", "cases": []}
        return {"status": "completed", "customer": "Synthetic employer", "cases": [],
                "credentials": "SYNTHETIC-CMS-SECRET"}
    def subject(data):
        if change == "builder_failed":
            return {"status": "failed", "error": "SYNTHETIC-CMS-SECRET"}
        return {"status": "completed"}
    return app.run_workflow(api, capture=capture, extract=extract, review=review,
                            cms=cms, subject_line=subject, audit_holder=holder,
                            today=TODAY, adapt=lambda fields, *, cms_customer: {"customer": cms_customer})


def saved(result):
    path = Path(result["audit_path"])
    assert path.is_file()
    return json.loads(path.read_text(encoding="utf-8"))


def test_completed_record_stages_providers_edits_credentials(tmp_path, monkeypatch, complete_fields):
    api, holder = setup(tmp_path, monkeypatch)
    result = run(api, holder, complete_fields)
    record = saved(result)
    assert [s["name"] for s in record["stages"]] == [
        "CAPTURE", "EXTRACT", "REVIEW", "GATE", "CMS", "SUBJECT LINE BUILDER"]
    assert all(s["started_at"] and s["ended_at"] for s in record["stages"])
    assert record["capture"] == {"attachment_name": "synthetic-referral.txt", "captured_characters": 61}
    assert record["extraction"]["model_id"] == "synthetic-model-id"
    assert record["extraction"]["sent_characters"] == record["capture"]["captured_characters"]
    assert len(record["extraction"]["fields"]["providers"]) == 2
    assert record["extraction"]["fields"]["providers"][1]["Provider Phone"] == "202-555-0101"
    assert "Provider Phone" not in record["extraction"]["fields"]
    assert [e["field"] for e in record["review"]["edits"]] == ["First Name", "Provider Phone"]
    assert record["review"]["edits"][1]["provider_index"] == 1
    assert record["gate"]["status"] == "Passed"
    assert record["cms"]["customer"] == "Synthetic employer"
    assert record["subject_line_builder"]["status"] == "completed"
    assert (record["outcome"], record["reason"]) == ("completed", "completed")
    serialized = json.dumps(record)
    for credential in (api._key, *api._cms_secrets):
        assert credential not in serialized
    assert "document_text" not in serialized and "claimant_row_value" not in serialized


@pytest.mark.parametrize("change,expected,stages", [
    ("no_attachment", ("ended", "no_referral_attached"), 1),
    ("cancel", ("ended", "operator_cancelled"), 3),
    ("incomplete", ("ended", "incomplete"), 4),
    ("cms_stop", ("stopped", "user_declined"), 5),
    ("cms_failed", ("failed", "cms_failed"), 5),
    ("builder_failed", ("failed", "subject_line_failed"), 6),
])
def test_early_outcomes(tmp_path, monkeypatch, complete_fields, change, expected, stages):
    api, holder = setup(tmp_path, monkeypatch)
    result = run(api, holder, complete_fields, change=change)
    record = saved(result)
    assert (record["outcome"], record["reason"]) == expected
    assert len(record["stages"]) == stages
    if change == "incomplete":
        assert any("First Name" in item for item in record["gate"]["missing_fields"])
    if change == "cancel":
        assert record["review"]["approved"] is False
    if change == "no_attachment":
        assert record["capture"]["captured_characters"] == 0
    assert "SYNTHETIC-CMS-SECRET" not in json.dumps(record)


@pytest.mark.parametrize("which", ["capture", "extract", "launcher"])
def test_failures_also_persist(tmp_path, monkeypatch, complete_fields, which):
    api, holder = setup(tmp_path, monkeypatch)
    if which == "launcher":
        result = app.run_workflow(api, capture=None, extract=None, review=None, cms=None,
                                  subject_line=None, audit_holder=holder,
                                  run=Mock(side_effect=RuntimeError("Synthetic launcher failure")))
        assert saved(result)["reason"] == "launcher_error"
    else:
        error = RuntimeError("Synthetic stage failure")
        result = run(api, holder, complete_fields, **{which + "_error": error})
        record = saved(result)
        assert (record["outcome"], record["reason"]) == ("failed", "exception")
        assert record["stages"][-1]["name"] == which.upper()
        assert record["stages"][-1]["outcome"] == "failed"


def test_missing_cms_inputs_persist(tmp_path, monkeypatch, complete_fields):
    from finalcode import orchestrator
    api, holder = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(orchestrator.cms_inputs, "to_cms_inputs", lambda fields: {})
    result = run(api, holder, complete_fields)
    record = saved(result)
    assert (record["outcome"], record["reason"]) == ("failed", "missing_cms_inputs")
    assert record["stages"][-1]["name"] == "CMS"
    assert "claimNumber" in record["gate"]["cms_input_missing_fields"]


def test_write_failure_is_nonfatal_and_visible(tmp_path, monkeypatch, complete_fields, caplog):
    api, holder = setup(tmp_path, monkeypatch)
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("Synthetic blocker", encoding="utf-8")
    monkeypatch.setenv(audit.ENV_DIRECTORY, str(blocker / "audit"))
    result = run(api, holder, complete_fields)
    assert (result["outcome"], result["reason"]) == ("completed", "completed")
    assert "audit_path" not in result
    assert "Referral audit could not be saved" in result["audit_error"]
    assert result["audit_error"] in api.stages[-1]
    assert "SYNTHETIC-CMS-SECRET" not in caplog.text


def test_same_minute_unique_files(tmp_path, monkeypatch, complete_fields):
    api, holder = setup(tmp_path, monkeypatch)
    first = run(api, holder, complete_fields)
    second = run(api, holder, complete_fields)
    assert first["audit_path"] != second["audit_path"]
    assert saved(first)["run_id"] != saved(second)["run_id"]
    assert len(list((tmp_path / "audit").glob("*.json"))) == 2
    assert not list((tmp_path / "audit").glob("*.tmp"))


def test_repository_override_is_refused(tmp_path, monkeypatch, complete_fields):
    api, holder = setup(tmp_path, monkeypatch)
    repo = Path(__file__).resolve().parents[2]
    monkeypatch.setenv(audit.ENV_DIRECTORY, str(repo / "Output" / "audit"))
    result = run(api, holder, complete_fields)
    assert result["outcome"] == "completed"
    assert "audit_error" in result and "audit_path" not in result
    assert audit.output_directory.__module__ == "finalcode.audit"


def test_git_worktree_override_is_refused(tmp_path, monkeypatch, complete_fields):
    api, holder = setup(tmp_path, monkeypatch)
    worktree = tmp_path / "another-worktree"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: synthetic", encoding="utf-8")
    monkeypatch.setenv(audit.ENV_DIRECTORY, str(worktree / "audit"))
    result = run(api, holder, complete_fields)
    assert result["outcome"] == "completed"
    assert "audit_error" in result and "audit_path" not in result


def test_cms_credentials_cleared_before_audit_are_still_redacted(tmp_path, monkeypatch, complete_fields):
    api, holder = setup(tmp_path, monkeypatch)
    original = api.set_stage
    def stage(name):
        if name == "SUBJECT LINE BUILDER":
            api._audit_redactions.update(api._cms_secrets)
            api._cms_secrets.clear()
        return original(name)
    api.set_stage = stage
    complete_fields["First Name"] = "SYNTHETIC-CMS-SECRET"
    record = saved(run(api, holder, complete_fields))
    assert "SYNTHETIC-CMS-SECRET" not in json.dumps(record)
    assert record["extraction"]["fields"]["First Name"] == "[redacted]"
