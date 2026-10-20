"""Synthetic-only end-to-end contracts; no desktop, database or network."""
from datetime import date
import json
from pathlib import Path
import runpy
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


def test_shared_builder_original_failure_survives_orchestration(callbacks):
    root = Path(__file__).resolve().parents[2]
    run_flow = runpy.run_path(str(
        root / "Processes" / "SubjectLineBuilder" / "Deploy-Ready" / "subject_line_flow.py"))["run_flow"]
    namespace = {}
    source = '\n' * 838 + (
        'def legacy_failure(app=None):\n'
        '    try:\n'
        '        raise ValueError()\n'
        '    except Exception:\n'
        '        sys.exit()\n')
    exec(compile(source, 'legacy_steps.py', 'exec'), namespace)
    callbacks["subject_line"] = lambda _: run_flow({"sys": sys}, steps=namespace["legacy_failure"])
    result = flow.run(**callbacks)
    assert (result["outcome"], result["reason"]) == ("failed", "subject_line_failed")
    assert result["error"] == {"stage": "subject_line_builder", "type": "ValueError",
                               "message": "ValueError (legacy_steps.py:841)", "exit_code": None}
    json.dumps(result)


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


@pytest.mark.parametrize("runtime", [{}, {"synthetic": True}])
def test_live_wiring_contracts(monkeypatch, runtime):
    events = []
    desktop = Mock()
    desktop.window.side_effect = lambda **kw: events.append(("window", kw)) or object()
    monkeypatch.setitem(sys.modules, "pywinauto", SimpleNamespace(Desktop=Mock(return_value=desktop)))
    run_live = Mock(return_value={"status": "completed"})
    monkeypatch.setitem(sys.modules, "fcm_intake.workflows.reopen_flow", SimpleNamespace(run_live=run_live))
    cms = live_wiring.make_cms(app="synthetic-app", notify="notify", confirm="confirm")
    cms({"synthetic": True})
    assert run_live.call_args.kwargs["stage"] == "all"
    assert run_live.call_args.kwargs["show_customer_results"] is True
    run_flow = Mock(side_effect=lambda *a, **kw: events.append(("flow", kw)) or {"status": "completed"})
    complete_triage = Mock(side_effect=lambda data: events.append(("triage", data)))
    adapter = Mock(return_value=SimpleNamespace(complete_triage=complete_triage))
    monkeypatch.setitem(sys.modules, "fcm_intake.config", SimpleNamespace(PROJECT_ROOT=Path("synthetic")))
    def load(name, path):
        assert path == Path("synthetic") / "Processes" / "SubjectLineBuilder" / "Deploy-Ready" / (
            "subject_line_flow.py" if name == "finalcode_subject_line_flow" else "rrs_ui.py")
        if name == "finalcode_subject_line_flow":
            return SimpleNamespace(run_flow=run_flow)
        assert name == "finalcode_subject_line_rrs_ui"
        return SimpleNamespace(RRSAdapter=adapter)
    loader = Mock(side_effect=load)
    monkeypatch.setitem(sys.modules, "fcm_intake.legacy_loader", SimpleNamespace(
        load_module_from_path=loader))
    subject = live_wiring.make_subject_line(runtime=runtime, app="synthetic-app")
    assert events == []
    adapter.assert_not_called()
    all_data = {"customer": "Synthetic"}
    subject(all_data)
    subject({"customer": "Synthetic"})
    assert loader.call_count == 3  # Controller, then the adapter only after each completion.
    assert adapter.call_count == complete_triage.call_count == 2
    assert complete_triage.call_args_list[0].args[0] is all_data
    assert all(call.args[0] is runtime for call in run_flow.call_args_list)
    assert run_flow.call_args_list[0].kwargs["allData"] is all_data
    assert run_flow.call_args.kwargs["app"] == "synthetic-app"
    assert [e[0] for e in events] == ["window", "flow", "triage", "window", "flow", "triage"]
    assert events[0][1]["title"] == "Email Display"
    assert events[1][1]["skip_capture"] is events[1][1]["skip_cms"] is True
    assert events[1][1]["emaiDisplay"] is not events[4][1]["emaiDisplay"]


