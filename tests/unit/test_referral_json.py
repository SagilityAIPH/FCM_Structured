"""Synthetic records only; no documents or existing referral records are read."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys

import pytest

from AI import referral_json as store
from AI.referral_schema import ReferralFields


@pytest.fixture
def environment(tmp_path, monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = cls(2026, 10, 24, 12, 34, 56, tzinfo=timezone.utc)
            return instant.astimezone(tz) if tz else instant
    monkeypatch.setattr(store, "datetime", FixedDateTime)
    monkeypatch.delenv("FCM_REFERRALS_DIR", raising=False)
    monkeypatch.delenv("FCM_FINAL_CODE_AUDIT_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "installed" / "Synthetic.exe"))
    return tmp_path


def fields(first="Synthetic", last="Example"):
    return ReferralFields({"First Name": first, "Last Name": last, "Zip": "00000"},
                          [{"Provider City": "Synthetic City", "Provider Phone": "000-000-0000"}])


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("app", ["FinalCode", "AIPDFReader"])
def test_both_apps_write_schema_version_two(environment, app):
    assert store.SCHEMA_VERSION == 2
    path = store.ReferralRecord(app).save("after_extraction", ai_extracted=fields())
    assert read(path)["schema_version"] == 2


def test_frozen_creates_next_to_exe_folder_and_all_save_points_reuse_file(environment):
    record = store.ReferralRecord("FinalCode")
    original = fields()
    first = record.save("after_extraction", ai_extracted=original, model_id="synthetic-model",
                        captured_characters=123, sent_characters=100)
    assert first.parent == environment / "installed" / "Referrals"
    assert re.fullmatch(r"\d{4}-\d\d-\d\d_\d{6}_Example-Synthetic.json", first.name)
    original["Zip"] = "11111"
    for reason in ("save_changes", "complete", "run_end"):
        assert record.save(reason, current=original) == first
    data = read(first)
    assert [save["reason"] for save in data["saves"]] == ["after_extraction", "save_changes", "complete", "run_end"]
    assert all(save["at_local"] and save["at_utc"].endswith("+00:00") for save in data["saves"])
    assert data["ai_extracted"]["Zip"] == "00000"
    assert data["current"]["Zip"] == "11111"
    assert data["captured_characters"] == 123 and data["sent_characters"] == 100
    assert record.notice == "Saved Referrals\\" + first.name
    assert list(first.parent.glob("*.tmp")) == []


def test_rename_preserves_timestamp_original_and_one_record(environment):
    record = store.ReferralRecord("AIPDFReader")
    first = record.save("after_extraction", ai_extracted=fields(), source_file_name=r"C:\synthetic\source.pdf",
                        reader_status="Needs Review")
    edited = fields("Changed", "Revised")
    second = record.save("save_changes", current=edited, reader_status="Completed")
    assert second != first and not first.exists()
    assert second.name[:18] == first.name[:18]
    assert second.name.endswith("Revised-Changed.json")
    data = read(second)
    assert data["ai_extracted"]["First Name"] == "Synthetic"
    assert data["current"]["First Name"] == "Changed"
    assert data["source_file_name"] == "source.pdf"
    assert data["status"] == "Completed"
    assert "run_end" not in data and "captured_characters" not in data
    assert len(list(second.parent.glob("*.json"))) == 1


def test_collisions_never_clobber_another_referral_including_rename(environment):
    a, b, c = [store.ReferralRecord("FinalCode") for _ in range(3)]
    pa, pb = a.save("after_extraction", current=fields()), b.save("after_extraction", current=fields())
    assert pa != pb
    assert pb.name.endswith("_2.json")
    pc = c.save("after_extraction", current=fields())
    assert pc.name.endswith("_3.json")
    assert a.save("save_changes", current=fields()) == pa
    b.save("save_changes", current=fields("Other", "Name"))
    assert b.save("save_changes", current=fields()) == pb
    assert read(pa)["record_id"] == a.record_id
    assert read(pc)["record_id"] == c.record_id


def test_concurrent_first_save_uses_exclusive_names(environment):
    records = [store.ReferralRecord("AIPDFReader") for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        paths = list(pool.map(lambda record: record.save("after_extraction", current=fields()), records))
    assert None not in paths and len(set(paths)) == 8
    assert {read(path)["record_id"] for path in paths} == {record.record_id for record in records}


def test_existing_owned_path_replaced_by_other_id_is_not_clobbered(environment):
    record = store.ReferralRecord("FinalCode")
    first = record.save("after_extraction", current=fields())
    first.write_text('{"record_id": "another-synthetic-record"}', encoding="utf-8")
    second = record.save("save_changes", current=fields())
    assert second != first
    assert read(first) == {"record_id": "another-synthetic-record"}


@pytest.mark.parametrize("first,last,expected", [
    ("Not found", "", "Unknown-Claimant"),
    ("Zoë \u200bTest", "O’Example,\x00<Last>", "OExampleLast-Zoë-Test"),
    ("A'B\"C", 'D/E\\F:*?|', "DEF-ABC"),
    ("X" * 80, "Y" * 80, "Y" * 60),
])
def test_name_sanitization_unknown_unicode_and_cap(environment, first, last, expected):
    path = store.ReferralRecord("FinalCode").save("after_extraction", current=fields(first, last))
    assert path.name[18:-5] == expected


@pytest.mark.parametrize("app", ["FinalCode", "AIPDFReader"])
def test_source_run_fallback_visible(environment, monkeypatch, app):
    monkeypatch.delattr(sys, "frozen")
    record = store.ReferralRecord(app)
    path = record.save("after_extraction", current=fields())
    assert path.parent == environment / "local" / "FCM_Structured" / app / "Referrals"
    assert str(path) in record.notice and "fallback: source run" in record.notice


@pytest.mark.parametrize("git_marker", ["directory", "file"])
def test_git_worktree_exe_falls_back_for_git_directory_or_file(environment, git_marker):
    installed = environment / "installed"
    installed.mkdir()
    if git_marker == "directory":
        (installed / ".git").mkdir()
    else:
        (installed / ".git").write_text("gitdir: synthetic", encoding="utf-8")
    record = store.ReferralRecord("FinalCode")
    path = record.save("after_extraction", current=fields())
    assert path.parent == environment / "local" / "FCM_Structured" / "FinalCode" / "Referrals"
    assert "Git worktree" in record.notice
    assert not (installed / "Referrals").exists()


@pytest.mark.parametrize("env_name", ["FCM_REFERRALS_DIR", "FCM_FINAL_CODE_AUDIT_DIR"])
def test_absolute_override_and_final_code_alias(environment, monkeypatch, env_name):
    target = environment / "override"
    monkeypatch.setenv(env_name, str(target))
    record = store.ReferralRecord("FinalCode")
    assert record.save("after_extraction", current=fields()).parent == target


def test_new_override_precedes_alias_and_reader_ignores_alias(environment, monkeypatch):
    monkeypatch.setenv("FCM_FINAL_CODE_AUDIT_DIR", str(environment / "alias"))
    reader = store.ReferralRecord("AIPDFReader")
    assert reader.save("after_extraction", current=fields()).parent == environment / "installed" / "Referrals"
    monkeypatch.setenv("FCM_REFERRALS_DIR", str(environment / "override"))
    assert store.ReferralRecord("FinalCode").save("after_extraction", current=fields()).parent == environment / "override"


@pytest.mark.parametrize("kind", ["relative", "git"])
def test_invalid_override_falls_back_with_warning(environment, monkeypatch, kind):
    target = environment / "repo"
    target.mkdir()
    (target / ".git").write_text("gitdir: synthetic", encoding="utf-8")
    monkeypatch.setenv("FCM_REFERRALS_DIR", "relative/path" if kind == "relative" else str(target / "nested"))
    record = store.ReferralRecord("AIPDFReader")
    path = record.save("after_extraction", current=fields())
    assert path.parent == environment / "local" / "FCM_Structured" / "AIPDFReader" / "Referrals"
    assert "fallback: invalid or Git-contained override" in record.notice


def test_unwritable_exe_falls_back_and_all_failure_is_nonfatal(environment, monkeypatch):
    real = store.ReferralRecord._write
    def no_exe(self, directory, record, stamp):
        if directory.parent == environment / "installed":
            raise PermissionError("synthetic failure")
        return real(self, directory, record, stamp)
    monkeypatch.setattr(store.ReferralRecord, "_write", no_exe)
    record = store.ReferralRecord("FinalCode")
    assert record.save("after_extraction", current=fields()) is not None
    assert "unwritable" in record.notice
    monkeypatch.setattr(store.ReferralRecord, "_write", lambda *args: (_ for _ in ()).throw(PermissionError("SECRET")))
    assert record.save("save_changes", current=fields()) is None
    assert "Warning" in record.notice and "SECRET" not in record.notice
    assert record.error


def test_atomic_failure_preserves_previous_valid_record_and_cleans_temp(environment, monkeypatch):
    monkeypatch.delattr(sys, "frozen")
    record = store.ReferralRecord("FinalCode")
    path = record.save("after_extraction", current=fields())
    before = path.read_bytes()
    monkeypatch.setattr(os, "replace", lambda *args: (_ for _ in ()).throw(PermissionError("synthetic")))
    assert record.save("save_changes", current=fields()) is None
    assert path.read_bytes() == before
    assert not list(path.parent.glob("*.tmp"))


def test_secret_name_redacted_and_later_credentials_redact_frozen_original(environment):
    record = store.ReferralRecord("FinalCode")
    first = record.save("after_extraction", ai_extracted=fields("TOKEN", "Example"))
    second = record.save("save_changes", current=fields("TOKEN", "Example"), credentials=("TOKEN",))
    assert "TOKEN" not in second.name and not first.exists()
    assert "TOKEN" not in second.read_text(encoding="utf-8")
    assert read(second)["ai_extracted"]["First Name"] == "[redacted]"


def test_derived_fields_and_version_preserved(environment):
    value = fields()
    value["Body Part"] = "Synthetic body part"
    value["Injury Cause"] = "Synthetic injury cause"
    path = store.ReferralRecord("FinalCode").save("after_extraction", ai_extracted=value)
    assert read(path)["ai_extracted"]["Body Part"] == "Synthetic body part"
    assert read(path)["current"]["Injury Cause"] == "Synthetic injury cause"
    assert read(path)["app_version"] == "1.0.9"


def test_later_unwritable_exe_folder_falls_back(environment, monkeypatch):
    record = store.ReferralRecord("FinalCode")
    first = record.save("after_extraction", ai_extracted=fields())
    real = record._write
    def unavailable(directory, data, stamp):
        if directory == first.parent:
            raise PermissionError("synthetic")
        return real(directory, data, stamp)
    monkeypatch.setattr(record, "_write", unavailable)
    second = record.save("save_changes", current=fields())
    assert second.parent == environment / "local" / "FCM_Structured" / "FinalCode" / "Referrals"
    assert not first.exists()
    assert [item["reason"] for item in read(second)["saves"]] == ["after_extraction", "save_changes"]


def test_rename_cleanup_failure_reports_stale_filename_warning(environment, monkeypatch):
    record = store.ReferralRecord("FinalCode")
    first = record.save("after_extraction", ai_extracted=fields())
    real_unlink = Path.unlink
    def unavailable(path, *args, **kwargs):
        if path == first:
            raise PermissionError("synthetic")
        return real_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", unavailable)
    second = record.save("save_changes", current=fields("Revised", "Example"))
    assert second != first and second.exists() and first.exists()
    assert "warning: previous filename could not be removed" in record.notice
    assert record.error is None


def test_whitelist_redaction_provider_array_and_early_failure(environment):
    value = fields()
    value["raw_captured_text"] = "SYNTHETIC RAW TEXT"
    value["cms_payload"] = {"password": "SYNTHETIC SECRET"}
    value["Employer Name"] = "SYNTHETIC SECRET Customer"
    value["Provider Phone"] = "LEGACY FLAT PROVIDER"
    value.providers[0]["password"] = "SYNTHETIC SECRET"
    record = store.ReferralRecord("FinalCode", credentials=("SYNTHETIC SECRET",))
    path = record.save("run_end", ai_extracted=value, current=value,
        review_edits=[{"key": "Zip", "at": "synthetic", "before": "raw", "password": "secret"},
                      {"key": "password", "at": "secret"}],
        completeness={"status": "Failed", "missing_fields": ["Synthetic field"],
                      "provider_missing_fields": [["Appointment Date"]], "confirmation_required": [],
                      "appointments": [{"provider_index": 1, "date_only": True, "confirmed": False,
                                        "reasons": ["Synthetic confirmation"], "raw": "NO"}], "raw": "NO"},
        run_end={"started_at": "synthetic", "ended_at": "synthetic", "outcome": "failed", "reason": "exception",
                 "error": {"stage": "CAPTURE", "type": "RuntimeError", "message": "SYNTHETIC RAW TEXT"},
                 "stages": [{"name": "CAPTURE", "started_at": "synthetic", "ended_at": "synthetic", "outcome": "failed", "raw": "NO"}],
                 "cms": {"status": "failed", "reason": "failure", "customer": "SYNTHETIC SECRET Customer", "payload": "NO"},
                 "subject_line_builder": {"status": "stopped", "reason": "stopped", "raw": "NO"}, "payloads": "NO"})
    data, text = read(path), path.read_text(encoding="utf-8")
    assert "SYNTHETIC SECRET" not in text and "SYNTHETIC RAW TEXT" not in text
    assert "LEGACY FLAT PROVIDER" not in text and "password" not in text
    assert data["ai_extracted"]["Employer Name"] == "[redacted] Customer"
    assert "Provider Phone" not in data["current"]
    assert data["current"]["providers"] == [{"Provider Phone": "000-000-0000", "Provider City": "Synthetic City"}]
    assert data["review_edits"] == [{"field": "Zip", "provider_index": None, "changed": True, "at": "synthetic"}]
    assert data["run_end"]["error"] == {"stage": "CAPTURE", "type": "RuntimeError"}
    assert data["completeness"]["provider_missing_fields"] == [["Appointment Date"]]


def test_multiple_reader_documents_independent_and_no_workbook_changes(environment):
    workbook = environment / "synthetic.xlsx"
    workbook.write_bytes(b"synthetic workbook sentinel")
    a, b = store.ReferralRecord("AIPDFReader"), store.ReferralRecord("AIPDFReader")
    pa = a.save("after_extraction", ai_extracted=fields(), source_file_name="synthetic-a.pdf")
    pb = b.save("after_extraction", ai_extracted=fields("Another", "Example"), source_file_name="synthetic-b.pdf")
    assert a.save("save_changes", current=fields()) == pa
    assert read(pa)["source_file_name"] == "synthetic-a.pdf"
    assert read(pb)["source_file_name"] == "synthetic-b.pdf"
    assert len(read(pb)["saves"]) == 1
    assert workbook.read_bytes() == b"synthetic workbook sentinel"


@pytest.mark.parametrize("app", ["FinalCode", "AIPDFReader"])
def test_full_source_and_differing_sent_text_frozen_through_save_and_rename(environment, app):
    source = ("Synthetic full source – Zoë 漢字\nSecond synthetic line\n" * 8000) + "END OF SYNTHETIC SOURCE"
    sent = "Synthetic selected model input\nUnicode: 漢字\n"
    record = store.ReferralRecord(app)
    first = record.save("after_extraction", ai_extracted=fields(), source_text=source, sent_text=sent)
    assert read(first)["source_text"] == source
    assert read(first)["sent_text"] == sent
    assert len(read(first)["source_text"]) > 300000
    renamed = record.save("save_changes", current=fields("Renamed", "Example"),
                          source_text="replacement must not win", sent_text="replacement must not win")
    assert renamed != first and not first.exists()
    record.save("complete", current=fields("Renamed", "Example"))
    data = read(renamed)
    assert data["source_text"] == source and data["sent_text"] == sent
    assert [item["reason"] for item in data["saves"]] == ["after_extraction", "save_changes", "complete"]


def test_empty_source_is_frozen_and_identical_sent_input_is_optional(environment):
    record = store.ReferralRecord("FinalCode")
    early = record.save("run_end")
    assert read(early)["source_text"] is None and "sent_text" not in read(early)
    path = record.save("after_extraction", ai_extracted=fields(), source_text="", sent_text="")
    record.save("save_changes", current=fields(), source_text="do not replace empty", sent_text="do not replace empty")
    assert read(path)["source_text"] == "" and "sent_text" not in read(path)
    other = store.ReferralRecord("AIPDFReader")
    same = other.save("after_extraction", ai_extracted=fields(), source_text="Synthetic same", sent_text="Synthetic same")
    other.save("save_changes", sent_text="Synthetic different later")
    assert read(same)["source_text"] == "Synthetic same" and "sent_text" not in read(same)


def test_full_text_late_credentials_redacted_and_arbitrary_payloads_still_excluded(environment):
    record = store.ReferralRecord("FinalCode")
    value = fields()
    value["arbitrary_raw_text"] = "DISALLOWED SYNTHETIC RAW"
    value["cms_payload"] = {"password": "DISALLOWED SYNTHETIC PAYLOAD"}
    path = record.save("after_extraction", ai_extracted=value,
                       source_text="Synthetic full source\nLATE_SYNTHETIC_SECRET\n漢字",
                       sent_text="Synthetic model input LATE_SYNTHETIC_SECRET")
    assert "LATE_SYNTHETIC_SECRET" in read(path)["source_text"]
    record.save("run_end", credentials=("LATE_SYNTHETIC_SECRET",),
                run_end={"outcome": "completed", "reason": "completed",
                         "payloads": {"cms": "DISALLOWED SYNTHETIC PAYLOAD"},
                         "error": {"stage": "CMS", "type": "SyntheticError", "message": "DISALLOWED SYNTHETIC RAW"}})
    text, data = path.read_text(encoding="utf-8"), read(path)
    assert data["source_text"] == "Synthetic full source\n[redacted]\n漢字"
    assert data["sent_text"] == "Synthetic model input [redacted]"
    assert "LATE_SYNTHETIC_SECRET" not in text
    assert "DISALLOWED SYNTHETIC" not in text and "cms_payload" not in text
