# Final Code: current attended flow

## Purpose and scope

Final Code is the merged, attended referral-intake application: RRS capture → Bedrock field extraction → operator review → completeness gate → CMS Customer Search → Subject Line Builder. Its launcher opens one shared pywebview/React window and starts a workflow worker only when the operator selects **Start**. The AI PDF Reader uses that same frontend but is a separate application: Final Code's `FinalCodeAPI` sets `memory_only=True`, which selects text-only review and suppresses the Reader's automatic daily-Excel save; the Reader's normal file-import and workbook behavior must not be inferred for Final Code. The window is not itself evidence of a successful live portal run. (`Final Code/finalcode/api.py:8-14`; `Final Code/finalcode/app.py:189-199`; `AI/workbench/backend.py:424-437`)

This describes the source working tree inspected for this note, not a claim that an older packaged executable contains every current UI change. Earlier `Final Code/PLAN.md` and `Final Code/PROCESS-MAP.md` describe design/target states and have stale status text; executable source and the current `Final Code/MAPPING.md` take precedence.

## Operator's journey

1. **Prepare and Start.** Have the intended case ready in RRS. The window opens idle with **Waiting for Start**; its Final Code header offers **Start**, and the fields pane waits for RRS capture. Start reserves one run, rejects another concurrent start, and starts a daemon worker. The stage/progress strip updates while the frontend polls state. Configure Bedrock credentials/settings in **Settings** before extraction; Start itself does not validate a key. (`Final Code/finalcode/api.py:8-46`; `AI/workbench/frontend/src/App.tsx:144-164`; `Final Code/finalcode/app.py:175-198`)
2. **Capture.** The worker focuses the RRS work queue, opens claimant row 0, examines Email Display attachment names, opens the first name matching the legacy selection predicate, and reads the viewer's UI Automation `DocumentRange.GetText(-1)`. A missing matching attachment ends the chain. A blank or inaccessible text capture instead fails at import/review or extraction; opening a viewer does not prove all its pages were captured. (`Final Code/finalcode/rrs_capture.py:14-49`; `AI/workbench/backend.py:272-295`; `Final Code/finalcode/orchestrator.py:73-82`)
3. **AI extraction.** The captured text is sent to the configured Bedrock client via shared `run_reasoning`, which parses/normalizes the response into canonical fields and retries malformed/incomplete JSON once. This is a single text handoff, not a file upload. A returned exception fails the active stage. (`Final Code/finalcode/live_wiring.py:18-33`; `AI/bedrock_core.py:198-213`; `Final Code/finalcode/orchestrator.py:80-82`)
4. **Attended review.** The extracted fields and captured text appear in the shared workbench; the PDF preview has no image and explains that the text came from RRS. Check and edit the grouped fields, inspect missing-field and appointment warnings, and use **Save field changes** before **Approve and continue**. The approve control is disabled for unsaved edits, and the backend rejects approval while edits are unsaved. An appointment requiring confirmation has its own explicit confirmation action; editing a confirmed appointment changes its fingerprint and requires checking it again. **Cancel run** returns no fields and ends this run. The review worker waits for that answer while UI polling remains responsive. (`Final Code/finalcode/app.py:96-113`; `AI/workbench/backend.py:199-238`; `AI/workbench/backend.py:317-348`; `AI/workbench/frontend/src/App.tsx:191-197`; `AI/appointment_rules.py:33-76`)
5. **Completeness gate.** Approval is not a bypass. The gate checks required scalar fields, at least one complete provider identity/record, and unresolved appointment warnings. Only `Passed` advances. Otherwise the result is **Ended**, with missing fields and/or appointment confirmations listed; this run does not continue automatically after later edits. (`AI/referral_schema.py:481-514`; `Final Code/finalcode/orchestrator.py:90-96`; `AI/workbench/frontend/src/components/CmsSection.tsx:17-22`)
6. **CMS Customer Search.** The app supplies five mapped inputs to the existing reopen/customer flow, fixed to `stage="all"`: case search, any operator notification/confirmation, then customer validation. The window displays in-process prompts that the operator acknowledges or answers. A CMS business stop does not run the Subject Line Builder. The result panel shows the outcome/reason, resolved customer when supplied, and returned case cards; it is titled **CMS Customer Search** even when an earlier stage ends. (`Final Code/finalcode/live_wiring.py:36-41`; `Processes/Reopen-Check/Deploy-Ready/reopen_flow.py:8-56`; `AI/workbench/backend.py:152-197`; `AI/workbench/frontend/src/components/CmsSection.tsx:13-34`)
7. **Subject Line Builder.** Only a completed CMS result with a nonblank resolved customer advances. The adapter sets that customer in the legacy field dictionary. The live callable re-acquires Email Display after the review pause and calls the existing form-filling flow with capture and CMS repeats disabled. The legacy controller returns completed, stopped, or failed; the window publishes the corresponding final workflow result. The operator should not interpret a synthetic completion as proof that real RRS form filling worked. (`Final Code/finalcode/orchestrator.py:107-139`; `Final Code/finalcode/field_adapter.py:105-144`; `Final Code/finalcode/live_wiring.py:44-61`; `Processes/SubjectLineBuilder/Deploy-Ready/subject_line_flow.py:21-50`; `Final Code/finalcode/app.py:145-172`)

