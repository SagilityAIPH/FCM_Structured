"""Attended, synchronous state machine; no desktop, network or UI ownership.

review(fields) returns ReferralFields, or None to abandon. Callbacks may block.
Pass today for deterministic appointment checks and adapt for an entirely offline
run (the existing adapter's optional office lookup reads a reference workbook).
No run data is persisted. A UI should retain this result only in memory.
"""
from copy import deepcopy
from datetime import date, datetime
import json

from AI.referral_schema import completeness
from . import cms_inputs, field_adapter

STAGES = ("CAPTURE", "EXTRACT", "REVIEW", "GATE", "CMS", "SUBJECT LINE BUILDER")


def _snapshot(value):
    """Detach JSON payloads, retaining ReferralFields' lossless side metadata."""
    if isinstance(value, dict):
        result = {str(k): _snapshot(v) for k, v in value.items()}
        for key, item in vars(value).items() if hasattr(value, "__dict__") else ():
            result[key] = _snapshot(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_snapshot(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    # Reject unsupported callback values rather than inventing display strings.
    json.dumps(value, allow_nan=False)
    return value


def run(*, capture, extract, review, cms, subject_line, on_stage=None,
        today=None, adapt=None):
    """Return outcome/reason/stages/payloads, plus gate and CMS UI summaries.

    Only a completed CMS response with a nonblank resolved customer advances.
    Business endings and stops are not exceptions. Callback exceptions (including
    accidental SystemExit from legacy glue) are contained at the active stage;
    KeyboardInterrupt remains an intentional host interrupt.
    """
    result = {"outcome": None, "reason": None, "stages": [], "payloads": {},
              "missing_fields": [], "confirmation_required": [],
              "appointments": [], "cases": [], "customer": None}
    stage = None

    def start(name):
        nonlocal stage
        stage = name
        result["stages"].append(name)
        result["payloads"][name] = {}
        if on_stage is not None:
            on_stage(name)

    def finish(outcome, reason):
        result.update(outcome=outcome, reason=reason)
        return result

    def store(value):
        result["payloads"][stage] = _snapshot(value)

    try:
        start("CAPTURE")
        captured = capture()
        store(captured)
        if captured["attachment_name"] is None:
            return finish("ended", "no_referral_attached")

        start("EXTRACT")
        fields = extract(captured["document_text"])
        store(fields)

        start("REVIEW")
        fields = review(deepcopy(fields))
        store(fields)
        if fields is None:
            return finish("ended", "operator_cancelled")

        start("GATE")
        gate = completeness(fields, today=today)
        store(gate)
        for key in ("missing_fields", "confirmation_required", "appointments"):
            result[key] = _snapshot(gate[key])
        if gate["status"] != "Passed":
            return finish("ended", "incomplete")

        start("CMS")
        inputs = cms_inputs.to_cms_inputs(fields)
        store({"inputs": inputs})
        missing = cms_inputs.missing_cms_inputs(inputs)
        if missing:
            result["missing_fields"] = missing
            result["error"] = {"stage": stage, "type": "ValueError",
                               "message": "Missing process inputs: " + ", ".join(missing)}
            return finish("failed", "missing_cms_inputs")
        response = cms(inputs)
        store({"inputs": inputs, "result": response})
        result["cases"] = _snapshot(response.get("cases", []))
        result["customer"] = _snapshot(response.get("customer"))
        if response["status"] == "stopped":
            return finish("stopped", response.get("reason") or "cms_stopped")
        if response["status"] == "failed":
            return finish("failed", response.get("reason") or "cms_failed")
        if response["status"] != "completed":
            raise ValueError("Unexpected CMS status: " + str(response["status"]))
        customer = response["customer"]
        if not isinstance(customer, str) or customer.strip().casefold() in ("", "not found"):
            raise ValueError("Completed CMS result must supply a resolved customer")

        start("SUBJECT LINE BUILDER")
        all_data = (adapt or field_adapter.to_all_data)(fields, cms_customer=customer)
        store({"all_data": all_data})
        response = subject_line(all_data)
        store({"all_data": all_data, "result": response})
        status = response["status"]
        if status not in ("completed", "stopped", "failed"):
            raise ValueError("Unexpected Subject Line Builder status: " + str(status))
        return finish(status, response.get("reason") or {
            "completed": "completed", "stopped": "subject_line_stopped",
            "failed": "subject_line_failed"}[status])
    except (Exception, SystemExit) as error:
        detail = {"stage": stage, "type": type(error).__name__, "message": str(error)}
        result["error"] = detail
        result["payloads"][stage] = {"payload": result["payloads"].get(stage), "error": detail}
        return finish("failed", "exception")
