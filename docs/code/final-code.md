---
tags: [code, final-code, app]
sources: ["Final Code/finalcode/orchestrator.py", "Final Code/finalcode/app.py", "Final Code/finalcode/live_wiring.py", "Final Code/finalcode/field_adapter.py", "Final Code/finalcode/cms_inputs.py", "Final Code/finalcode/audit.py", "Final Code/finalcode/rrs_capture.py", "Final Code/MAPPING.md"]
verified_at: b47ced0 (2026-10-28)
---
# Final Code

**Summary.** Final Code is the merged, attended intake app, `FinalCode.exe`. One operator-started run captures the open RRS referral's text, extracts the fields with AI, pauses for review, checks completeness, runs CMS re-open/customer search, then drives the RRS Subject Line Builder through Complete Triage and Unity Entry export. It stops **before Unity assignment**. The operator journey is in [[FINAL-CODE-FLOW]]; this note maps the code.

## Orchestrator: a synchronous state machine

`run(*, capture, extract, review, cms, subject_line, on_stage=None, today=None, adapt=None)` at `Final Code/finalcode/orchestrator.py:34`. Every stage is an injected callable, so the whole chain can be tested offline.

| Stage (`STAGES`, `:15`) | Does | Stops with |
| --- | --- | --- |
| CAPTURE `:74` | `capture()` reads the RRS viewer text and the attachment name | `ended / no_referral_attached` when there's no attachment |
| EXTRACT `:80` | `extract(text)` → `ReferralFields` (Bedrock) | `failed / exception` |
| REVIEW `:84` | `review(fields)` blocks until the operator approves or cancels | `ended / operator_cancelled` (review returns `None`) |
| GATE `:90` | `referral_schema.completeness(fields)` must be `Passed` | `ended / incomplete` |
| CMS `:98` | `cms(to_cms_inputs(fields))` runs re-open + customer search (`stage="all"`) | `failed / missing_cms_inputs`; `stopped`/`failed` from CMS; `failed / exception` if completed without a resolved customer (`:116-120`) |
| SUBJECT LINE BUILDER `:122` | `subject_line(to_all_data(fields, cms_customer=…))` | the builder's own `stopped`/`failed` |

Any exception, including `SystemExit`, becomes `failed / exception` (`:135-139`). The run writes no run data except the per-referral JSON from the app layer.

## Package files (`Final Code/finalcode/`)

| File | Role |
| --- | --- |
| `orchestrator.py` | The state machine above; has no UI, network or desktop dependencies |
| `app.py` | Wiring and lifecycle: `bootstrap_paths:41`, `make_capture:100`, `make_review:107`, `make_extract:128`, `build_live_callables:153`, `run_workflow:168`, `start_workflow:286` (runs only on Start), `launch:312`, `self_test:349`, `main:430` (`--self-test --report PATH`) |
| `api.py` | `FinalCodeAPI` adds `start_attended:30` on top of the shared Reader bridge. Start is operator-gated: the app does **not** auto-start |
| `live_wiring.py` | Live factories, never invoked on import. `make_capture:9`, `make_extract:18` (→ `bedrock_core.run_reasoning`), `make_cms:36` (→ `fcm_intake.workflows.reopen_flow.run_live(..., stage="all")`), `make_subject_line:83` (→ `subject_line_flow.run_flow(skip_capture=True, skip_cms=True)`; on `completed`, then `rrs_ui.RRSAdapter().complete_triage(all_data)`) |
| `rrs_capture.py` | `capture:22`: opens the work row at the top of the grid (`Claimant Row 0`), then the Email Display. It picks the attachment with the **legacy filename rule**: not `icasemanager`, and the name contains a comma or an 11-letter `w…` word. It opens that attachment and reads the viewer's accessible text, requiring two identical reads of at least 64 characters (`MIN_CAPTURE_CHARS`, up to 4 attempts). It doesn't parse the text, and the text isn't proof that every page rendered |
| `cms_inputs.py` | Pure mapping of AI fields to the CMS stage inputs, plus `missing_cms_inputs` |
| `field_adapter.py` | **One-way** AI → legacy `allData` adapter (~57 camelCase keys). Adjuster address comes from the office matrix (`_load_office_matrix:17`); `Not found` becomes `""` (`:91`). Full table: `Final Code/MAPPING.md` |
| `audit.py` | Run-end whitelist for the per-referral JSON. Storage lives in `AI/referral_json.py` |

## Front end and window

Final Code launches the **AI PDF Reader front end** in `memory_only` mode: there's no file upload or workbook write, and the text comes from RRS. Final Code-only controls (Start, review Approve/Cancel, CMS sign-in, the outcome panel) are scoped to that mode. See [[code/ai-pdf-reader]].

## Build and release

`Final Code/build.ps1` + `final_code.spec` → `dist/FinalCode.exe` plus `FinalCode.exe.sha256`. Tag family `finalcode-v*`; latest is `finalcode-v1.0.9`. The spec bundles the legacy scripts that are loaded at runtime (`legacy_fcm.py` for the SLB runtime) and the SLB `Deploy-Ready` files. See [[code/build-and-release]].

## Boundaries not to cross without the owner

- **Unity stays out of Final Code** (`AGENTS.md`). No file under `Final Code/` references `Processes/Unity`.
- Don't call legacy `main()` or the monolithic SLB entry point after earlier stages have already run, or capture and CMS run twice.

## Related

[[FINAL-CODE-FLOW]] · [[code/architecture]] · [[code/cms-customer-search]] · [[code/subject-line-builder]] · [[code/data-contracts]]

## Open questions

- `Final Code/PLAN.md:9` still says "spec only". That's a known stale line, already in the backlog.