@pytest.fixture
def lazy_subject_runtime(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    controller_path = root / "Processes" / "SubjectLineBuilder" / "Deploy-Ready" / "subject_line_flow.py"
    run_flow = runpy.run_path(str(controller_path))["run_flow"]
    events = []
    desktop = Mock()
    desktop.window.side_effect = lambda **kw: events.append("window") or object()
    desktop_factory = Mock(return_value=desktop)
    monkeypatch.setitem(sys.modules, "pywinauto", SimpleNamespace(Desktop=desktop_factory))
    runtime_path = Path("synthetic_legacy_runtime.py")
    monkeypatch.setitem(sys.modules, "fcm_intake.config", SimpleNamespace(
        PROJECT_ROOT=root, FCM_SCRIPT=runtime_path))
    legacy = SimpleNamespace(synthetic_helper=Mock(return_value={"synthetic": True}),
                             synthetic_marker=object())

    def steps(*, app, allData, emaiDisplay, skip_capture, skip_cms):
        namespace = globals()
        namespace["data"] = namespace["synthetic_helper"](allData, namespace["synthetic_marker"])
        namespace["botStop"] = False

    controller = Mock(side_effect=lambda *args, **kwargs: run_flow(*args, steps=steps, **kwargs))
    complete_triage = Mock(side_effect=lambda data: events.append("triage") or ["Export -> OK"])
    adapter = Mock(return_value=SimpleNamespace(complete_triage=complete_triage))

    def load(name, path):
        if name == "finalcode_subject_line_flow":
            assert path == controller_path
            return SimpleNamespace(run_flow=controller)
        if name == "finalcode_subject_line_rrs_ui":
            assert path == controller_path.with_name("rrs_ui.py")
            return SimpleNamespace(RRSAdapter=adapter)
        assert (name, path) == ("standalone_subject_line_runtime", runtime_path)
        events.append("runtime")
        return legacy

    loader = Mock(side_effect=load)
    monkeypatch.setitem(sys.modules, "fcm_intake.legacy_loader", SimpleNamespace(
        load_module_from_path=loader))
    return SimpleNamespace(loader=loader, legacy=legacy, controller=controller,
                           desktop=desktop, desktop_factory=desktop_factory, events=events,
                           adapter=adapter, complete_triage=complete_triage)


def test_missing_runtime_is_loaded_only_at_subject_invocation(callbacks, lazy_subject_runtime):
    setup = lazy_subject_runtime
    subject = live_wiring.make_subject_line(runtime=None, app="synthetic-app")
    assert setup.loader.call_count == 1  # Factory loads the shared controller, not legacy_fcm.
    setup.desktop_factory.assert_not_called()
    callbacks["subject_line"] = subject
    original_review = callbacks["review"].side_effect
    callbacks["review"].side_effect = lambda f: None
    assert flow.run(**callbacks)["reason"] == "operator_cancelled"
    assert setup.loader.call_count == 1
    callbacks["review"].side_effect = original_review

    for _ in range(2):
        result = flow.run(**callbacks)
        assert result["outcome"] == "completed"
        assert result["payloads"]["SUBJECT LINE BUILDER"]["result"]["data"] == {"synthetic": True}
    assert setup.loader.call_count == 4  # Runtime once, adapter after each builder completion.
    assert setup.events == ["runtime", "window", "triage", "window", "triage"]
    assert setup.adapter.call_count == setup.complete_triage.call_count == 2
    calls = setup.controller.call_args_list
    assert all(call.args[0] is vars(setup.legacy) for call in calls)
    assert setup.legacy.synthetic_helper.call_count == 2
    for call, triage_call in zip(calls, setup.complete_triage.call_args_list):
        assert call.kwargs["allData"]["customer"] == "Synthetic Resolved Employer"
        assert triage_call.args[0] is call.kwargs["allData"]
        assert call.kwargs["app"] == "synthetic-app"
        assert call.kwargs["skip_capture"] is call.kwargs["skip_cms"] is True
    assert calls[0].kwargs["emaiDisplay"] is not calls[1].kwargs["emaiDisplay"]
    setup.desktop.window.assert_called_with(title="Email Display", control_type="Window")


def test_missing_runtime_loader_failure_surfaces_at_subject_line(callbacks, lazy_subject_runtime):
    setup = lazy_subject_runtime
    subject = live_wiring.make_subject_line(runtime=None)
    setup.loader.side_effect = ImportError("Synthetic runtime dependency unavailable")
    callbacks["subject_line"] = subject
    result = flow.run(**callbacks)
    assert (result["outcome"], result["reason"]) == ("failed", "exception")
    assert result["stages"][-1] == "SUBJECT LINE BUILDER"
    assert result["error"] == {"stage": "SUBJECT LINE BUILDER", "type": "ImportError",
                               "message": "Synthetic runtime dependency unavailable"}
    setup.desktop_factory.assert_not_called()
    setup.controller.assert_not_called()
    setup.adapter.assert_not_called()


@pytest.mark.parametrize("stop", ["no_attachment", "cancel", "incomplete", "cms_stopped",
                                 "cms_failed", "cms_unknown", "cms_unresolved"])
def test_triage_runtime_stays_lazy_before_subject_stage(callbacks, lazy_subject_runtime, stop):
    setup = lazy_subject_runtime
    callbacks["subject_line"] = live_wiring.make_subject_line(runtime=None)
    if stop == "no_attachment":
        callbacks["capture"].return_value["attachment_name"] = None
    elif stop == "cancel":
        callbacks["review"].side_effect = lambda f: None
    elif stop == "incomplete":
        callbacks["review"].side_effect = lambda f: f.__setitem__("First Name", "Not found") or f
    else:
        status = {"cms_stopped": "stopped", "cms_failed": "failed",
                  "cms_unknown": "unknown", "cms_unresolved": "completed"}[stop]
        callbacks["cms"].return_value = {"status": status, "customer": "", "cases": []}
    assert flow.run(**callbacks)["outcome"] != "completed"
    assert setup.loader.call_count == 1  # Pure controller only, no legacy runtime or UI adapter.
    setup.desktop_factory.assert_not_called()
    setup.controller.assert_not_called()
    setup.adapter.assert_not_called()
    setup.complete_triage.assert_not_called()


@pytest.mark.parametrize("response", [{"status": "stopped", "reason": "Synthetic stop"},
    {"status": "failed", "error": "Synthetic failure"}, {"status": "unknown"}, {}, None, "completed"])
def test_only_completed_builder_can_start_triage(callbacks, lazy_subject_runtime, response):
    setup = lazy_subject_runtime
    setup.controller.side_effect = None
    setup.controller.return_value = response
    callbacks["subject_line"] = live_wiring.make_subject_line(runtime=None)
    result = flow.run(**callbacks)
    assert result["outcome"] != "completed"
    assert setup.loader.call_count == 2  # Controller and legacy runtime, never the triage adapter.
    setup.adapter.assert_not_called()
    setup.complete_triage.assert_not_called()
    if isinstance(response, dict) and response.get("status") in ("stopped", "failed"):
        assert result["outcome"] == response["status"]
        assert result["payloads"]["SUBJECT LINE BUILDER"]["result"] == response
    else:
        assert result["error"]["stage"] == "SUBJECT LINE BUILDER"


def test_completion_waits_for_export_and_preserves_reviewed_data(callbacks, lazy_subject_runtime):
    setup = lazy_subject_runtime
    response = {"status": "completed", "data": {"synthetic": True}, "reason": "Synthetic complete"}
    events = []
    all_data = {"customer": "Synthetic Resolved Employer", "claimNumber": "TEST-REVIEWED"}
    callbacks["review"].side_effect = lambda f: f.__setitem__("Claim Number", "TEST-REVIEWED") or f

    def adapt(fields, *, cms_customer):
        assert fields["Claim Number"] == all_data["claimNumber"]
        assert cms_customer == all_data["customer"]
        events.append("adapt")
        return all_data

    def builder(*args, **kwargs):
        assert kwargs["allData"] is all_data
        events.append("builder")
        setup.complete_triage.assert_not_called()
        return response

    def export(data):
        assert data is all_data
        events.append("export")
        return ["Synthetic confirmation"]

    callbacks["adapt"].side_effect = adapt
    setup.controller.side_effect = builder
    setup.complete_triage.side_effect = export
    subject = live_wiring.make_subject_line(runtime=None)

    def subject_stage(data):
        result = subject(data)
        assert result is response
        assert events == ["adapt", "builder", "export"]
        events.append("returned")
        return result

    callbacks["subject_line"] = subject_stage
    result = flow.run(**callbacks)
    assert result["outcome"] == "completed"
    assert events == ["adapt", "builder", "export", "returned"]
    assert result["payloads"]["SUBJECT LINE BUILDER"] == {"all_data": all_data, "result": response}
    setup.controller.assert_called_once()
    setup.adapter.assert_called_once_with()
    setup.complete_triage.assert_called_once_with(all_data)


@pytest.mark.parametrize("failure", ["builder", "adapter_load", "adapter_init", "triage_export"])
def test_triage_boundary_errors_fail_subject_stage(callbacks, lazy_subject_runtime, failure):
    setup = lazy_subject_runtime
    subject = live_wiring.make_subject_line(runtime=None)
    error = RuntimeError("Synthetic triage boundary failure")
    if failure == "builder":
        setup.controller.side_effect = error
    elif failure == "adapter_load":
        original_load = setup.loader.side_effect
        def load(name, path):
            if name == "finalcode_subject_line_rrs_ui":
                raise error
            return original_load(name, path)
        setup.loader.side_effect = load
    elif failure == "adapter_init":
        setup.adapter.side_effect = error
    else:
        setup.complete_triage.side_effect = error
    callbacks["subject_line"] = subject
    result = flow.run(**callbacks)
    assert (result["outcome"], result["reason"]) == ("failed", "exception")
    assert result["stages"][-1] == "SUBJECT LINE BUILDER"
    assert result["error"] == {"stage": "SUBJECT LINE BUILDER", "type": "RuntimeError",
                               "message": str(error)}
    assert "result" not in result["payloads"]["SUBJECT LINE BUILDER"]
    if failure == "triage_export":
        setup.complete_triage.assert_called_once()
    else:
        setup.complete_triage.assert_not_called()


@pytest.mark.parametrize("credentials", [None, lambda: ("synthetic-user", "synthetic-secret")])
def test_cms_results_option_reaches_live_runner_with_or_without_credentials(monkeypatch, credentials):
    run_live = Mock(return_value={"status": "completed", "customer": "Synthetic Resolved"})
    set_credentials = Mock()
    monkeypatch.setitem(sys.modules, "fcm_intake.workflows.reopen_flow", SimpleNamespace(run_live=run_live))
    monkeypatch.setitem(sys.modules, "fcm_intake.cms.session", SimpleNamespace(
        set_credentials=set_credentials, CmsAuthenticationRejected=type("Rejected", (RuntimeError,), {})))
    data = {"customer": "Synthetic"}
    result = live_wiring.make_cms(credentials=credentials, show_customer_results=False)(data)
    assert result["customer"] == "Synthetic Resolved"
    run_live.assert_called_once_with(data, app=None, notify=None, confirm=None, stage="all",
                                    show_customer_results=False)
    if credentials is not None:
        assert set_credentials.call_args_list[-1].args == ("", "")


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