## Technical chain

`finalcode.orchestrator.run` owns the ordered, synchronous state machine; its five injected callbacks may block. `app.build_live_callables` assembles them, `start_workflow` runs them off the UI thread, and `run_workflow` publishes the final in-memory result. Stage notifications go through `api.set_stage`. (`Final Code/finalcode/orchestrator.py:34-58`; `Final Code/finalcode/app.py:132-185`)

| Stage | Injected callable and implementation | Result/boundary |
|---|---|---|
| CAPTURE | `capture`: `app.make_capture` wraps `live_wiring.make_capture` → `rrs_capture.capture` (`Final Code/finalcode/app.py:89-93`; `Final Code/finalcode/live_wiring.py:9-15`; `Final Code/finalcode/rrs_capture.py:14-49`) | Attachment name, viewer text, claimant-row value; `None` attachment ends run (`Final Code/finalcode/orchestrator.py:73-78`). |
| EXTRACT | `extract`: `app.make_extract` reads current API settings → `live_wiring.make_extract` → `AI.bedrock_core.run_reasoning` (`Final Code/finalcode/app.py:116-129`; `Final Code/finalcode/live_wiring.py:18-33`) | Canonical field object passed to review (`Final Code/finalcode/orchestrator.py:80-85`). |
| REVIEW | `review`: `app.make_review` imports captured text, attaches already-extracted fields without another model call, and blocks on `api.wait_for_review` (`Final Code/finalcode/app.py:96-113`; `AI/workbench/backend.py:199-238`) | Saved, approved fields or `None` for cancellation (`Final Code/finalcode/orchestrator.py:84-88`). |
| GATE | No injected callback: `AI.referral_schema.completeness` (`Final Code/finalcode/orchestrator.py:90-96`; `AI/referral_schema.py:481-514`) | Only `Passed` reaches CMS. |
| CMS | `cms`: `live_wiring.make_cms` → `fcm_intake.workflows.reopen_flow.run_live(..., stage="all")`; notify/confirm are workbench callbacks (`Final Code/finalcode/app.py:132-142`; `Final Code/finalcode/live_wiring.py:36-41`; `src/fcm_intake/workflows/reopen_flow.py:12-35`) | Required-input check precedes call; resolved customer is mandatory for continuation (`Final Code/finalcode/orchestrator.py:98-120`). |
| SUBJECT LINE BUILDER | `subject_line`: `live_wiring.make_subject_line` loads `subject_line_flow.run_flow` with a fresh Email Display handle and `skip_capture=True, skip_cms=True` (`Final Code/finalcode/live_wiring.py:44-61`; `Processes/SubjectLineBuilder/Deploy-Ready/subject_line_flow.py:21-50`) | `field_adapter.to_all_data` converts approved fields with CMS customer before form filling (`Final Code/finalcode/orchestrator.py:122-134`). |

## Every exit path

The published workflow outcome is **Completed**, **Ended**, **Stopped**, or **Failed** in the result panel. Each row is a terminal path for the current run; later stages are not invoked. Error detail is displayed when supplied. (`Final Code/finalcode/app.py:145-172`; `AI/workbench/frontend/src/components/CmsSection.tsx:5-34`)

