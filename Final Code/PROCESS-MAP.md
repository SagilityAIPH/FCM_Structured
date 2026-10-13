# FCM_Structured — process map

**Purpose:** orient an AI agent (or a new engineer) on how the FCM processes connect, so the
"Final Code" integration can be built without re-discovering the codebase.

**How to use this:** §2 is the inventory (what exists, where). §3 is the target chain. §4 is the
data contract — the exact keys that cross each boundary. §7 lists traps that will cost you an hour
each if you miss them.

Every path, line number and key in this document was verified against the working tree. Re-verify
with the commands in §9 before trusting it — line numbers drift.

Companion document: `PLAN.md` (implementation spec and build order).

---

## 1. One-implementation rule

All AI Reader interfaces share the `AI/` modules. Standalone processes import from `AI.`.
**Do not add a third copy of a business rule.** `legacy_fcm.py` and the Subject Line Builder
`Deploy-Ready/` folder already duplicate some rules and are marked for removal.

If you find yourself re-implementing provider merging, address splitting, injury classification or
completeness, stop — it already exists in `AI/`.

---

## 2. Process inventory

### 2.1 RRS — Referral Routing System
Windows desktop app, automated with **pywinauto UIA**. Not ours; we drive its UI.

| | |
|---|---|
| Window | `Desktop(backend="uia").window(title_re=r"Referral Routing System*")` |
| Work queue grid | `auto_id="dgWorkWindow"`, control_type `Table` |
| Row selector | `Claimant Row 0` (Edit) / `Select Row 0` (CheckBox) |
| Attachment window | `Email Display`, grid `auto_id="dgAttach"` |
| Attachment cell | `Filename Row {r}` (Edit) |
| Triage button | `auto_id="btnTriage"` |
| Unity export window | `Unity Entry`, buttons `btnDownload`, `btnExit` |

Driven from two places:
- `Processes/SubjectLineBuilder/Deploy-Ready/legacy_steps.py` → `CreateSubjectLineBuilder()` L10–72 — opens the case and the attachment
- `src/fcm_intake/legacy/legacy_fcm.py` → `CompleteTriageAndExportAttachment()` L3996–4098 — triage, then exports the file via `btnDownload`
- `Processes/SubjectLineBuilder/Deploy-Ready/rrs_ui.py` — RRS form automation (recently expanded upstream; read before touching RRS)

### 2.2 AI PDF Analyzer (AI PDF Reader / FCM Workbench)

| | |
|---|---|
| Shared logic | `AI/` |
| Pipeline entry | `AI/workbench/backend.py` → `start_processing` |
| Extraction | `bedrock_runtime` / `bedrock_core.run_reasoning` — one Bedrock call, one retry on bad JSON |
| Post-processing | `referral_schema.force_exact_field_output` → `parse_field_block` |
| UI | pywebview + Edge WebView2 + React/TS/Vite/Tailwind, `AI/workbench/frontend/` |
| Window | 480 × 900, fixed width, `MaximizeBox = False` (`AI/workbench/window_layout.py`) |
| Launcher | `AI/workbench/launcher.py` → `python -m AI.workbench.launcher` |
| EXE | `dist/AI-FCM-Workbench.exe` (`AI/workbench/build.ps1`) |

Python API exposed to the frontend (`WorkbenchAPI`): `get_state`, `choose_documents`,
`get_document`, `render_page`, `save_settings`, `test_connection`, `start_processing`,
`save_fields`, `confirm_appointment`, `retry_save`, `export_document`, `open_output`.

**Model: the frontend polls `get_state()`.** Long work runs on a daemon thread started by
`_start(stage, work)`, which sets `_busy`, `_stage` and `_progress`.

### 2.3 CMS Customer Search (folder name: Reopen-Check)

| | |
|---|---|
| Home | `Processes/Reopen-Check/Stand-Alone/` |
| Core flow | `Processes/Reopen-Check/Deploy-Ready/reopen_flow.py` → `run_flow(data, *, search_cases, check_customer, notify, confirm, stage="all")` |
| App adapter | `src/fcm_intake/workflows/reopen_flow.py` → `run_live(data, *, app, notify, confirm, stage)` |
| Re-open check | `src/fcm_intake/workflows/reopen_check.py` → `MainReopenCheck(claim_number, claimant_name)` |
| Customer check | `src/fcm_intake/workflows/customer_checker.py` → `MainCustomerCheck(customer, claim_id, claimant, app)` |
| UI | pywebview + React/TS/Vite/Tailwind, `Processes/Reopen-Check/Stand-Alone/ui/` |
| Window | 1080 × 860 (`webview_app.py`) |
| Backend | `desktop.py` → `execute_request(request)`, `worker_main(connection, request)` |
| EXE | `dist/CMSCustomerSearch.exe` |

