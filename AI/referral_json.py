"""Shared, whitelisted per-referral JSON persistence for the attended apps.

The owner-approved source text and differing model input are retained in full.
CMS input payloads, exception messages and credentials do not belong here.
Files contain PHI and must stay outside Git working trees.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from threading import Lock
import unicodedata
from uuid import uuid4

from AI.referral_schema import DERIVED_FIELDS, PROVIDER_FIELDS, REQUIRED_FIELDS

SCHEMA_VERSION = 2
APP_VERSIONS = {"FinalCode": "1.0.9", "AIPDFReader": "1.1.1"}
SCALAR_FIELDS = frozenset([*REQUIRED_FIELDS, *DERIVED_FIELDS]).difference(PROVIDER_FIELDS)
ENV_DIRECTORY = "FCM_REFERRALS_DIR"


def _value(value):
    return value if value is None or isinstance(value, (str, bool, int, float)) else None


def _pick(value, keys):
    return {key: _value(value[key]) for key in keys if key in value} if isinstance(value, dict) else {}


def _fields(value):
    if not isinstance(value, dict):
        return None
    providers = getattr(value, "providers", None)
    if providers is None:
        providers = value.get("providers", value.get("Provider Information", []))
    result: dict[str, object] = dict(_pick(value, SCALAR_FIELDS))
    result["providers"] = [_pick(provider, PROVIDER_FIELDS) for provider in providers
                           if isinstance(provider, dict)] if isinstance(providers, list) else []
    result["review_flags"] = [
        {"field": item["field"], "provider_index": item.get("provider_index"),
         "kind": item["kind"], "reason": item["reason"],
         **({"reader_value": item["reader_value"]} if item.get("kind") == "disagreement" else {})}
        for item in getattr(value, "review_flags", value.get("review_flags", []))
        if isinstance(item, dict) and item.get("field") in SCALAR_FIELDS | set(PROVIDER_FIELDS)
        and item.get("kind") in ("disagreement", "format")
        and isinstance(item.get("reason"), str)
        and (item.get("kind") != "disagreement" or isinstance(item.get("reader_value"), str))]
    return result


def _strings(value):
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _completeness(value):
    if not isinstance(value, dict):
        return None
    return {
        "status": _value(value.get("status")),
        "missing_fields": _strings(value.get("missing_fields")),
        "provider_missing_fields": [_strings(item) for item in value.get("provider_missing_fields", [])
                                    if isinstance(item, list)],
        "confirmation_required": _strings(value.get("confirmation_required")),
        "appointments": [{**_pick(item, ("provider_index", "appointment_date", "date_only", "confirmed",
                                         "can_confirm", "fingerprint")),
                          "reasons": _strings(item.get("reasons"))}
                         for item in value.get("appointments", []) if isinstance(item, dict)],
    }


def _edits(value):
    result = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        field = item.get("field", item.get("key"))
        if field not in SCALAR_FIELDS and field not in PROVIDER_FIELDS:
            continue
        result.append({"field": field, "provider_index": _value(item.get("provider_index")),
                       "changed": True, "at": _value(item.get("at"))})
    return result


def _reason(value):
    return value if isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,80}", value) else None


def _run_end(value):
    if not isinstance(value, dict):
        return None
    result = _pick(value, ("started_at", "ended_at", "outcome"))
    result["reason"] = _reason(value.get("reason"))
    result["error"] = _pick(value["error"], ("stage", "type")) if isinstance(value.get("error"), dict) else None
    result["stages"] = [_pick(item, ("name", "started_at", "ended_at", "outcome"))
                        for item in value.get("stages", []) if isinstance(item, dict)]
    for key in ("cms", "subject_line_builder"):
        item = value.get(key) or {}
        if not isinstance(item, dict):
            item = {}
        result[key] = {"status": item.get("status") if item.get("status") in
                       ("completed", "stopped", "failed") else None,
                       "reason": _reason(item.get("reason"))}
        if key == "cms":
            result[key]["customer"] = _value(item.get("customer"))
    return result


def _redact(value, credentials):
    if isinstance(value, str):
        for secret in credentials:
            if isinstance(secret, str) and secret:
                value = value.replace(secret, "[redacted]")
        return value
    if isinstance(value, list):
        return [_redact(item, credentials) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item, credentials) for key, item in value.items()}
    return value


def _outside_git(path):
    resolved = path.resolve()
    if any((parent / ".git").exists() for parent in (resolved, *resolved.parents)):
        raise ValueError("folder is inside a Git worktree")
    return resolved


def _fallback(app):
    local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return _outside_git(local / "FCM_Structured" / app / "Referrals")


def _directory(app):
    override = os.environ.get(ENV_DIRECTORY)
    if not override and app == "FinalCode":
        override = os.environ.get("FCM_FINAL_CODE_AUDIT_DIR")
    if override:
        path = Path(override).expanduser()
        try:
            if not path.is_absolute():
                raise ValueError("override must be an absolute path")
            return _outside_git(path), None, False
        except (OSError, ValueError):
            return _fallback(app), "invalid or Git-contained override", True
    if not getattr(sys, "frozen", False):
        return _fallback(app), "source run", True
    try:
        return _outside_git(Path(sys.executable).parent / "Referrals"), None, False
    except (OSError, ValueError):
        return _fallback(app), "EXE folder is in a Git worktree", True


def _name_part(value):
    if not isinstance(value, str) or value.strip().casefold() in ("", "not found", "unknown", "none", "null"):
        return ""
    # Preserve Unicode letters while removing Windows-invalid characters,
    # apostrophes/commas and all Unicode control/format characters.
    value = "".join(char for char in value if char not in '<>:"/\\|?*,\'’'
                    and not unicodedata.category(char).startswith("C"))
    return re.sub(r"\s+", "-", value).strip(" .-")


def _claimant(fields):
    fields = fields or {}
    last, first = _name_part(fields.get("Last Name")), _name_part(fields.get("First Name"))
    return (f"{last}-{first}" if last and first else last or first or "Unknown-Claimant")[:60].rstrip(" .-")


class ReferralRecord:
    """One mutable referral file; failed writes never interrupt the operator.

    New names are installed with an exclusive hard link to a fully flushed temp
    file. Existing filenames are replaced only when they still belong to this
    instance's record ID. A rename installs the new file before deleting the old.
    """

    def __init__(self, app, *, record_id=None, credentials=()):
        if app not in ("FinalCode", "AIPDFReader"):
            raise ValueError("Unknown referral application")
        self.app = app
        self.record_id = record_id or str(uuid4())
        self.path = None
        self.notice = ""
        self.error = None
        self._credentials = tuple(credentials)
        self._save_lock = Lock()
        self._stamp = None
        self._data = {"schema_version": SCHEMA_VERSION, "app": app, "app_version": APP_VERSIONS[app] if getattr(sys, "frozen", False) else "source",
                      "record_id": self.record_id, "saves": [], "model_id": None,
                      "ai_extracted": None, "current": None, "review_edits": [],
                      "completeness": None, "source_text": None, "sent_text": None}
        if app == "FinalCode":
            self._data.update(captured_characters=None, sent_characters=None, run_end=None)
        else:
            self._data["source_file_name"] = None
            self._data["status"] = None

    def _owned(self, path):
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("record_id") == self.record_id
        except (OSError, ValueError, AttributeError):
            return False

    def _write(self, directory, record, stamp):
        directory.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                                             prefix=".referral-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            stem = f"{stamp}_{_claimant(record.get('current') or record.get('ai_extracted'))}"
            suffix = 1
            while True:
                path = directory / f"{stem}{'_' + str(suffix) if suffix > 1 else ''}.json"
                if path == self.path and self._owned(path):
                    os.replace(temporary, path)
                    break
                try:
                    os.link(temporary, path)
                    break
                except FileExistsError:
                    suffix += 1
            old_path = self.path
            self.path = path
            if old_path and old_path != path and self._owned(old_path):
                try:
                    old_path.unlink(missing_ok=True)
                except OSError:
                    self._cleanup_warning = "previous filename could not be removed"
            return path
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def save(self, reason, *, ai_extracted=None, current=None, review_edits=None,
             completeness=None, model_id=None, captured_characters=None,
             sent_characters=None, source_file_name=None, reader_status=None,
             source_text=None, sent_text=None, run_end=None, credentials=()):
        """Persist a whitelisted snapshot and expose a nonblocking status notice."""
        # This lock belongs only to this file writer. Callers must release their
        # UI/state lock before invoking save; file I/O never takes that lock.
        with self._save_lock:
            return self._save(reason, ai_extracted=ai_extracted, current=current,
                              review_edits=review_edits, completeness=completeness,
                              model_id=model_id, captured_characters=captured_characters,
                              sent_characters=sent_characters, source_file_name=source_file_name,
                              reader_status=reader_status,
                              source_text=source_text, sent_text=sent_text,
                              run_end=run_end, credentials=credentials)

    def _save(self, reason, *, ai_extracted=None, current=None, review_edits=None,
              completeness=None, model_id=None, captured_characters=None,
              sent_characters=None, source_file_name=None, reader_status=None,
              source_text=None, sent_text=None, run_end=None, credentials=()):
        self.error = None
        self._cleanup_warning = None
        self._credentials = tuple(dict.fromkeys((*self._credentials, *credentials)))
        try:
            for key, text in (("source_text", source_text), ("sent_text", sent_text)):
                # None means not supplied yet; the empty string is a complete,
                # immutable source value, not permission to replace it later.
                if self._data[key] is None and isinstance(text, str):
                    self._data[key] = text
            if self._data["ai_extracted"] is None and ai_extracted is not None:
                self._data["ai_extracted"] = deepcopy(_fields(ai_extracted))
            if current is not None:
                self._data["current"] = _fields(current)
            elif self._data["current"] is None and ai_extracted is not None:
                self._data["current"] = deepcopy(self._data["ai_extracted"])
            if review_edits is not None:
                self._data["review_edits"] = _edits(review_edits)
            if completeness is not None:
                self._data["completeness"] = _completeness(completeness)
            if model_id is not None:
                self._data["model_id"] = _value(model_id)
            if self.app == "FinalCode":
                for key, value in (("captured_characters", captured_characters), ("sent_characters", sent_characters)):
                    if value is not None:
                        self._data[key] = value if isinstance(value, int) and value >= 0 else None
                if run_end is not None:
                    self._data["run_end"] = _run_end(run_end)
            else:
                if source_file_name is not None:
                    self._data["source_file_name"] = re.split(r"[/\\]", str(source_file_name))[-1]
                if reader_status is not None:
                    self._data["status"] = reader_status if reader_status in (
                        "Completed", "Needs Review", "Failed", "Processing") else None
            local = datetime.now().astimezone()
            stamp = self._stamp or local.strftime("%Y-%m-%d_%H%M%S")
            save = {"reason": _reason(reason), "at_local": local.isoformat(),
                    "at_utc": local.astimezone(timezone.utc).isoformat()}
            record = _redact(deepcopy(self._data), self._credentials)
            # Persist actual model input separately only when it differs from
            # the full source; keep the first supplied value frozen internally.
            if self._data["sent_text"] is None or self._data["sent_text"] == self._data["source_text"]:
                record.pop("sent_text", None)
            record["saves"].append(save)
            if self.path:
                directory = self.path.parent
                fallback_reason, fallback = self._fallback_reason, self._is_fallback
            else:
                directory, fallback_reason, fallback = _directory(self.app)
            try:
                path = self._write(directory, record, stamp)
            except OSError:
                if fallback:
                    raise
                directory = _fallback(self.app)
                fallback_reason = "EXE/override folder is unwritable"
                fallback = True
                path = self._write(directory, record, stamp)
            self._stamp = stamp
            self._data["saves"].append(save)
            self._fallback_reason = fallback_reason
            self._is_fallback = fallback
            self.notice = (f"Saved {path} (fallback: {fallback_reason})" if fallback_reason
                           else f"Saved {path}" if os.environ.get(ENV_DIRECTORY) or
                           (self.app == "FinalCode" and os.environ.get("FCM_FINAL_CODE_AUDIT_DIR"))
                           else f"Saved Referrals\\{path.name}")
            if self._cleanup_warning:
                self.notice += "; warning: " + self._cleanup_warning
            return path
        except Exception:
            # Avoid leaking exception text: paths/messages can contain credentials
            # or source text. The operator still receives an explicit warning.
            self.error = "Referral JSON could not be saved; check folder permissions."
            self.notice = "Warning: " + self.error
            return None
