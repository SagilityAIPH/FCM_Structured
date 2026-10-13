"""Synthetic-only end-to-end contracts; no desktop, database or network."""
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Final Code"))
from AI.referral_schema import REQUIRED_FIELDS, PROVIDER_FIELDS, force_exact_field_output, completeness
from finalcode import orchestrator as flow, live_wiring, field_adapter

TODAY = date(2030, 1, 2)


@pytest.fixture
def fields():
    data = {key: "Synthetic" for key in REQUIRED_FIELDS if key not in PROVIDER_FIELDS}
    provider = {key: "Synthetic" for key in PROVIDER_FIELDS}
    provider.update({"Appointment Date": "01/03/2030", "Appointment Time": "10:00 AM",
                     "Provider Phone": "202-555-0100", "Provider Zip": "00000"})
    data.update({"Provider Information": [provider], "Phone Number": "202-555-0100",
                 "Zip": "00000", "Claims Office Number": "Not found"})
    _, result = force_exact_field_output(json.dumps(data))
    # Explicit operator edits, via canonical keys, can repair deterministic classifications.
    for key in REQUIRED_FIELDS:
        if key not in PROVIDER_FIELDS and result.get(key) == "Not found":
            result[key] = "Synthetic"
    assert completeness(result, today=TODAY)["status"] == "Passed"
    return result


@pytest.fixture
def callbacks(fields):
    return dict(capture=Mock(return_value={"attachment_name": "Synthetic, Referral.pdf",
                                          "document_text": "Synthetic referral", "claimant_row_value": "Synthetic"}),
                extract=Mock(return_value=fields), review=Mock(side_effect=lambda f: f),
                cms=Mock(return_value={"status": "completed", "customer": "Synthetic Resolved Employer", "cases": []}),
                subject_line=Mock(return_value={"status": "completed"}),
                adapt=Mock(side_effect=lambda f, *, cms_customer: {"customer": cms_customer}),
                today=TODAY)


def test_happy_path_and_notifications(callbacks):
    events = []
    def notify(stage):
        events.append(stage)
        callback = {"CAPTURE": "capture", "EXTRACT": "extract", "REVIEW": "review",
                    "CMS": "cms", "SUBJECT LINE BUILDER": "subject_line"}.get(stage)
        if callback:
            callbacks[callback].assert_not_called()
    result = flow.run(**callbacks, on_stage=notify)
    assert result["outcome"] == result["reason"] == "completed"
    assert result["stages"] == events == list(flow.STAGES)
    callbacks["extract"].assert_called_once_with("Synthetic referral")
    assert result["payloads"]["REVIEW"]["providers"]
    assert json.loads(json.dumps(result)) == result


def test_no_referral(callbacks):
    callbacks["capture"].return_value["attachment_name"] = None
    result = flow.run(**callbacks)
    assert (result["outcome"], result["reason"], result["stages"]) == ("ended", "no_referral_attached", ["CAPTURE"])
    callbacks["extract"].assert_not_called()
    callbacks["cms"].assert_not_called()


def test_cancel(callbacks):
    callbacks["review"].side_effect = lambda f: None
    result = flow.run(**callbacks)
    assert (result["outcome"], result["reason"]) == ("ended", "operator_cancelled")
    assert result["stages"] == list(flow.STAGES[:3])
    callbacks["cms"].assert_not_called()


def test_incomplete_and_review_edits(callbacks):
    def edit(f):
        f["First Name"] = "Not found"
        return f
    callbacks["review"].side_effect = edit
    result = flow.run(**callbacks)
    assert (result["outcome"], result["reason"]) == ("ended", "incomplete")
    assert any("First Name" in x for x in result["missing_fields"])
    assert result["payloads"]["EXTRACT"]["First Name"] != "Not found"
    callbacks["cms"].assert_not_called()


def test_appointment_confirmation(callbacks):
    def edit(f):
        f.providers[0]["Appointment Date"] = "01/01/2030"
        return f
    callbacks["review"].side_effect = edit
    result = flow.run(**callbacks)
    assert result["reason"] == "incomplete"
    assert result["confirmation_required"] and result["appointments"]
    callbacks["cms"].assert_not_called()


@pytest.mark.parametrize("reason", ["tire_customer_open_tcm", "user_declined", "customer_unresolved_or_cem"])
def test_cms_stop(callbacks, reason):
    callbacks["cms"].return_value = {"status": "stopped", "reason": reason,
                                      "cases": [{"synthetic": True}], "customer": "Synthetic"}
    result = flow.run(**callbacks)
    assert (result["outcome"], result["reason"]) == ("stopped", reason)
    assert result["cases"] == [{"synthetic": True}]
    callbacks["subject_line"].assert_not_called()