Python API exposed to its frontend (`Api` in `webview_app.py`): `get_config`, `browse_excel`,
`load_record`, `start`, `answer_prompt`, `poll_status`, `save_result`.

**Model: the frontend polls `poll_status()`.** Work runs in an **isolated worker process**;
live prompts cross back over a pipe (`PipePrompts.ask_yes_no` / `ask_text` / `notify`).

`stage` is one of `all` | `reopen` | `customer`.

### 2.4 Subject Line Builder
`Processes/SubjectLineBuilder/`. Entry `subject_line_flow.run_flow(runtime, app=)`; the real UI steps
live in `Deploy-Ready/legacy_steps.py` (2,649 lines) bound to the legacy module namespace via
`FunctionType`. Reached from the app through `src/fcm_intake/workflows/subject_line_builder.py`.

| | |
|---|---|
| RRS window | `Subject Line Builder Email Display`, opened via `btnSubjectSearch` on Email Display |
| Form fields | `tbCustomer`, `tbEmployer`, … (UIA `auto_id`, set with `iface_value.SetValue`) |
| Input | the legacy `allData` dict — ~57 camelCase keys |

**`CreateSubjectLineBuilder` is not just the Subject Line Builder.** It is one function containing
all three processes end to end — see §3.1. Integration uses opt-in guards, not a split.

### 2.5 Legacy FCM main app
`src/fcm_intake/app.py` (CustomTkinter) → "Run Full FCM Flow" → `runners/fcm.py::run_fcm` →
loads `legacy_fcm.py` via `legacy_loader.load_module_from_path(FCM_SCRIPT)` → `module.main()`.

`legacy_fcm.main()` order **today**:
```
CreateSubjectLineBuilder()            L4394
CompleteTriageAndExportAttachment()   L4396
OpenUnity() + CompleteAssignment()    L4398-4400
```

---

## 3. The Final Code chain

### 3.1 What exists today — all three processes are ONE function

`legacy_steps.py :: CreateSubjectLineBuilder(app=None)` — 2,649 lines — contains the whole chain:

| Lines | Does | Final Code treatment |
|---|---|---|
| 10–72 | RRS: open case item, find attachment, open PDF, `OpenPDFAndCaptureData` | **port** (Stage 1), drop the regex |
| 74–98 | business rules + `get_validation_missing` | superseded by AI + `completeness()` |
| 795–798 | gate: `if not ValidateInfo(allData): botStop; sys.exit()` | replaced by `completeness()` |
| 801 | `correctZipCode = allData['providerZip']` — global consumed later by triage | carry forward |
| **804** | **`run_reopen_flow(allData, app=app, notify=notify)`** — the CMS step | **reuse as-is** |
| 805–807 | `if process_result['status'] != 'completed': botStop; sys.exit()` | surface in UI |
| **808** | **`allData['customer'] = process_result['customer']`** | **load-bearing — see below** |
| 814–818 | `btnSubjectSearch` → `Subject Line Builder Email Display` window | **the SLB tail starts here** |
| 827–2649 | fill the SLB form from `allData[...]` | **reuse**, fed by an adapter |

> **SLB depends on CMS.** Line 808 replaces `allData['customer']` with the CMS-validated employer
> name, and line 835 types it into `tbEmployer`. Running the `reopen` stage alone, or skipping CMS,
> fills the RRS form with an unvalidated customer. **Final Code must run `stage='all'`.**

**Option A — parameterise, move no code (supersedes extraction).** The table above uses
pre-guard line numbers. Do not split at L814: head helper `_click_first_row_if_any`
closes over tail-defined matching/selection/search helpers, while the tail calls
head-defined `run_provider_search`; `run_provider_search_part` also shares that helper.
Both directions require the same late-bound function scope. Final Code enters through
`subject_line_flow.run_flow(..., allData=..., emaiDisplay=..., skip_capture=True, skip_cms=True)`,
with the CMS-validated customer already set by the adapter. This preserves SystemExit
containment. `correctZipCode`, derived business rules, and the natural manual-validation
safety net still run; validation is not superseded or bypassed by these guards.

### 3.2 Target chain

