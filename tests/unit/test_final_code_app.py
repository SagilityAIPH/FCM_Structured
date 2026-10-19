"""Launcher wiring contracts. Synthetic only; no desktop, window or network."""
from pathlib import Path
import subprocess
import sys
import threading

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Final Code"))
from finalcode import app

ROOT = Path(__file__).resolve().parents[2]


class ReviewApi:
    """Minimal stand-in for the bridge surface make_review() drives."""

    def __init__(self, answer, *, fail_import=False):
        self.answer, self.fail_import, self.calls = answer, fail_import, []

    def import_text(self, name, text):
        self.calls.append(("import_text", name, text))
        if self.fail_import:
            return {"ok": False, "error": "Synthetic import failure"}
        return {"ok": True, "value": "doc-1"}

    def start_processing(self, identifiers, *, prepared_fields=None):
        self.calls.append(("start_processing", list(identifiers), prepared_fields))
        return {"ok": True, "value": True}

    def wait_for_review(self, identifier):
        self.calls.append(("wait_for_review", identifier))
        return self.answer


class WorkflowApi:
    """Records what the launcher publishes, and when."""

    def __init__(self):
        self._workflow_active = False
        self.active_during_run = None
        self.results, self.stages = [], []

    def set_workflow_result(self, result):
        self.results.append(result)
        return {"ok": True, "value": True}

    def set_stage(self, stage, done=None, total=None):
        self.stages.append(stage)
        self.active_during_run = self._workflow_active
        return {"ok": True, "value": stage}


def test_import_pulls_in_no_heavy_dependencies():
    script = ("import sys; sys.path.insert(0, 'Final Code'); from finalcode import app; "
              "names=('pywinauto','selenium','pyodbc','boto3','webview'); "
              "assert not any(n in sys.modules for n in names), [n for n in names if n in sys.modules]; "
              "print('pure')")
    done = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert "pure" in done.stdout


def test_bootstrap_paths_adds_root_src_and_final_code(tmp_path):
    original = list(sys.path)
    try:
        app.bootstrap_paths(tmp_path)
        for expected in (tmp_path, tmp_path / "src", tmp_path / "Final Code"):
            assert str(expected) in sys.path
    finally:
        sys.path[:] = original


def test_review_shows_prepared_fields_then_returns_operator_edits():
    """The extract stage already paid for Bedrock; review must not re-extract."""
    holder = app.CaptureHolder()
    holder.record({"attachment_name": "Synthetic, Referral.pdf", "document_text": "Synthetic text"})
    edited = {"First Name": "Synthetic"}
    api = ReviewApi(edited)
    assert app.make_review(api, holder)({"First Name": "Extracted"}) is edited
    assert api.calls[0] == ("import_text", "Synthetic, Referral.pdf", "Synthetic text")
    assert api.calls[1] == ("start_processing", ["doc-1"], {"First Name": "Extracted"})
    assert api.calls[2] == ("wait_for_review", "doc-1")


def test_review_cancel_returns_none_so_orchestrator_ends_the_run():
    api = ReviewApi(None)
    assert app.make_review(api, app.CaptureHolder())({}) is None


