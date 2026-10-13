"""pywebview bridge. Extraction decisions remain in the shared AI modules."""
from base64 import b64encode
from copy import deepcopy
from datetime import datetime
from functools import wraps
from io import BytesIO
import json
import os
from pathlib import Path
import threading
import time
import uuid

import fitz

from AI import bedrock_runtime as core
from AI.address_enrichment import suggest_addresses, apply_suggestions
from AI.appointment_rules import confirm_appointments
from AI.daily_output import output_directory, save_daily_output
from AI.injury_classification import classify
from AI.provider_records import provider_summary, provider_display_name
from AI.referral_schema import FIELD_GROUPS, OPTIONAL_FIELDS, PROVIDER_FIELDS, DERIVED_FIELDS, output_key, clean_value


def response(method):
    """Expose a small, JSON-only API and redact credentials from errors."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        try:
            return {"ok": True, "value": method(self, *args, **kwargs)}
        except Exception as error:
            return {"ok": False, "error": self._error(error)}
    return wrapped


class WorkbenchAPI:
    def __init__(self, directory=None, *, memory_only=False):
        self._memory_only = memory_only
        self._review = None
        self._review_waiter = None
        self._workflow_active = False
        self._window = None
        self._lock = threading.RLock()
        self._documents = {}
        self._busy = False
        self._unsaved = False
        self._compact = False
        self._pending_prompt = None
        self._prompt_waiter = None
        self._workflow_result = None
        self._compact_lock = threading.Lock()
        self._external_stage = None
        self._external_progress = None
        self._thread = None
        self._stage = "Ready to import documents"
        self._bedrock = "Not tested"
        self._started = None
        self._elapsed = 0
        self._progress = {"done": 0, "total": 0}
        self._directory = Path(directory) if directory else output_directory()
        self._key = core.resolve_bedrock_api_key()
        self._settings = {"region": core.DEFAULT_BEDROCK_REGION, "model": core.DEFAULT_BEDROCK_MODEL,
                          "max_tokens": core.DEFAULT_MAX_TOKENS, "temperature": core.DEFAULT_TEMP,
                          "document_limit": core.DEFAULT_MAX_DOC_CHARS}

    def _error(self, error):
        message = str(error)
        return message.replace(self._key, "[redacted]") if self._key else message

    def _idle(self):
        if self._busy:
            raise ValueError("Wait for the current operation to finish.")

    def _document(self, identifier, fields=False):
        if identifier not in self._documents:
            raise ValueError("Document is no longer in this session.")
        doc = self._documents[identifier]
        if fields and doc["fields"] is None:
            raise ValueError("Extract this document first.")
        return doc

    def _summary(self, doc):
        fields = doc["fields"]
        checked = core.completeness(fields) if fields is not None else None
        return {key: doc[key] for key in ("id", "name", "status", "pages", "revision", "error", "elapsed", "workbook", "save_error")} | {
            "claimant": " ".join(fields.get(k, "") for k in ("First Name", "Last Name")) if fields is not None else "—",
            "claim": fields.get("Claim Number", "Not found") if fields is not None else "—",
            "next_step": checked["status"] if checked else None,
            "issues": len(checked["missing_fields"]) + len(checked["confirmation_required"]) if checked else 0,
        }

    @response
    def get_state(self):
        with self._lock:
            return {"documents": [self._summary(d) for d in self._documents.values()],
                    "busy": self._busy, "compact": self._compact,
                    "memory_only": self._memory_only,
                    "pending_review": deepcopy(self._review),
                    "pending_prompt": deepcopy(self._pending_prompt),
                    "workflow_result": deepcopy(self._workflow_result),
                    "stage": self._external_stage if self._external_stage is not None else self._stage, "bedrock": self._bedrock,
                    "elapsed": round(time.monotonic() - self._started, 1) if self._busy and self._started else self._elapsed,
                    "progress": dict(self._external_progress if self._external_progress is not None else self._progress), "settings": dict(self._settings),
                    "key_configured": bool(self._key), "output_directory": str(self._directory)}

    @response
    def set_compact(self, value):
        """Resize without holding the state lock across a synchronous UI Invoke."""
        if type(value) is not bool:
            raise ValueError("Compact mode must be a boolean.")
        from AI.workbench.window_layout import set_compact
        # Serialize resize requests, but let the UI and poller acquire _lock.
        with self._compact_lock:
            with self._lock:
                if value and self._pending_prompt is not None:
                    raise ValueError("Answer the pending prompt before entering compact mode.")
            set_compact(self._window, value)
            with self._lock:
                self._compact = value
        return value

    @response
    def set_stage(self, stage, done=None, total=None):
        """Publish an external stage, idle or busy, until the next accepted _start.

        Internal job updates (including completion/errors) continue underneath,
        but cannot overwrite this display override. An optional progress pair is
        likewise pinned; omitting it uses live internal progress. Does not mark
        the app busy or start its elapsed timer. Drivers must inspect job results.
        """
        if not isinstance(stage, str) or not stage.strip():
            raise ValueError("Stage must be a non-empty string.")
        if (done is not None or total is not None) and (
                type(done) is not int or type(total) is not int or not 0 <= done <= total):
            raise ValueError("Progress requires integer done and total with 0 <= done <= total.")
        with self._lock:
            self._external_stage = stage
            self._external_progress = None if done is None else {"done": done, "total": total}
        return True

    @response
    def set_workflow_result(self, result):
        """Publish the unchanged orchestrator result; pass None at a new run."""
        if result is not None and (not isinstance(result, dict) or result.get("outcome") not in
                                   ("completed", "ended", "stopped", "failed")):
            raise ValueError("Invalid workflow outcome.")
        snapshot = json.loads(json.dumps(result, allow_nan=False))
        with self._lock:
            self._workflow_result = snapshot
        return True

    def _ask_prompt(self, kind, title, message):
        """In-process worker callback. Never wait or resize with _lock held.

        A second concurrent prompt is rejected, not allowed to replace a waiter.
        notify also waits for acknowledgement so instructions cannot be lost.
        """
        waiter = {"event": threading.Event(), "answer": False}
        prompt = {"id": str(uuid.uuid4()), "kind": kind,
                  "title": str(title), "message": str(message)}
        with self._lock:
            if self._pending_prompt is not None:
                raise RuntimeError("Another operator prompt is already pending.")
            self._pending_prompt, self._prompt_waiter = prompt, waiter
        try:
            resized = self.set_compact(False)
            if not resized["ok"]:
                raise RuntimeError(resized["error"])
            waiter["event"].wait()
            return waiter["answer"]
        finally:
            with self._lock:
                if self._pending_prompt and self._pending_prompt["id"] == prompt["id"]:
                    self._pending_prompt = self._prompt_waiter = None

    def notify(self, title, message):
        """Pass directly as run_live(notify=api.notify) from a worker thread."""
        self._ask_prompt("notify", title, message)

    def confirm(self, title, message):
        """Raw boolean callback, deliberately not a bridge response envelope."""
        return self._ask_prompt("confirm", title, message)

    @response
    def answer_prompt(self, identifier, answer):
        with self._lock:
            if self._pending_prompt is None or self._pending_prompt["id"] != identifier:
                raise ValueError("Prompt is no longer pending.")
            if type(answer) is not bool:
                raise ValueError("Prompt answer must be a boolean.")
            if self._pending_prompt["kind"] == "notify" and not answer:
                raise ValueError("Acknowledge the notification.")
            waiter = self._prompt_waiter
            waiter["answer"] = answer
            self._pending_prompt = self._prompt_waiter = None
            waiter["event"].set()
        return True

    def wait_for_review(self, identifier):
        """Worker-only wait. Polling, editing and bridge answers never wait here."""
        waiter = {"event": threading.Event(), "fields": None}
        with self._lock:
            self._idle()
            self._document(identifier, fields=True)
            if self._review is not None:
                raise RuntimeError("Another review is pending.")
            self._review = {"id": str(uuid.uuid4()), "document_id": identifier}
            self._review_waiter = waiter
        try:
            resized = self.set_compact(False)
            if not resized["ok"]:
                raise RuntimeError(resized["error"])
            waiter["event"].wait()
            return waiter["fields"]
        finally:
            with self._lock:
                if self._review_waiter is waiter:
                    self._review = self._review_waiter = None

    @response
    def answer_review(self, identifier, approve):
        with self._lock:
            if self._review is None or self._review["id"] != identifier:
                raise ValueError("Review is no longer pending.")
            if type(approve) is not bool:
                raise ValueError("Review answer must be a boolean.")
            if approve:
                self._idle()
                if self._unsaved:
                    raise ValueError("Save field changes before approving.")
                fields = deepcopy(self._document(self._review["document_id"], fields=True)["fields"])
            else:
                fields = None
            waiter = self._review_waiter
            waiter["fields"] = fields
            self._review = self._review_waiter = None
            waiter["event"].set()
        return True

    def _import_paths(self, paths):
        with self._lock:
            self._idle()
            imported = []
            for value in paths:
                path = Path(value).resolve()
                duplicate = next((d for d in self._documents.values() if d["path"] == path), None)
                if duplicate:
                    imported.append(duplicate["id"])
                    continue
                if path.suffix.lower() not in (".pdf", ".docx", ".txt"):
                    raise ValueError("Choose PDF, DOCX, or TXT documents.")
                identifier = str(uuid.uuid4())
                doc = {"id": identifier, "path": path, "name": path.name, "status": "Ready", "pages": 0,
                       "revision": 0, "error": "", "elapsed": 0, "workbook": "", "save_error": "",
                       "fields": None, "raw": "", "text": "", "content": b"", "record_id": None,
                       "extracted_at": None, "address_report": [], "edits": [], "sent_characters": 0}
                try:
                    content = path.read_bytes()
                    stream = BytesIO(content)
                    stream.name = path.name
                    pages = core.extract_document_pages(stream)
                    doc.update(text=core.join_pages(pages), pages=len(pages), content=content)
                    if not doc["text"].strip():
                        raise ValueError("No selectable text found. This document needs OCR before extraction.")
                except Exception as error:
                    doc.update(status="Failed", error=self._error(error))
                self._documents[identifier] = doc
                imported.append(identifier)
            self._stage = f"Imported {len(imported)} document(s)"
            return imported

    def _import_text(self, name, text):
        """Ingest a document captured as text with no file on disk.

        Each capture is a separate document, even when its name is reused.
        """
        with self._lock:
            self._idle()
            pages = core.extract_pages_from_txt(text.encode("utf-8"))
            # Check page content before join_pages adds non-empty page headings.
            if not any(page["text"].strip() for page in pages):
                raise ValueError("No selectable text found in referral capture. Capture text or use OCR before extraction.")
            identifier = str(uuid.uuid4())
            self._documents[identifier] = {
                "id": identifier, "path": None, "name": name, "status": "Ready", "pages": len(pages),
                "revision": 0, "error": "", "elapsed": 0, "workbook": "", "save_error": "",
                "fields": None, "raw": "", "text": core.join_pages(pages), "content": b"", "record_id": None,
                "extracted_at": None, "address_report": [], "edits": [], "sent_characters": 0,
            }
            self._stage = "Imported referral text"
            return identifier

    @response
    def import_text(self, name, text):
        return self._import_text(name, text)

    @response
    def choose_documents(self):
        import webview
        with self._lock:
            self._idle()
        paths = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=True,
                                               file_types=("Documents (*.pdf;*.docx;*.txt)",))
        imported = self._import_paths(paths or [])
        self._queue_pending()
        return imported

    def _queue_pending(self):
        pending = [d['id'] for d in self._documents.values() if d['status'] == 'Ready']
        if pending and self._key:
            result = self.start_processing(pending)
            if not result['ok']:
                raise ValueError(result['error'])
        elif pending:
            self._stage = 'Documents ready. Configure Bedrock in Settings to start automatically.'

    @response
    def get_document(self, identifier):
        with self._lock:
            doc = self._document(identifier)
            fields = doc["fields"]
            groups = []
            if fields is not None:
                edited = {(e["key"], e["provider_index"]) for e in doc["edits"]}
                sources = {item["field"]: item["source"] for item in getattr(fields, "classification", [])}
                for group, labels in FIELD_GROUPS.items():
                    records = list(enumerate(fields.providers or [{}])) if group == "Provider Information" else [(None, fields)]
                    for index, record in records:
                        groups.append({"name": group if index is None else f"Provider {index + 1}",
                                       "fields": [{"key": output_key(group, label), "label": label,
                                                   "value": record.get(output_key(group, label), "Not found"),
                                                   "display_value": provider_display_name(record) if group == "Provider Information" and label == "Doctor / Facility" else None,
                                                   "provider_index": index, "confidence": None,
                                                   "manual": (output_key(group, label), index) in edited,
                                                   "optional": output_key(group, label) in OPTIONAL_FIELDS,
                                                   "source": sources.get(output_key(group, label)) if index is None else None,
                                                   "conditional": label in ("Doctor / Facility", "Doctor First Name", "Doctor Last Name")}
                                                  for label in labels]})
            return self._summary(doc) | {"groups": groups, "raw": doc["raw"], "text": doc["text"],
                    "is_pdf": doc["path"] is not None and doc["path"].suffix.lower() == ".pdf",
                    "preview_message": "No preview — referral text captured from RRS" if doc["path"] is None else None,
                    "record_id": doc["record_id"],
                    "validation": core.completeness(fields) if fields is not None else None,
                    "address_report": deepcopy(doc["address_report"]), "edits": deepcopy(doc["edits"]),
                    "name_inference": getattr(fields, "name_inference", []),
                    "address_review": getattr(fields, "address_review", []),
                    "classification": getattr(fields, "classification", []),
                    "sent_characters": doc["sent_characters"], "total_characters": len(doc["text"])}

    @response
    def render_page(self, identifier, page, scale=1.0):
        with self._lock:
            content = self._document(identifier)["content"]
        if not isinstance(page, int) or not 0.15 <= float(scale) <= 2.5:
            raise ValueError("Invalid preview page or zoom.")
        if not content:
            return {"available": False, "message": "No preview — referral text captured from RRS"}
        with fitz.open(stream=content, filetype="pdf") as pdf:
            if not 0 <= page < len(pdf):
                raise ValueError("Page is outside the document.")
            source = pdf[page]
            # Bound raster size even for PDFs with unusually large page dimensions.
            factor = min(float(scale), 2200 / max(source.rect.width, source.rect.height))
            pixmap = source.get_pixmap(matrix=fitz.Matrix(factor, factor), alpha=False)
            return "data:image/png;base64," + b64encode(pixmap.tobytes("png")).decode("ascii")

    def _start(self, stage, work):
        with self._lock:
            self._idle()
            self._external_stage = self._external_progress = None
            self._busy, self._stage, self._started = True, stage, time.monotonic()
        def worker():
            try:
                work()
            except Exception as error:
                with self._lock:
                    self._stage = self._error(error)
            finally:
                with self._lock:
                    self._elapsed = round(time.monotonic() - self._started, 1)
                    self._busy = False
        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    @response
    def save_settings(self, settings, api_key=""):
        with self._lock:
            self._idle()
            candidate = {"region": str(settings["region"]).strip(), "model": str(settings["model"]).strip(),
                         "max_tokens": int(settings["max_tokens"]), "temperature": float(settings["temperature"]),
                         "document_limit": int(settings["document_limit"])}
            core.build_bedrock_base_url(candidate["region"])
            if (not candidate["model"] or not 128 <= candidate["max_tokens"] <= core.MAX_OUTPUT_TOKENS
                    or not 0 <= candidate["temperature"] <= .5 or not 5000 <= candidate["document_limit"] <= 400000):
                raise ValueError("Use 128–16,384 tokens, temperature 0–0.5, and 5,000–400,000 document characters.")
            self._settings = candidate
            if api_key.strip():
                self._key = api_key.strip()
            self._bedrock = "Not tested"
            self._queue_pending()
            return True

    def _client(self):
        return core.create_bedrock_client(self._key, core.build_bedrock_base_url(self._settings["region"]))

    @response
    def test_connection(self):
        with self._lock:
            if not self._key:
                raise ValueError("Add a Bedrock API key in Settings first.")
            def work():
                try:
                    with self._client() as client:
                        core.test_bedrock_connection(client, self._settings["model"])
                except Exception:
                    with self._lock:
                        self._bedrock = "Connection failed"
                    raise
                with self._lock:
                    self._bedrock, self._stage = "Connected", "Bedrock connection verified"
            self._start("Testing Bedrock connection…", work)
            return True

    def _save(self, doc):
        if self._memory_only:
            return
        try:
            path, _ = save_daily_output(doc["fields"], str(doc["path"]) if doc["path"] is not None else doc["name"], directory=self._directory,
                                       record_id=doc["record_id"], extracted_at=doc["extracted_at"], update_existing=True)
            doc.update(workbook=str(path), save_error="")
        except Exception as error:
            doc["save_error"] = "Daily Excel was not saved. Close the workbook and retry. " + self._error(error)

    def _assess(self, doc):
        doc["status"] = "Completed" if core.completeness(doc["fields"])["status"] == "Passed" else "Needs Review"
        doc["revision"] += 1
        self._save(doc)

    def _enrich(self, fields):
        report = suggest_addresses(fields)
        selected = [i for i, item in enumerate(report) if item['status'] == 'suggested']
        if selected:
            fields = apply_suggestions(fields, report, selected)
            for i in selected:
                report[i]['status'] = 'accepted'
                report[i]['applied_automatically'] = True
            for item in fields.address_review[-len(selected):]:
                item['applied_automatically'] = True
        return fields, report

    @response
    def start_processing(self, identifiers, *, prepared_fields=None):
        with self._lock:
            self._idle()
            if prepared_fields is not None:
                if not self._memory_only or len(identifiers) != 1:
                    raise ValueError("Prepared extraction requires one in-memory workflow document.")
                doc = self._document(identifiers[0])
                doc.update(fields=deepcopy(prepared_fields), error="")
                self._assess(doc)
                return True
            if not self._key:
                raise ValueError("Add a Bedrock API key in Settings first.")
            docs = [self._document(i) for i in dict.fromkeys(identifiers)]
            if not docs or any(not d["text"].strip() for d in docs):
                raise ValueError("Select documents containing selectable text.")
            self._progress = {"done": 0, "total": len(docs)}
            for doc in docs:
                doc.update(status="Queued", fields=None, raw="", record_id=None, workbook="", save_error="",
                           address_report=[], edits=[], error="")
                doc['revision'] += 1
            def work():
                for doc in docs:
                    started = time.monotonic()
                    with self._lock:
                        doc.update(status="Processing", error="")
                        self._stage = "Extracting " + doc["name"]
                    try:
                        settings = self._settings
                        with self._client() as client:
                            _, fields, raw, elapsed = core.run_reasoning(client, settings["model"],
                                doc["text"][:settings["document_limit"]], doc["text"],
                                settings["max_tokens"], settings["temperature"])
                        with self._lock:
                            self._stage = 'Checking missing addresses: ' + doc['name']
                        fields, report = self._enrich(fields)
                        with self._lock:
                            doc.update(fields=fields, raw=raw, elapsed=elapsed, record_id=str(uuid.uuid4()),
                                       extracted_at=datetime.now().astimezone(), address_report=report, edits=[],
                                       sent_characters=min(len(doc["text"]), settings["document_limit"]), workbook="")
                            self._bedrock = "Connected"
                            self._assess(doc)
                    except Exception as error:
                        with self._lock:
                            doc.update(status="Failed", error=self._error(error), elapsed=round(time.monotonic() - started, 1))
                            doc["revision"] += 1
                    with self._lock:
                        self._progress["done"] += 1
                with self._lock:
                    self._stage = "Queue finished. Review validation and Excel save status."
            self._start("Starting extraction…", work)
            return True

    @response
    def save_fields(self, identifier, edits, revision):
        with self._lock:
            self._idle()
            doc = self._document(identifier, fields=True)
            if revision != doc["revision"]:
                raise ValueError("Results changed. Reload the document before saving edits.")
            fields = deepcopy(doc["fields"])
            if not fields.providers and any(edit.get('provider_index') == 0 for edit in edits):
                fields.providers = [{key: 'Not found' for key in PROVIDER_FIELDS}]
            allowed = {output_key(g, label) for g, labels in FIELD_GROUPS.items() if g != "Provider Information" for label in labels}
            history = []
            for edit in edits:
                key, index = edit["key"], edit["provider_index"]
                if (index is None and key not in allowed) or (index is not None and
                    (key not in PROVIDER_FIELDS or not isinstance(index, int) or not 0 <= index < len(fields.providers))):
                    raise ValueError("Unknown extraction field.")
                record = fields if index is None else fields.providers[index]
                value = clean_value(str(edit["value"]))
                if len(value) > 32767:
                    raise ValueError("A field exceeds Excel's 32,767-character cell limit.")
                if value != record.get(key):
                    history.append({"key": key, "provider_index": index, "before": record.get(key), "after": value,
                                    "at": datetime.now().astimezone().isoformat()})
                    record[key] = value
            for key in PROVIDER_FIELDS:
                fields[key] = provider_summary(fields.providers, key)
            # Re-run the RRS classification on edited descriptions; an operator's own choice always wins.
            manual = {e["key"]: e["after"] for e in doc["edits"] + history
                      if e["key"] in DERIVED_FIELDS and e["provider_index"] is None}
            ai = {item["field"]: item["ai_value"] for item in getattr(fields, "classification", [])}
            fields.classification = classify(fields, ai, manual)
            doc.update(fields=fields, address_report=[])
            doc["edits"].extend(history)
            doc['revision'] += 1
            def work():
                updated, report = self._enrich(fields)
                with self._lock:
                    doc.update(fields=updated, address_report=report)
                    self._assess(doc)
                    self._stage = 'Changes validated and address check finished.'
            self._start('Validating edits and checking missing address components…', work)
            return True

    @response
    def confirm_appointment(self, identifier, index):
        with self._lock:
            self._idle()
            doc = self._document(identifier, fields=True)
            doc["fields"] = confirm_appointments(doc["fields"], [index])
            self._assess(doc)
            return True

    @response
    def retry_save(self, identifier):
        with self._lock:
            self._idle()
            doc = self._document(identifier, fields=True)
            self._save(doc)
            doc["revision"] += 1
            if doc["save_error"]:
                raise ValueError(doc["save_error"])
            return doc["workbook"]

    @response
    def export_document(self, identifier, kind):
        import webview
        with self._lock:
            doc = self._document(identifier, fields=True)
            fields = deepcopy(doc["fields"])
            filename = (doc["path"] if doc["path"] is not None else Path(doc["name"])).stem or "referral"
        if kind == "json":
            content = json.dumps(core.export_payload(fields), indent=2, ensure_ascii=False)
        elif kind == "txt":
            content = core.format_field_block(fields)
        elif kind == "csv":
            content = core.table_df_to_csv_text(core.fields_to_table_df(fields))
        else:
            raise ValueError("Unsupported export format.")
        target = self._window.create_file_dialog(webview.FileDialog.SAVE, save_filename=f"{filename}.{kind}",
                                                  file_types=(f"Output (*.{kind})",))
        if target:
            path = Path(target if isinstance(target, str) else target[0])
            path.write_text(content, encoding="utf-8-sig" if kind == "csv" else "utf-8")
            return str(path)
        return None

    @response
    def set_unsaved(self, value):
        # Pushed from React so the close handler never has to query the page:
        # evaluate_js inside pywebview's closing event deadlocks the UI thread.
        self._unsaved = bool(value)
        return True

    @response
    def open_output(self):
        self._directory.mkdir(parents=True, exist_ok=True)
        os.startfile(str(self._directory))
        return True