| Outcome / reason | Trigger | What the operator sees |
|---|---|---|
| `ended / no_referral_attached` | Capture returned `attachment_name=None` (`Final Code/finalcode/orchestrator.py:73-78`; `Final Code/finalcode/rrs_capture.py:48-49`). | **Ended**, “No referral attachment was found”; no CMS cases (`AI/workbench/frontend/src/components/CmsSection.tsx:5-19`). |
| `ended / operator_cancelled` | Review returns `None` after **Cancel run** (`Final Code/finalcode/orchestrator.py:84-88`; `AI/workbench/frontend/src/App.tsx:193-196`). | **Ended**, cancellation explanation (`AI/workbench/frontend/src/components/CmsSection.tsx:5-19`). |
| `ended / incomplete` | Gate status is not `Passed` (`Final Code/finalcode/orchestrator.py:90-96`). | **Ended**, missing required fields and unresolved appointment confirmations; no CMS invocation (`AI/workbench/frontend/src/components/CmsSection.tsx:10-22`). |
| `failed / missing_cms_inputs` | After the gate, one or more of `claimNumber`, `customer`, `claimID`, `claimantFull` is blank; `referralType` is optional (`Final Code/finalcode/cms_inputs.py:5-19`; `Final Code/finalcode/orchestrator.py:98-106`). | **Failed**, error stage/type/message. The CMS flow is not called (`AI/workbench/frontend/src/components/CmsSection.tsx:17-23`). |
| `stopped / <CMS reason>` | CMS returns `stopped`, including `tire_customer_open_tcm`, `user_declined`, `customer_unresolved_or_cem` (`Processes/Reopen-Check/Deploy-Ready/reopen_flow.py:32-54`; `Final Code/finalcode/orchestrator.py:107-112`). | **Stopped** with business reason/manual-action wording for those named reasons, plus cases/customer if supplied; no builder (`AI/workbench/frontend/src/components/CmsSection.tsx:5-31`). |
| `failed / <CMS reason or cms_failed>` | CMS returns `failed`, or returns an invalid status/completed response without a resolved customer (`Final Code/finalcode/orchestrator.py:113-120`). | **Failed**. Supplied CMS `error`/`message` becomes structured detail; an invalid response instead produces an `exception` with stage `CMS` (`Final Code/finalcode/orchestrator.py:60-68`; `Final Code/finalcode/orchestrator.py:135-139`; `AI/workbench/frontend/src/components/CmsSection.tsx:17-23`). |
| `stopped / subject_line_stopped`, `failed / subject_line_failed`, or `completed / completed` (unless callback supplies a reason) | Builder returns a valid status. Legacy controller catches `SystemExit` and ordinary exceptions as a failed response (`Final Code/finalcode/orchestrator.py:122-134`; `Processes/SubjectLineBuilder/Deploy-Ready/subject_line_flow.py:35-50`). | Matching final badge, reason and error detail when supplied; a failed response with no details explicitly says details were not supplied (`AI/workbench/frontend/src/components/CmsSection.tsx:5-23`). |
| `failed / exception` | Capture, extraction, review, gate, adapter, CMS, builder, or stage callback raises `Exception` or `SystemExit`; `KeyboardInterrupt` is deliberately not caught here (`Final Code/finalcode/orchestrator.py:34-41`; `Final Code/finalcode/orchestrator.py:135-139`). | **Failed**, active stage, exception type and message (`AI/workbench/frontend/src/components/CmsSection.tsx:17-23`). |
| `failed / launcher_error` | Unexpected error escapes the launcher/runner boundary (`Final Code/finalcode/app.py:153-171`). | **Failed**, `LAUNCHER` stage/type/message if publication succeeds (`AI/workbench/frontend/src/components/CmsSection.tsx:17-23`). |

## Data contract

- Capture returns `attachment_name`, `document_text`, and `claimant_row_value`; only `document_text` goes to the model. The captured name/text are held for the attended workbench review. UI Automation reads the viewer, not a PDF file path or bytes. (`Final Code/finalcode/rrs_capture.py:41-49`; `Final Code/finalcode/app.py:70-113`; `Final Code/finalcode/orchestrator.py:73-85`)
- `run_reasoning` returns parsed canonical fields as its **second** tuple member; normalization builds a `ReferralFields` dictionary with side metadata, which the orchestrator snapshots for result display. Review receives a copy and approval supplies the saved current fields. (`Final Code/finalcode/live_wiring.py:25-33`; `AI/referral_schema.py:569-571`; `Final Code/finalcode/orchestrator.py:18-31`; `AI/workbench/backend.py:221-238`)
- CMS receives exactly `claimNumber` ← `Claim Number`, `claimID` ← `Claim ID`, **`customer` ← `Employer Name`** (not a field labelled Customer), `claimantFull` ← `First Name` + `Last Name`, and `referralType` ← `Referral Type`. The first four are required. (`Final Code/finalcode/cms_inputs.py:5-19`; `Final Code/finalcode/field_adapter.py:31-37`; `Final Code/finalcode/field_adapter.py:122-125`)
- After CMS completes, the one-way adapter converts the approved canonical fields to the legacy camelCase dictionary. It uses the first provider record when present, reads selected Body Part/Injury Type/Injury Cause from flat keys, turns `Not found` into empty strings, derives service/routing/state values, and **overrides** `customer` with CMS's resolved value. See the [full mapping](../Final%20Code/MAPPING.md). (`Final Code/finalcode/field_adapter.py:90-144`; `Final Code/finalcode/orchestrator.py:118-125`)