def test_missing_cms_inputs(callbacks, monkeypatch):
    # Gate and CMS contracts differ; isolate blanks produced at the CMS mapping seam.
    monkeypatch.setattr(flow.cms_inputs, "to_cms_inputs", lambda f: {})
    result = flow.run(**callbacks)
    assert result["reason"] == "missing_cms_inputs"
    assert result["outcome"] == "failed"
    for key in ("claimNumber", "claimID", "customer", "claimantFull"):
        assert key in result["error"]["message"]
    callbacks["cms"].assert_not_called()


def test_resolved_customer_real_adapter(callbacks, monkeypatch):
    # Inject the adapter's only external effect, never open an office workbook.
    monkeypatch.setattr(field_adapter, "_load_office_matrix", lambda: SimpleNamespace(
        adjuster_addresses=lambda d: ("", ""), enrich_adjuster=lambda d: (d, [])))
    spy = Mock(wraps=field_adapter.to_all_data)
    monkeypatch.setattr(field_adapter, "to_all_data", spy)
    del callbacks["adapt"]
    result = flow.run(**callbacks)
    assert result["outcome"] == "completed"
    assert spy.call_args.kwargs == {"cms_customer": "Synthetic Resolved Employer"}
    assert callbacks["subject_line"].call_args.args[0]["customer"] == result["customer"]


@pytest.mark.parametrize("callback,stage", [("capture", "CAPTURE"), ("extract", "EXTRACT"),
    ("review", "REVIEW"), ("cms", "CMS"), ("subject_line", "SUBJECT LINE BUILDER"), ("adapt", "SUBJECT LINE BUILDER")])
def test_callback_exception(callbacks, callback, stage):
    callbacks[callback].side_effect = RuntimeError("Synthetic failure")
    result = flow.run(**callbacks)
    assert result["outcome"] == "failed"
    assert result["error"] == {"stage": stage, "type": "RuntimeError", "message": "Synthetic failure"}
    assert result["stages"][-1] == stage
    json.dumps(result)


def test_gate_exception(callbacks, monkeypatch):
    monkeypatch.setattr(flow, "completeness", Mock(side_effect=ValueError("Synthetic gate error")))
    assert flow.run(**callbacks)["error"]["stage"] == "GATE"


def test_notification_exception(callbacks):
    result = flow.run(**callbacks, on_stage=Mock(side_effect=RuntimeError("Synthetic notification error")))
    assert result["error"]["stage"] == "CAPTURE"
    callbacks["capture"].assert_not_called()


@pytest.mark.parametrize("status", ["completed", "stopped", "failed"])
def test_subject_line_outcomes(callbacks, status):
    callbacks["subject_line"].return_value = {"status": status, "error": "Synthetic"}
    result = flow.run(**callbacks)
    assert result["outcome"] == status
    assert result["payloads"]["SUBJECT LINE BUILDER"]["result"]["error"] == "Synthetic"


@pytest.mark.parametrize("response", [{"status": "unknown"}, {"status": "completed"},
    {"status": "completed", "customer": ""}, {"status": "completed", "customer": "Not found"}])
def test_invalid_cms_response(callbacks, response):
    callbacks["cms"].return_value = response
    result = flow.run(**callbacks)
    assert result["outcome"] == "failed"
    assert result["error"]["stage"] == "CMS"
    callbacks["subject_line"].assert_not_called()


def test_invalid_subject_line_status(callbacks):
    callbacks["subject_line"].return_value = {"status": "unknown"}
    assert flow.run(**callbacks)["error"]["stage"] == "SUBJECT LINE BUILDER"


def test_legacy_exit_contained(callbacks):
    callbacks["subject_line"].side_effect = SystemExit(3)
    assert flow.run(**callbacks)["error"]["type"] == "SystemExit"


def test_non_json_callback_rejected(callbacks):
    callbacks["capture"].return_value["unsupported"] = object()
    result = flow.run(**callbacks)
    assert result["outcome"] == "failed"
    json.dumps(result, allow_nan=False)