```
RRS                      AI PDF Analyzer            Operator        CMS                 SLB
───                      ───────────────            ────────        ───                 ───
Open Case Item
  ↓
◇ Referral attached? ──No──────────────────────────────────────────────────────→ End Process
  ↓ Yes
Open PDF (browser)
  ↓
UIA text grab ──────────→ Bedrock
                            ↓
                          parse_field_block
                            ↓
                          ReferralFields ─────────→ review/edit
                                                      ↓
                                                   ◇ completeness()
                                                      │
                                              Failed ─┴──────────────────────────→ End Process
                                                      ↓ Passed
                                                              run_flow(stage='all')
                                                                    ↓
                                                              ◇ status == completed?
                                                                    │
                                                        stopped ────┴────────────→ End Process
                                                                    ↓ completed
                                                              customer resolved
                                                                    ↓
                                                                              btnSubjectSearch
                                                                                    ↓
                                                                              fill SLB form
```

**Boundary 1 — RRS → AI:** a single `document_text` string. No file, no bytes.
**Boundary 2 — AI → CMS:** five scalar fields, in memory. See §4.2.
**Boundary 3 — CMS → SLB:** the resolved `customer` string, plus the full field set as `allData`. See §4.4.

---

## 4. Data contracts

### 4.1 RRS → AI PDF Analyzer

```python
# legacy_fcm.py L3773-3779 — the capture, regex removed
PDFBrowser = Desktop(backend="uia").window(title_re=f"{PDFName}")
PDFBrowser.wait("visible ready", timeout=60)
focus_control(PDFBrowser)
PDFDoc = PDFBrowser.child_window(title=PDFName, control_type="Document").wrapper_object()
document_text = PDFDoc.iface_text.DocumentRange.GetText(-1)
```

Produces `(attachment_name: str, document_text: str)`.

This text becomes `source_text` for the whole deterministic layer. Everything downstream
(`extract_special_instructions`, `explicit_form_fields`, `special_evidence`,
`recover_provider_records`, `split_address`, `classify`) consumes `source_text` and works unchanged
without a file.

### 4.2 AI PDF Analyzer → CMS

`reopen_flow.run_flow` validates these and raises `ValueError("Missing process inputs: ...")`:

| `run_flow` key | AI JSON key | Required for stage |
|---|---|---|
| `claimNumber` | `Claim Number` | `all`, `reopen` |
| `customer` | **`Employer Name`** | `all`, `customer` |
| `claimID` | `Claim ID` | `all`, `customer` |
| `claimantFull` | `First Name` + `" "` + `Last Name` | `all`, `customer` |
| `referralType` | `Referral Type` | optional — used by the tire-customer rule |

Verify the `customer` mapping yourself:
```python
output_key('Claimant Information', 'Customer Name')   # -> 'Employer Name'
```

`run_flow` returns:
```python
{"status": "completed" | "stopped", "reason": str, "customer": str,
 "cases": [...], "steps": [...]}
```
`status == "stopped"` is a **business stop**, not an error — e.g. an open TCM case for a
tire customer with a Full Case Management or One-Time RN Visit referral. The UI must surface
`reason` rather than treating it as success.

### 4.3 AI Reader internals worth knowing

- `REQUIRED_FIELDS` — 63 canonical keys; also builds the Bedrock JSON template and the parse check
- `PROVIDER_FIELDS` — 12 keys per provider record
- `FIELD_GROUPS` — display labels per section, drives every UI and `export_payload`
- `OPTIONAL_FIELDS` — decides whether a missing value fails the gate
- `DERIVED_FIELDS` — the three RRS classification values (Body Part, Injury Type, Injury Cause)
- `ReferralFields` — a `dict` subclass carrying `.providers`, `.classification`, `.name_inference`

---

## 5. Shared modules — use these, don't rewrite

| Need | Module |
|---|---|
| Extraction schema, prompt, post-processing | `AI/referral_schema.py` |
| Bedrock transport | `AI/bedrock_runtime.py`, `AI/bedrock_core.py` |
| Provider merge / summary / identity | `AI/provider_records.py` |
| Provider recovery from source text | `AI/provider_evidence.py` |
| Address split + canonical comparison | `AI/address_normalization.py` |
| Appointment validation + confirmation fingerprint | `AI/appointment_rules.py` |
| RRS dropdown classification | `AI/injury_classification.py` |
| Special Instructions extraction | `AI/document_sections.py` |
| Daily workbook | `AI/daily_output.py` |
| CMS re-open + customer flow | `Processes/Reopen-Check/Deploy-Ready/reopen_flow.py` |

---

## 6. Seams — where to plug in

