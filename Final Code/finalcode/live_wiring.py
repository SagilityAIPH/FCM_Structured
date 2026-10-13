"""Explicit live factories, never invoked on import. No UI or business policy.

The launcher must put the repository root, src, and Final Code on sys.path.
Review and stage notifications belong to the caller's attended UI. Do not share
one legacy runtime/desktop across concurrent runs.
"""


def make_capture():
    from pywinauto import Desktop
    from .rrs_capture import capture

    def invoke():
        return capture(desktop=Desktop(backend="uia"))
    return invoke


def make_extract(*, client_factory, model_id, max_tokens, temperature=0.0):
    """client_factory returns the configured Bedrock client's context manager.

    Shared run_reasoning includes force_exact_field_output and its JSON retry;
    the full captured text is also its validation source. Credentials and model
    settings remain owned by the launcher, not this wiring module.
    """
    from AI.bedrock_core import run_reasoning

    def invoke(document_text):
        with client_factory() as client:
            _, fields, _, _ = run_reasoning(
                client, model_id, document_text, validation_source_text=document_text,
                max_tokens=max_tokens, temperature=temperature)
        return fields
    return invoke


def make_cms(*, app=None, notify=None, confirm=None):
    from fcm_intake.workflows.reopen_flow import run_live

    def invoke(data):
        return run_live(data, app=app, notify=notify, confirm=confirm, stage="all")
    return invoke


def make_subject_line(*, runtime, app=None):
    """runtime is the caller-owned legacy module namespace (not a UI handle)."""
    from pywinauto import Desktop
    from fcm_intake.config import PROJECT_ROOT
    from fcm_intake.legacy_loader import load_module_from_path

    flow = load_module_from_path(
        "finalcode_subject_line_flow",
        PROJECT_ROOT / "Processes" / "SubjectLineBuilder" / "Deploy-Ready" / "subject_line_flow.py")

    def invoke(all_data):
        # Re-acquire by title NOW: review may have lasted minutes and the operator
        # may have navigated elsewhere in RRS; a pre-review handle is unsafe.
        email_display = Desktop(backend="uia").window(
            title="Email Display", control_type="Window")
        return flow.run_flow(runtime, app=app, allData=all_data,
                             emaiDisplay=email_display, skip_capture=True, skip_cms=True)
    return invoke