## What is not done

- The Final Code intake boundary does **not** open/read/copy a PDF file or send PDF bytes to Bedrock; RRS itself opens an attachment viewer, and Final Code scrapes its accessible text. An image-only or lazily rendered page may have no captured text. (`Final Code/finalcode/rrs_capture.py:39-49`; `Final Code/finalcode/live_wiring.py:27-32`; `AI/workbench/backend.py:272-295`)
- Final Code does **not automatically write the Reader's daily Excel workbook**. It now saves one automatic referral JSON through the shared `AI/referral_json.py` module, including extraction, saved review and terminal outcome. The earlier separate run-audit writer is replaced; the legacy `audit_path` result key points to the same referral JSON. Explicit JSON/CSV/TXT export remains a separate operator action. Subject Line Builder still fills RRS UI.
- The **Claims Office Matrix workbook is read**, not written, to look up adjuster physical/mailing address from Claims Office Number (with a claim-number fallback). Missing lookup data leaves address keys blank. This reference workbook is distinct from the absent daily-output workbook. (`Final Code/finalcode/field_adapter.py:133-144`; `Processes/SubjectLineBuilder/Deploy-Ready/office_matrix.py:147-153`; `Processes/SubjectLineBuilder/Deploy-Ready/office_matrix.py:269-290`)

## Automatic referral JSON (FCM-1.1-81)

Final Code creates a shared `ReferralRecord` for each run. The exact core
`saves[].reason` tokens are `after_extraction`, `save_changes`, `complete`, and
`run_end`. Extraction and **Save changes** save immediately. `complete` is saved
only after operator approval and the orchestrator's actual `Passed` completeness
gate, at entry to CMS before its input checks/callback. Approval alone does not
save `complete`; cancellation, an incomplete gate or a gate exception never does.
Extra address-check/confirmation/retry saves retain their own reason tokens.
Early capture/extraction failures, cancellation, incomplete gates,
CMS stops/failures, builder failures and launcher errors still get a run-end
record, using `Unknown-Claimant` when no claimant is available. All saves for the
run use one record ID and one current file; name edits rename that file while
preserving its first-save timestamp. Reader uses the same writer for its own
per-document records and keeps its existing daily workbook behavior.

For a frozen app the preferred folder is `Path(sys.executable).parent / Referrals`,
created automatically. Source execution, an EXE inside Git (including a `.git`
worktree file), or an unwritable folder falls back visibly to
`%LOCALAPPDATA%/FCM_Structured/FinalCode/Referrals/`. Absolute `FCM_REFERRALS_DIR`
overrides this; `FCM_FINAL_CODE_AUDIT_DIR` remains a Final Code alias. Every
selected folder must be outside Git. Invalid/unwritable targets produce a
fallback or nonfatal warning in the existing status area. A successful adjacent
save displays `Saved Referrals\<filename>`; fallback output shows its path.
State locks are released before file I/O and operator waits.

Filename: local first-save `YYYY-MM-DD_HHMMSS_<Last>-<First>.json`, with
`Unknown-Claimant` for absent names. Invalid characters, controls, commas and
apostrophes are removed, spaces become dashes, and the claimant component is
capped at about 60 characters. Different records with the same name/timestamp
use `_2`, `_3`, etc.; atomic writes preserve the previous file on failure and
protect other referrals from replacement.