def test_cancelled_review_handoff_ends_orchestrator_without_downstream_calls():
    from AI.workbench.backend import WorkbenchAPI
    from finalcode import orchestrator
    from tests.unit.test_referral_schema import complete_payload
    from AI.workbench import backend
    import json
    import time

    api = WorkbenchAPI(memory_only=True)
    fields = backend.core.force_exact_field_output(json.dumps(complete_payload()))[1]
    holder = app.CaptureHolder()
    called = []
    outcome = {}
    thread = threading.Thread(target=lambda: outcome.update(result=orchestrator.run(
        capture=app.make_capture(lambda: {'attachment_name': 'synthetic.txt',
                                           'document_text': 'Synthetic captured text.'}, holder),
        extract=lambda text: fields, review=app.make_review(api, holder),
        cms=lambda _: called.append('CMS'), subject_line=lambda _: called.append('SLB'))), daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    review = None
    try:
        while time.monotonic() < deadline:
            review = api.get_state()['value']['pending_review']
            if review:
                break
            time.sleep(.01)
        assert review and thread.is_alive()
        assert api.answer_review(review['id'], False)['ok']
    finally:
        if review:
            api.answer_review(review['id'], False)
    thread.join(5)
    assert not thread.is_alive()
    assert outcome['result']['outcome'] == 'ended'
    assert outcome['result']['reason'] == 'operator_cancelled'
    assert outcome['result']['stages'] == ['CAPTURE', 'EXTRACT', 'REVIEW']
    assert called == []
    assert api.get_state()['value']['pending_review'] is None


def test_review_raises_the_redacted_bridge_error():
    api = ReviewApi(None, fail_import=True)
    with pytest.raises(RuntimeError, match="Synthetic import failure"):
        app.make_review(api, app.CaptureHolder())({})


def test_capture_holder_defaults_survive_a_nameless_capture():
    holder = app.CaptureHolder()
    holder.record({"attachment_name": None, "document_text": None})
    assert (holder.name, holder.text) == ("Referral capture", "")


def test_workflow_publishes_result_and_clears_active_flag():
    api = WorkflowApi()
    result = {"outcome": "completed", "reason": "completed"}

    def runner(**kwargs):
        assert api._workflow_active is True
        kwargs["on_stage"]("CAPTURE")
        return result

    published = app.run_workflow(api, capture=None, extract=None, review=None, cms=None,
                                 subject_line=None, run=runner)
    assert published is result
    assert api.results == [None, result]
    assert api.stages == ["CAPTURE"]
    assert api.active_during_run is True
    assert api._workflow_active is False


def test_launcher_bug_still_publishes_a_failed_result():
    """Without this the window would sit on a stage that never resolves."""
    api = WorkflowApi()

    def runner(**kwargs):
        raise RuntimeError("Synthetic wiring bug")

    result = app.run_workflow(api, capture=None, extract=None, review=None, cms=None,
                              subject_line=None, run=runner)
    assert (result["outcome"], result["reason"]) == ("failed", "launcher_error")
    assert result["error"] == {"stage": "LAUNCHER", "type": "RuntimeError",
                               "message": "Synthetic wiring bug"}
    assert api._workflow_active is False
    assert api.results[-1] is result


def test_workflow_runs_off_the_ui_thread():
    api, seen = WorkflowApi(), {}

    def runner(**kwargs):
        seen["main"] = threading.current_thread() is threading.main_thread()
        return {"outcome": "completed", "reason": "completed"}

    thread = app.start_workflow(api, dict(capture=None, extract=None, review=None,
                                          cms=None, subject_line=None), run=runner)
    thread.join(timeout=10)
    assert thread.daemon is True
    assert seen["main"] is False


def test_self_test_drives_the_whole_chain_through_a_real_blocking_review():
    """Covers the one deadlock-capable path: a worker parked in wait_for_review
    while the poller keeps reading get_state()."""
    summary = app.self_test()
    assert summary["outcome"] == "completed"
    assert summary["stages"] == summary["executed"] == ["CAPTURE", "EXTRACT", "REVIEW",
                                                        "GATE", "CMS", "SUBJECT LINE BUILDER"]
    assert summary["customer"] == "SYNTHETIC EMPLOYER"
    assert summary["published"] is True
    assert summary["workflow_active_cleared"] is True


def test_self_test_entry_point_reports_and_exits_zero(tmp_path):
    report = tmp_path / "selftest.json"
    assert app.main(["--self-test", "--report", str(report)]) == 0
    assert '"outcome": "completed"' in report.read_text(encoding="utf-8")


def test_launch_waits_for_operator_even_after_frontend_loaded(monkeypatch):
    from AI.workbench import launcher
    captured = {}

    def fake_window(**kwargs):
        captured.update(kwargs)
        if kwargs.get("on_loaded"):
            kwargs["on_loaded"]()

    monkeypatch.setattr(launcher, "launch_window", fake_window)
    monkeypatch.setattr(app, "build_live_callables", lambda *a, **k: pytest.fail("built before Start"))
    api = app.launch()
    assert captured["api"] is api
    assert "on_loaded" not in captured
    assert api.get_state()["value"]["stage"] == "Waiting for Start"
    assert api.get_state()["value"]["workflow_active"] is False


def test_operator_start_runs_injected_chain_and_rejects_concurrent_start(monkeypatch):
    from finalcode.api import FinalCodeAPI
    entered, release = threading.Event(), threading.Event()
    calls = []

    def capture():
        calls.append("CAPTURE")
        entered.set()
        assert release.wait(timeout=10)
        return {}

    fake = dict(capture=capture, extract=lambda text: calls.append("EXTRACT"),
                review=lambda fields: calls.append("REVIEW"), cms=lambda fields: calls.append("CMS"),
                subject_line=lambda fields: calls.append("SUBJECT LINE BUILDER"))
    def runner(**kwargs):
        for name in ("capture", "extract", "review", "cms", "subject_line"):
            kwargs[name](None) if name != "capture" else kwargs[name]()
        return {"outcome": "completed", "reason": "completed", "stages": list(calls)}

    from finalcode import orchestrator
    monkeypatch.setattr(orchestrator, "run", runner)
    monkeypatch.setattr("finalcode.api.build_live_callables", lambda api, **kwargs: fake)
    api = FinalCodeAPI()
    assert api.start_attended() == {"ok": True, "value": True}
    assert entered.wait(timeout=10)
    try:
        assert api.get_state()["value"]["workflow_active"] is True
        assert api.start_attended() == {"ok": False, "error": "The attended run is already active."}
        assert calls == ["CAPTURE"]
    finally:
        release.set()
    # Poll the published result instead of assuming the worker finished as soon as capture returns.
    import time
    end = time.monotonic() + 10
    while api.get_state()["value"]["workflow_result"] is None and time.monotonic() < end:
        time.sleep(.01)
    state = api.get_state()["value"]
    assert state["workflow_result"]["outcome"] == "completed"
    end = time.monotonic() + 10
    while api.get_state()["value"]["workflow_active"] and time.monotonic() < end:
        time.sleep(.01)
    assert api.get_state()["value"]["workflow_active"] is False
    assert calls == ["CAPTURE", "EXTRACT", "REVIEW", "CMS", "SUBJECT LINE BUILDER"]


def test_reader_api_has_no_attended_entry_point():
    from AI.workbench.backend import WorkbenchAPI
    api = WorkbenchAPI(memory_only=False)
    state = api.get_state()["value"]
    assert state["memory_only"] is False
    assert state["pending_review"] is None
    assert "workflow_active" not in state
    assert not hasattr(api, "start_attended")
