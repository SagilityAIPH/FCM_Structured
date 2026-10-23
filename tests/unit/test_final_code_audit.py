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
    monkeypatch.delenv("FCM_REFERRALS_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
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


def run(api, holder, fields, *, change=None, capture_error=None, extract_error=None, source_text=None):
    text = source_text if source_text is not None else "Synthetic referral capture. Nothing relates to a real person."
    def capture():
        if capture_error:
            raise capture_error
        return holder.record({"attachment_name": None if change == "no_attachment" else "synthetic-referral.txt",
                              "document_text": "" if change == "no_attachment" else text,
                              "claimant_row_value": "synthetic"})
    def extract(document_text):
        holder.sent_characters = len(document_text)
        if change == "truncated":
            holder.sent_text = document_text[:11]
            holder.sent_characters = len(holder.sent_text)
        if extract_error:
            raise extract_error
        return fields
    def review(value):
        if api._referral_record.path is not None:
            initial = json.loads(api._referral_record.path.read_text(encoding="utf-8"))
            expected = text
            for secret in (api._key, *api._cms_secrets, *api._audit_redactions):
                expected = expected.replace(secret, "[redacted]")
            assert initial["source_text"] == expected
        if change == "text_preserve":
            holder.text = "Synthetic later display text"
            holder.sent_text = "Synthetic later model text"
        if change == "cancel":
            return None
        if change == "incomplete":
            value["First Name"] = "Not found"
        return value
    def cms(data):
        if api._referral_record.path is not None:
            checkpoint = json.loads(api._referral_record.path.read_text(encoding="utf-8"))
            assert checkpoint["saves"][-1]["reason"] == "complete"
            assert checkpoint["completeness"]["status"] == "Passed"
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
    end = record["run_end"]
    assert [s["name"] for s in end["stages"]] == [
        "CAPTURE", "EXTRACT", "REVIEW", "GATE", "CMS", "SUBJECT LINE BUILDER"]
    assert all(s["started_at"] and s["ended_at"] for s in end["stages"])
    assert record["captured_characters"] == 61
    assert record["model_id"] == "synthetic-model-id"
    assert record["sent_characters"] == record["captured_characters"]
    assert record["source_text"] == "Synthetic referral capture. Nothing relates to a real person."
    assert "sent_text" not in record
    assert len(record["ai_extracted"]["providers"]) == 2
    assert record["ai_extracted"]["providers"][1]["Provider Phone"] == "202-555-0101"
    assert "Provider Phone" not in record["ai_extracted"]
    assert [e["field"] for e in record["review_edits"]] == ["First Name", "Provider Phone"]
    assert record["review_edits"][1]["provider_index"] == 1
    assert record["completeness"]["status"] == "Passed"
    assert end["cms"]["customer"] == "Synthetic employer"
    assert end["subject_line_builder"]["status"] == "completed"
    assert (end["outcome"], end["reason"]) == ("completed", "completed")
    assert [item["reason"] for item in record["saves"]] == ["after_extraction", "complete", "run_end"]
    assert result["audit_path"] == result["referral_path"]
    assert len(list(Path(result["referral_path"]).parent.glob("*.json"))) == 1
    serialized = json.dumps(record)
    for credential in (api._key, *api._cms_secrets):
        assert credential not in serialized
    assert "document_text" not in serialized and "claimant_row_value" not in serialized


def test_final_code_different_model_input_preserved(tmp_path, monkeypatch, complete_fields):
    api, holder = setup(tmp_path, monkeypatch)
    data = saved(run(api, holder, complete_fields, change="truncated"))
    assert data["source_text"] == "Synthetic referral capture. Nothing relates to a real person."
    assert data["sent_text"] == data["source_text"][:11]
    assert data["sent_characters"] == 11
    assert data["captured_characters"] == len(data["source_text"])


def test_final_code_source_is_frozen_through_completion_and_run_end(tmp_path, monkeypatch, complete_fields):
    api, holder = setup(tmp_path, monkeypatch)
    data = saved(run(api, holder, complete_fields, change="text_preserve"))
    assert data["source_text"] == "Synthetic referral capture. Nothing relates to a real person."
    assert "sent_text" not in data
    assert [item["reason"] for item in data["saves"]] == ["after_extraction", "complete", "run_end"]


def test_final_code_source_credentials_redacted(tmp_path, monkeypatch, complete_fields):
    api, holder = setup(tmp_path, monkeypatch)
    data = saved(run(api, holder, complete_fields,
                     source_text="Synthetic captured source SYNTHETIC-BEDROCK-SECRET and SYNTHETIC-CMS-SECRET"))
    assert data["source_text"] == "Synthetic captured source [redacted] and [redacted]"
    assert "SYNTHETIC-BEDROCK-SECRET" not in json.dumps(data)


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
    assert (record["run_end"]["outcome"], record["run_end"]["reason"]) == expected
    assert len(record["run_end"]["stages"]) == stages
    if change == "incomplete":
        assert [s["reason"] for s in record["saves"]] == ["after_extraction", "run_end"]
        assert any("First Name" in item for item in record["completeness"]["missing_fields"])
        assert record["ai_extracted"]["First Name"] == "Synthetic"
        assert record["current"]["First Name"] == "Not found"
    if change == "cancel":
        assert "complete" not in [s["reason"] for s in record["saves"]]
    if change == "no_attachment":
        assert record["captured_characters"] == 0
    assert "SYNTHETIC-CMS-SECRET" not in json.dumps(record)


@pytest.mark.parametrize("which", ["capture", "extract", "launcher"])
def test_failures_also_persist(tmp_path, monkeypatch, complete_fields, which):
    api, holder = setup(tmp_path, monkeypatch)
    if which == "launcher":
        result = app.run_workflow(api, capture=None, extract=None, review=None, cms=None,
                                  subject_line=None, audit_holder=holder,
                                  run=Mock(side_effect=RuntimeError("Synthetic launcher failure")))
        assert saved(result)["run_end"]["reason"] == "launcher_error"
    else:
        error = RuntimeError("Synthetic stage failure")
        result = run(api, holder, complete_fields, **{which + "_error": error})
        record = saved(result)
        assert (record["run_end"]["outcome"], record["run_end"]["reason"]) == ("failed", "exception")
        assert record["run_end"]["stages"][-1]["name"] == which.upper()
        assert record["run_end"]["stages"][-1]["outcome"] == "failed"


def test_missing_cms_inputs_persist(tmp_path, monkeypatch, complete_fields):
    from finalcode import orchestrator
    api, holder = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(orchestrator.cms_inputs, "to_cms_inputs", lambda fields: {})
    result = run(api, holder, complete_fields)
    record = saved(result)
    assert record["record_id"] == getattr(api, "_referral_record").record_id
    assert (record["run_end"]["outcome"], record["run_end"]["reason"]) == ("failed", "missing_cms_inputs")
    assert record["run_end"]["stages"][-1]["name"] == "CMS"
    assert [s["reason"] for s in record["saves"]] == ["after_extraction", "complete", "run_end"]


def test_gate_exception_does_not_mark_complete(tmp_path, monkeypatch, complete_fields):
    from finalcode import orchestrator
    api, holder = setup(tmp_path, monkeypatch)
    def failed_gate(*args, **kwargs):
        raise RuntimeError("Synthetic gate failure")
    monkeypatch.setattr(orchestrator, "completeness", failed_gate)
    result = run(api, holder, complete_fields)
    record = saved(result)
    assert result["outcome"] == "failed"
    assert record["run_end"]["error"]["stage"] == "GATE"
    assert [s["reason"] for s in record["saves"]] == ["after_extraction", "run_end"]


def test_fabricated_custom_runner_stages_do_not_mark_complete(tmp_path, monkeypatch, complete_fields):
    api, holder = setup(tmp_path, monkeypatch)
    def fabricated(**kwargs):
        kwargs["review"](complete_fields)
        kwargs["on_stage"]("GATE")
        kwargs["on_stage"]("CMS")
        return {"outcome": "completed", "reason": "completed", "stages": [], "payloads": {}}
    result = app.run_workflow(api, capture=None, extract=None, review=lambda value: value,
                              cms=None, subject_line=None, run=fabricated,
                              audit_holder=holder, today=TODAY)
    record = saved(result)
    assert [s["reason"] for s in record["saves"]] == ["run_end"]


def test_write_failure_is_nonfatal_and_visible(tmp_path, monkeypatch, complete_fields, caplog):
    api, holder = setup(tmp_path, monkeypatch)
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("Synthetic blocker", encoding="utf-8")
    monkeypatch.setenv(audit.ENV_DIRECTORY, str(blocker / "audit"))
    monkeypatch.setenv("LOCALAPPDATA", str(blocker))
    result = run(api, holder, complete_fields)
    assert (result["outcome"], result["reason"]) == ("completed", "completed")
    assert "audit_path" not in result
    assert "could not be saved" in result["audit_error"]
    assert result["audit_error"] in api.stages[-1]
    assert "SYNTHETIC-CMS-SECRET" not in caplog.text


def test_same_minute_unique_files(tmp_path, monkeypatch, complete_fields):
    api, holder = setup(tmp_path, monkeypatch)
    first = run(api, holder, complete_fields)
    second = run(api, holder, complete_fields)
    assert first["audit_path"] != second["audit_path"]
    assert saved(first)["record_id"] != saved(second)["record_id"]
    assert len(list((tmp_path / "audit").glob("*.json"))) == 2
    assert not list((tmp_path / "audit").glob("*.tmp"))


def test_repository_override_falls_back_visibly(tmp_path, monkeypatch, complete_fields):
    api, holder = setup(tmp_path, monkeypatch)
    repo = Path(__file__).resolve().parents[2]
    monkeypatch.setenv(audit.ENV_DIRECTORY, str(repo / "Output" / "audit"))
    result = run(api, holder, complete_fields)
    assert result["outcome"] == "completed"
    assert "fallback" in result["referral_notice"]
    assert not Path(result["referral_path"]).is_relative_to(repo)


def test_git_worktree_override_falls_back_visibly(tmp_path, monkeypatch, complete_fields):
    api, holder = setup(tmp_path, monkeypatch)
    worktree = tmp_path / "another-worktree"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: synthetic", encoding="utf-8")
    monkeypatch.setenv(audit.ENV_DIRECTORY, str(worktree / "audit"))
    result = run(api, holder, complete_fields)
    assert result["outcome"] == "completed"
    assert "fallback" in result["referral_notice"]
    assert not Path(result["referral_path"]).is_relative_to(worktree)


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
    assert record["ai_extracted"]["First Name"] == "[redacted]"


def test_live_factory_failure_is_recorded_on_worker_without_live_calls(tmp_path, monkeypatch):
    import threading
    from finalcode.api import FinalCodeAPI
    from finalcode import api as api_module
    entered = threading.Event()
    released = threading.Event()
    def broken_factory(*args, **kwargs):
        assert threading.current_thread() is not threading.main_thread()
        entered.set()
        assert released.wait(5)
        raise RuntimeError("Synthetic construction failure")
    monkeypatch.setattr(api_module, "build_live_callables", broken_factory)
    api = FinalCodeAPI()
    assert api.start_attended()["ok"]
    assert entered.wait(5)
    assert api.get_state()["value"]["workflow_active"] is True
    released.set()
    import time
    deadline = time.monotonic() + 5
    while api.get_state()["value"]["workflow_active"] and time.monotonic() < deadline:
        time.sleep(.01)
    result = api.get_state()["value"]["workflow_result"]
    assert result["reason"] == "launcher_error"
    data = saved(result)
    assert [item["reason"] for item in data["saves"]] == ["run_end"]
    assert data["run_end"]["error"] == {"stage": "LAUNCHER", "type": "RuntimeError"}