The versioned whitelist stores app, `app_version: "source"`, `schema_version: 2`
and record ID, local/UTC save
history, model ID, immutable `ai_extracted`, current canonical fields, provider
arrays, edit metadata and completeness (missing fields, provider gaps and
appointment confirmations). Final Code adds captured/sent character counts and
terminal outcome/reason, value-free error type/stage, stage timings, resolved
CMS customer/status and Subject Line Builder status. Reader adds the
source filename and current Reader status on each save. **Owner decision:
always store the full raw source text for debugging**, beginning with the first
after-extraction save, and preserve it through later edits/overwrites.
`source_text` is the full RRS viewer capture in Final Code (the text counted by
`captured_characters`), or the uploaded document's extracted text after
`join_pages` in Reader. If the model receives different text, `sent_text` also
stores that exact model input, including a Reader character-limit truncation.
Reader passes `sent_text` as `run_reasoning`'s `full_document_text` argument,
which is inserted into the model prompt; the full `source_text` is the separate
`validation_source_text` argument used by Python post-processing. No inference
input or section-reader rule is changed by this persistence hook.
No opt-in is required. Runs ending before extraction may lack these texts.
CMS inputs/cases, credentials, raw model responses and free-form exception
messages remain excluded; configured secrets are redacted in source/sent text
and all other allowed values. Character counts describe input before redaction.
The original field snapshot is the canonical extraction returned by
the current engine; it is not the raw model response. Shared extraction now keeps
the AI value when the section reader disagrees or returns blank; a valid reader
value fills a blank AI value, and format validity breaks a one-valid-one-invalid
tie. Disagreements and malformed ZIP, date, SSN, phone and gender values are
non-blocking review flags shown in both apps and persisted in `ai_extracted`
and `current` as `review_flags` (`field`, `provider_index`, `kind`, `reason`,
optional `reader_value`). Saving an edit clears its disagreement and reruns
format checks; completeness and the approval gate are unchanged.

These records contain PHI and claimant names in filenames. **FCM-1.1-46** remains
open for retention, access, deletion/backup and folder/profile protections,
including the folder beside the EXE. **The expiry number of days will be added
later under FCM-1.1-46; no expiry or automatic deletion is implemented here.**
The full-text retention is explicitly owner-approved. FCM-1.1-81, FCM-1.1-82
and FCM-1.1-83 ship in Final Code v1.0.9 and AI PDF Reader v1.1.1, with
synthetic unit and packaged self-tests. No live RRS/CMS/Bedrock/portal behavior
or packaged operator clicks are established by these tests; supervised live
confirmation remains separate work.

## Known limitations and open items

- Live RRS/CMS/Bedrock/Subject Line Builder integration and multi-page viewer text coverage are not established by the synthetic self-test. Confirm capture completeness and native window/prompt behavior during a supervised live verification. The `README-exe.md` notes the same validation boundary; the current backlog is [[INSTRUCTIONS]], not this document. (`Final Code/finalcode/app.py:226-284`; `Final Code/finalcode/rrs_capture.py:14-18`)
- The UI/backend code in shared files was being edited concurrently while this note was written. The review controls, idle Start state, and wording above were observed in the working tree at verification; an older EXE or a later unverified edit may differ. The v1.0.9 binary packages these source changes; packaged UI clicks were not tested. Earlier `PLAN.md` says “spec only”; that status is obsolete given the live source described above.

## Run and verify

From the repository root on Windows, start `dist/FinalCode.exe` for the attended window. Build instructions/prerequisites are in [Final Code/README-exe.md](../Final%20Code/README-exe.md). For an offline **packaged** smoke test, use a **native Windows path** for the report (a bare MSYS `/tmp/...` path is not suitable for this native EXE): (`Final Code/finalcode/app.py:299-316`; `Final Code/final_code.spec:87-95`)

```bash
./dist/FinalCode.exe --self-test --report "C:/Users/Administrator/AppData/Local/hermes/profiles/omniroute/cache/scratch/finalcode-selftest.json"
```

The self-test uses synthetic fields, stub capture/extract/CMS/builder callbacks, and a real blocking review handoff automatically answered by a test thread. Check the report for `outcome: completed`, all six stages, and `published: true`; the windowed EXE does not rely on stdout. The command above is a verification recipe, not a claim that this EXE was run for this document. (`Final Code/finalcode/app.py:226-296`; `Final Code/finalcode/app.py:299-312`)

Baseline source tests, from the repository root:

```bash
.venv-bedrock/Scripts/python.exe -m pytest tests/unit -q -p no:cacheprovider
.venv-bedrock/Scripts/python.exe -m unittest discover -s Processes/SubjectLineBuilder/Stand-Alone -p "test_*.py"
```

Synthetic tests verify the exercised code paths, **not** live RRS capture, CMS access, Bedrock output, or RRS form-fill behavior.