| Seam | Signature | Use |
|---|---|---|
| `WorkbenchAPI._import_paths(paths)` | requires a real file | **needs a sibling `_import_text(name, text)`** for RRS capture |
| `WorkbenchAPI._start(stage, work)` | sets `_busy`/`_stage`, runs a thread | add new stages here; the stage string shows in the UI automatically |
| `reopen_flow.run_flow(...)` | injected `search_cases`, `check_customer`, `notify`, `confirm` | call directly; already dependency-injected |
| `reopen_flow.run_live(data, ...)` | wraps the above with live CMS deps | the app-level entry |
| `legacy_loader.load_module_from_path(name, path)` | loads legacy modules with sys.path fixups | how every legacy module is reached |

---

## 7. Traps

1. **`customer` is `Employer Name`.** Searching the schema for "Customer" yields
   `Customer Contact Name` and `Customer Contact Phone Number` — both wrong.
2. **`render_page` needs real PDF bytes.** `fitz.open(stream=content, filetype="pdf")` raises on
   `b""`. Text-only ingestion must make the preview fail soft.
3. **`_import_paths` rejects anything without a file path** and a `.pdf/.docx/.txt` suffix.
4. **Daily workbook headers come from keys, not labels.** `HEADERS = [...] + REQUIRED_FIELDS`,
   `PROVIDER_HEADERS = [...] + PROVIDER_FIELDS`. Renaming a *display label* is free; renaming a
   *key* needs a `VERSION` bump, a migration branch and a rebuild of every reader EXE.
5. **`check_layout` demands the exact header list** per schema version. An old EXE rejects a new workbook.
6. **The two UIs have different concurrency models.** Reader = daemon thread, polled via
   `get_state()`. CMS = isolated worker process with a prompt pipe, polled via `poll_status()`.
   Merging the UIs does not merge these; keep both, or deliberately unify.
7. **CMS component set is larger.** Reader frontend has only `ui/button` and `ui/input`; CMS also
   uses `card, dialog, label, scroll-area, select, textarea`.
8. **Edge PDF viewer renders lazily.** The UIA accessibility tree may only contain rendered pages,
   so a long referral can yield truncated text. Unverified risk — test with a multi-page referral.
9. **`glob.glob(ATTACHMENT_FOLDER)[0]`** (`legacy_unity.py:1278`) takes glob order, not newest file.
   Stale attachments can be re-uploaded.
10. **`python3` does not exist on this host.** Use `.venv-bedrock/Scripts/python.exe`, and run
    pytest with `-m` from the repo root so `AI` stays importable.
11. **CRLF/LF mix** in some files. After editing run `git diff --stat`; if a small edit shows a huge
    diff, `git checkout` the file and re-apply at byte level.
12. **`graphify update .` rewrites tracked `graphify-out/` files.** Do not run it casually.

---

## 8. Open decisions

Resolve these before building the corresponding piece.

| # | Question | Blocks |
|---|---|---|
| 1 | Does Final Code still write the daily workbook (`save_daily_output`) as an audit trail, or skip it entirely? The handoff is in-memory, but that does not say whether the record is persisted. | Stage 5 wiring, reporting |
| 2 | Does Final Code always run `stage='all'`, or can the operator pick `reopen` / `customer`? The CMS standalone app lets you choose. | CMS section UI |
| 3 | What happens after CMS returns? Display the result and stop? And how is `status == "stopped"` surfaced differently from `completed`? | End of chain |
| 4 | Does CMS keep its isolated-worker + prompt-pipe model inside the merged UI, or move to the Reader's thread model? | UI merge architecture |

Settled decisions are recorded in `PLAN.md` §1–§4.

---

## 9. Verify this map

```bash
cd "C:/Users/Administrator/Desktop/Projects/FCM_Structured"

# RRS capture chunk
grep -n "def CreateSubjectLineBuilder" Processes/SubjectLineBuilder/Deploy-Ready/legacy_steps.py
grep -n "def OpenPDFAndCaptureData\|def CompleteTriageAndExportAttachment" src/fcm_intake/legacy/legacy_fcm.py

# CMS contract
grep -n "def run_flow" -A 12 Processes/Reopen-Check/Deploy-Ready/reopen_flow.py

# Field mapping
.venv-bedrock/Scripts/python.exe -c "import sys; sys.path.insert(0,'.'); \
from AI.referral_schema import output_key; \
print(output_key('Claimant Information','Customer Name'))"

# Test gates
.venv-bedrock/Scripts/python.exe -m pytest tests/unit -q -p no:cacheprovider
.venv-bedrock/Scripts/python.exe -m unittest discover -s Processes/SubjectLineBuilder/Stand-Alone -p "test_*.py"
npm --prefix AI/workbench/frontend run build
```

Current baselines: **236 passed, 1 skipped** (unit) · **28 OK** (SLB).
