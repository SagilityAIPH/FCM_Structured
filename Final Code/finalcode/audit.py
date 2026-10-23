"""Final Code run-end whitelist adapter; storage is shared in AI.referral_json."""
from datetime import datetime, timezone
import re
from uuid import uuid4

ENV_DIRECTORY = "FCM_FINAL_CODE_AUDIT_DIR"


def now():
    return datetime.now(timezone.utc).isoformat()


def _fields(value):
    if not isinstance(value, dict):
        return None
    # The per-provider array, not legacy flat provider summaries, is authoritative.
    from AI.referral_schema import PROVIDER_FIELDS
    providers = value.get("providers", [])
    return {k: v for k, v in value.items() if k not in PROVIDER_FIELDS and k != "Provider Information"} | {
        "providers": providers if isinstance(providers, list) else []}


def _safe_reason(value):
    # Business reason codes only; never a returned free-form error/message.
    return value if isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,80}", value) else None


def build_record(run_id, started_at, stage_times, result, *, model_id=None,
                 sent_characters=None, captured_characters=None, review_edits=None,
                 credentials=(), stage_ends=None):
    payloads = result.get("payloads") or {}
    capture = payloads.get("CAPTURE") or {}
    if "payload" in capture:  # exception during snapshotting
        capture = capture.get("payload") or {}
    extracted = payloads.get("EXTRACT")
    reviewed = payloads.get("REVIEW")
    gate = payloads.get("GATE") or {}
    cms = payloads.get("CMS") or {}
    builder = payloads.get("SUBJECT LINE BUILDER") or {}
    if not isinstance(capture, dict):
        capture = {}
    if not isinstance(gate, dict):
        gate = {}
    if not isinstance(cms, dict):
        cms = {}
    if not isinstance(builder, dict):
        builder = {}
    cms_response = cms.get("result") or {}
    builder_response = builder.get("result") or {}
    if not isinstance(cms_response, dict):
        cms_response = {}
    if not isinstance(builder_response, dict):
        builder_response = {}
    error = result.get("error") or {}
    if not isinstance(error, dict):
        error = {}
    record = {
        "schema_version": 1, "run_id": run_id, "started_at": started_at,
        "ended_at": now(), "stages": [
            {"name": stage, "started_at": stage_times.get(stage),
             "ended_at": (stage_ends or {}).get(stage),
             "outcome": ("finished" if i < len(result.get("stages", [])) - 1 else result.get("outcome"))}
            for i, stage in enumerate(result.get("stages", []))],
        "capture": {"attachment_name": capture.get("attachment_name"),
                    "captured_characters": captured_characters},
        "extraction": {"model_id": model_id, "sent_characters": sent_characters,
                       "fields": _fields(extracted)},
        "review": {"approved": reviewed is not None if "REVIEW" in payloads else None,
                   "fields": _fields(reviewed),
                   "edits": [{"field": e["key"], "provider_index": e.get("provider_index"),
                              "changed": True, "at": e.get("at")}
                             for e in (review_edits or []) if isinstance(e, dict) and "key" in e]},
        "gate": {"status": gate.get("status"),
                 "missing_fields": gate.get("missing_fields", []),
                 "confirmation_required": gate.get("confirmation_required", []),
                 "cms_input_missing_fields": result.get("missing_fields", [])
                 if result.get("reason") == "missing_cms_inputs" else []},
        "cms": {"status": cms_response.get("status") if cms_response.get("status") in
                ("completed", "stopped", "failed") else None,
                "reason": _safe_reason(cms_response.get("reason")),
                "customer": result.get("customer") if "result" in cms else None},
        "subject_line_builder": {"status": builder_response.get("status") if builder_response.get("status") in
                                 ("completed", "stopped", "failed") else None,
                                 "reason": _safe_reason(builder_response.get("reason"))},
        "outcome": result.get("outcome"), "reason": _safe_reason(result.get("reason")),
        "error": {"stage": error.get("stage"), "type": error.get("type")}
                 if error else None,
    }
    # Review can add or remove provider records as well as edit their fields.
    if isinstance(extracted, dict) and isinstance(reviewed, dict):
        before = _fields(extracted) or {}
        after = _fields(reviewed) or {}
        for key in before.keys() | after.keys():
            if key != "providers" and before.get(key) != after.get(key) and not any(
                    e["field"] == key and e["provider_index"] is None for e in record["review"]["edits"]):
                record["review"]["edits"].append({"field": key, "provider_index": None,
                                                    "changed": True, "at": None})
        for index, (old, new) in enumerate(zip(before.get("providers", []), after.get("providers", []))):
            if isinstance(old, dict) and isinstance(new, dict):
                for key in old.keys() | new.keys():
                    if old.get(key) != new.get(key) and not any(
                            e["field"] == key and e["provider_index"] == index for e in record["review"]["edits"]):
                        record["review"]["edits"].append({"field": key, "provider_index": index,
                                                            "changed": True, "at": None})
        if len(before.get("providers", [])) != len(after.get("providers", [])):
            record["review"]["provider_count_changed"] = True
    # Per-stage statuses reflect actual stage work rather than merely entry.
    stages = record["stages"]
    for entry in stages:
        name = entry["name"]
        if name == "GATE":
            entry["outcome"] = gate.get("status")
        elif name == "CMS" and cms_response.get("status") in ("completed", "stopped", "failed"):
            entry["outcome"] = cms_response["status"]
        elif name == "SUBJECT LINE BUILDER" and builder_response.get("status") in ("completed", "stopped", "failed"):
            entry["outcome"] = builder_response["status"]
        elif name == "REVIEW":
            entry["outcome"] = "cancelled" if reviewed is None else "approved"
        elif name == "CAPTURE" and capture.get("attachment_name") is None and "document_text" in capture:
            entry["outcome"] = "no_referral_attached"
    if stages and result.get("outcome") == "failed" and not (
            stages[-1]["name"] == "CMS" and cms_response.get("status") == "failed") and not (
            stages[-1]["name"] == "SUBJECT LINE BUILDER" and builder_response.get("status") == "failed"):
        stages[-1]["outcome"] = "failed"
    # Whitelist above avoids credential-bearing CMS inputs, raw text, and error
    # messages. Redact even field values that happen to contain a credential.
    def redact(value):
        if isinstance(value, str):
            for secret in credentials:
                if isinstance(secret, str) and secret:
                    value = value.replace(secret, "[redacted]")
            return value
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()}
        return value
    return redact(record)


class Audit:
    def __init__(self):
        self.run_id = str(uuid4())
        self.started_at = now()
        self.stage_times = {}
        self.stage_ends = {}
        self.path = None

    def stage(self, name):
        timestamp = now()
        if self.stage_times:
            previous = next(reversed(self.stage_times))
            self.stage_ends[previous] = timestamp
        self.stage_times[name] = timestamp

    def finish(self, result, *, model_id=None, sent_characters=None,
             captured_characters=None, review_edits=None, credentials=()):
        """Return safe metadata for the existing referral record, never a second file."""
        record = build_record(self.run_id, self.started_at, self.stage_times, result,
                              model_id=model_id, sent_characters=sent_characters,
                              captured_characters=captured_characters,
                              review_edits=review_edits, credentials=credentials,
                              stage_ends=self.stage_ends)
        if record["stages"]:
            record["stages"][-1]["ended_at"] = record["ended_at"]
        return record
