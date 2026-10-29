"""Pure attended CEM controller. Importing it never opens a browser."""
from dataclasses import asdict
import importlib.util
from pathlib import Path
import re
import sys


def _sibling(filename, name):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
        if spec is None or spec.loader is None:
            raise ImportError("CEM module unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules[name]

C = _sibling("contract.py", "_cem_contract")
R = _sibling("cem_rules.py", "_cem_rules")


def _safe_error(exc, stage):
    # Exception text can contain a URL/token/claim; never copy arbitrary exception text.
    return dict(stage=stage, type=type(exc).__name__, message="CEM operation failed; inspect locally without resubmitting.")


def run(request, *, stages, settings, on_stage=None, on_step=None):
    """Call only after explicit operator Start; no retries around submit."""
    result = C.new_result()
    submit_called = False

    def begin(stage):
        result["stage"] = stage
        if on_stage:
            on_stage(stage)

    def done():
        result["stages"].append(result["stage"])

    def step(name, status="done", detail=""):
        item = C.StepResult(name, status, detail)
        result["steps"].append(asdict(item))
        if on_step:
            on_step(item)

    def stop(reason, outcome="stopped"):
        result.update(outcome=outcome, reason=reason)
        return result

    def duplicate():
        # Both sources must be accessible; a lookup exception must not be treated as no duplicate.
        return bool(stages.find_log_duplicate(request, settings) or
                    stages.find_existing_request(request, settings))

    try:
        begin("START")
        problems = request.validate()
        if problems:
            result["problems"] = list(problems)
            return stop("invalid_request")
        if (settings.environment not in ("uat", "production") or
                not settings.employer_search_url or not settings.employer_add_url or
                not settings.cem_log_path or
                any(not str(url).startswith("https://") for url in
                    (settings.employer_search_url, settings.employer_add_url))):
            return stop("configuration_required")
        done()
        begin("VERIFY_SOURCE")
        address, reason = R.address_values(request, settings)
        if reason:
            return stop(reason)
        step("source_and_address")
        done()
        begin("SEARCH")
        match = R.classify_employer(stages.search_employer(request, settings), request.employer_name)
        if match != "new":
            return stop(match)
        if duplicate():
            return stop("duplicate_request")
        step("employer_and_duplicate_search")
        done()
        begin("REVIEW")
        filled = stages.fill_form(request, address, settings)
        if not isinstance(filled, dict) or R.normalize_name(filled.get("employer_name")) != R.normalize_name(request.employer_name):
            return stop("form_not_verified")
        if not R.bill_to_verified(filled):
            return stop("bill_to_unverified")
        if any(str(filled.get(key) or "").strip().casefold() != str(value).strip().casefold()
               for key, value in address.items()):
            return stop("form_not_verified")
        step("form_readback")
        if stages.review(request, filled, settings) is not True:
            return stop("operator_cancelled", "cancelled")
        step("operator_review")
        done()
        begin("SUBMIT")
        if stages.confirm_submit(request, filled, settings) is not True:
            return stop("submit_declined", "cancelled")
        step("submit_confirmation")
        if duplicate():
            return stop("duplicate_request")
        # Recheck immediately precedes the one and only irreversible call.
        submit_called = True
        try:
            submitted = stages.submit(request, settings)
        except (Exception, SystemExit):
            result["request_status"] = "unknown"
            result["warning"] = "Submit may have taken effect. Reconcile in portal; do not resubmit."
            return stop("submit_uncertain")
        if submitted is not True:
            result["request_status"] = "unknown"
            result["warning"] = "Submit result uncertain. Reconcile in portal; do not resubmit."
            return stop("submit_uncertain")
        # Even a positive click response is not proof of persistence.
        result["request_status"] = "unknown"
        step("submit_clicked")
        done()
        begin("VERIFY_RECEIPT")
        receipt = stages.read_back_request(request, settings)
        if not R.receipt_valid(receipt, request):
            result["warning"] = "Submit may have taken effect. Reconcile in portal; do not resubmit."
            return stop("receipt_not_found", "failed")
        reference = receipt["reference"].strip()
        if reference.startswith(("=", "+", "-", "@")):
            result["warning"] = "Submit may have taken effect. Reconcile in portal; do not resubmit."
            return stop("receipt_not_found", "failed")
        result["request_status"] = "submitted"
        result["request_reference"] = reference
        step("request_readback")
        done()
        begin("TRACK")
        try:
            tracking = stages.record(request, result["request_reference"], settings)
            if not isinstance(tracking, dict) or tracking.get("status") not in ("written", "existing") or not tracking.get("row"):
                raise ValueError("Tracking not verified")
            result["tracking_status"] = tracking["status"]
            result["cem_log_row"] = tracking["row"]
        except (Exception, SystemExit) as exc:
            result["tracking_status"] = "failed"
            result["warning"] = "Request submitted; tracking failed. Reconcile manually; do not resubmit."
            result["error"] = _safe_error(exc, "TRACK")
            return stop("tracking_failed_after_submit", "failed")
        step("tracking_readback")
        done()
        return stop("request_submitted", "completed")
    except (Exception, SystemExit) as exc:
        result["error"] = _safe_error(exc, result["stage"])
        if submit_called and result["request_status"] != "submitted":
            result["request_status"] = "unknown"
            result["warning"] = "Submit may have taken effect. Reconcile in portal; do not resubmit."
        return stop("exception", "failed")

run_flow = run