def test_import_purity():
    script = "import sys; sys.path.insert(0, 'Final Code'); from finalcode import orchestrator, live_wiring; " \
             "names=('pywinauto','selenium','pyodbc','boto3','webview'); " \
             "assert not any(n in sys.modules for n in names); print({n: n in sys.modules for n in names})"
    completed = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2],
                               capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_live_wiring_contracts(monkeypatch):
    import types
    events = []
    desktop = Mock()
    desktop.window.side_effect = lambda **kw: events.append(("window", kw)) or object()
    monkeypatch.setitem(sys.modules, "pywinauto", SimpleNamespace(Desktop=Mock(return_value=desktop)))
    run_live = Mock(return_value={"status": "completed"})
    monkeypatch.setitem(sys.modules, "fcm_intake.workflows.reopen_flow", SimpleNamespace(run_live=run_live))
    cms = live_wiring.make_cms(app="synthetic-app", notify="notify", confirm="confirm")
    cms({"synthetic": True})
    assert run_live.call_args.kwargs["stage"] == "all"
    run_flow = Mock(side_effect=lambda *a, **kw: events.append(("flow", kw)) or {"status": "completed"})
    monkeypatch.setitem(sys.modules, "fcm_intake.config", SimpleNamespace(PROJECT_ROOT=Path("synthetic")))
    monkeypatch.setitem(sys.modules, "fcm_intake.legacy_loader", SimpleNamespace(
        load_module_from_path=lambda *a: SimpleNamespace(run_flow=run_flow)))
    subject = live_wiring.make_subject_line(runtime={})
    assert events == []
    subject({"customer": "Synthetic"})
    subject({"customer": "Synthetic"})
    assert [e[0] for e in events] == ["window", "flow", "window", "flow"]
    assert events[0][1]["title"] == "Email Display"
    assert events[1][1]["skip_capture"] is events[1][1]["skip_cms"] is True
    assert events[1][1]["emaiDisplay"] is not events[3][1]["emaiDisplay"]


def test_extract_wiring(monkeypatch, fields):
    from contextlib import nullcontext
    reasoning = Mock(return_value=("formatted", fields, "raw", 0))
    monkeypatch.setitem(sys.modules, "AI.bedrock_core", SimpleNamespace(run_reasoning=reasoning))
    extract = live_wiring.make_extract(client_factory=lambda: nullcontext("synthetic-client"),
                                       model_id="synthetic-model", max_tokens=100)
    assert extract("Synthetic text") is fields
    assert reasoning.call_args.kwargs["validation_source_text"] == "Synthetic text"


def test_returned_subject_line_failure_carries_detail(callbacks):
    """run_flow converts a legacy sys.exit() into a RETURNED dict, so this - not
    a raised exception - is the usual production failure and must keep detail."""
    callbacks["subject_line"].return_value = {"status": "failed", "stage": "subject_line_builder",
                                              "error": "Synthetic bot stop", "exit_code": 3}
    result = flow.run(**callbacks)
    assert (result["outcome"], result["reason"]) == ("failed", "subject_line_failed")
    assert result["error"] == {"stage": "subject_line_builder", "exit_code": 3,
                               "message": "Synthetic bot stop"}


def test_sparse_returned_failure_invents_nothing(callbacks):
    callbacks["subject_line"].return_value = {"status": "failed"}
    result = flow.run(**callbacks)
    assert result["outcome"] == "failed"
    assert result["error"] == {}


def test_returned_cms_failure_carries_detail(callbacks):
    callbacks["cms"].return_value = {"status": "failed", "stage": "customer_check",
                                     "error": "Synthetic CMS failure"}
    result = flow.run(**callbacks)
    assert result["outcome"] == "failed"
    assert result["error"]["stage"] == "customer_check"
    assert result["error"]["message"] == "Synthetic CMS failure"
    callbacks["subject_line"].assert_not_called()


def test_raised_failure_detail_is_unchanged(callbacks):
    callbacks["subject_line"].side_effect = RuntimeError("Synthetic raise")
    assert flow.run(**callbacks)["error"] == {"stage": "SUBJECT LINE BUILDER",
                                              "type": "RuntimeError", "message": "Synthetic raise"}


def test_every_failed_outcome_carries_an_error_object(callbacks):
    """A red panel with no detail is the bug this guards against."""
    for mutate in (lambda: callbacks["subject_line"].__setattr__("return_value", {"status": "failed"}),
                   lambda: callbacks["cms"].__setattr__("return_value", {"status": "failed"}),
                   lambda: callbacks["extract"].__setattr__("side_effect", RuntimeError("Synthetic"))):
        mutate()
        result = flow.run(**callbacks)
        assert result["outcome"] == "failed"
        assert result["error"] is not None, result["reason"]
