---
tags: [code, process, rrs, subject-line-builder]
sources: [Processes/SubjectLineBuilder/README.md, Processes/SubjectLineBuilder/Deploy-Ready/subject_line_flow.py, Processes/SubjectLineBuilder/Deploy-Ready/legacy_steps.py, Processes/SubjectLineBuilder/Deploy-Ready/rrs_ui.py, Processes/SubjectLineBuilder/Deploy-Ready/manual_flow.py, src/fcm_intake/workflows/subject_line_builder.py]
verified_at: b47ced0 (2026-10-28)
---
# Subject Line Builder (`Processes/SubjectLineBuilder`)

**Summary.** This process drives the RRS **Subject Line Builder** form: customer and employer identity, claimant, like items, provider, adjuster and attorney lookups, appointment, claim and RRS classification dropdowns. It then runs **Complete Triage** and the **Unity Entry** attachment export. There are **two paths with different code**:

- the **shared legacy path**, used by Final Code and the legacy app;
- the **manual standalone path**, `SubjectLineBuilder.exe`, which uses Excel or manual input and doesn't read PDFs, call AI or connect to CMS.

BRD: [[brd/05-rrs-subject-line-builder-part1]], [[brd/06-rrs-subject-line-builder-part2]], [[brd/07-rrs-complete-triage-and-unity-export]].

## Path 1: the shared legacy path (Final Code and the legacy app)

- **Controller:** `run_flow(runtime, *, app=None, steps=None, allData=None, emaiDisplay=None, skip_capture=False, skip_cms=False)` at `Deploy-Ready/subject_line_flow.py:41`. It binds the extracted legacy steps into the legacy module namespace and catches `SystemExit` and ordinary failures, returning value-free diagnostics: type, message and source file:line.
- **Steps:** `Deploy-Ready/legacy_steps.py:3` `CreateSubjectLineBuilder(app=None, *, allData=None, emaiDisplay=None, skip_capture=False, skip_cms=False)`, about 2,700 lines with nested helpers. Its helpers before and after the CMS handoff call each other, so **don't split it at the handoff** (see `Final Code/PROCESS-MAP.md` §3.1).
- **Callers:**
  - The legacy app: `legacy_fcm.CreateSubjectLineBuilder` (`legacy_fcm.py:3991`) → `workflows/subject_line_builder.run_with_runtime(globals())`. That name is an alias of `subject_line_flow.run_flow`, loaded by path through the lower-case `PROJECT_ROOT / 'processes' / …`. This works only because Windows paths are case-insensitive.
  - Final Code: `live_wiring.make_subject_line` → `run_flow(skip_capture=True, skip_cms=True)`, then, only on `completed`, `rrs_ui.RRSAdapter().complete_triage(allData)` once ([[code/final-code]]).
- **Complete Triage boundary:** close the Email Display, uniquely match the claim's work row, click Complete Triage, answer the ZIP/confirmation prompts, export through Unity Entry `btnDownload`, then exit. Unity assignment is **not** part of this.

## Path 2: the manual standalone (`SubjectLineBuilder.exe`)

| File | Role |
| --- | --- |
| `Deploy-Ready/manual_flow.py` | Standalone schema, validation and guided workflow (`run_manual:99`). Imports nothing for PDF, CMS, AI, database or legacy |
| `Deploy-Ready/excel_input.py` | Template plus reader for `SubjectLineBuilder-Input.xlsx`: one referral and one provider per row |
| `Deploy-Ready/rrs_ui.py` | Focused UIA adapter `RRSAdapter:67`: `identity`, `claimant_search:494`, `provider_search:438`, `adjuster_search:523`, `appointment:612`, `fill_dropdown:688`, `create:756`, `select_work_row:817`, `answer_triage_prompts:849`, `complete_triage:873` |
| `Deploy-Ready/provider_match.py` | Provider and adjuster result matching: address normalization, phone formatting, strong and loose name matches |
| `Deploy-Ready/office_matrix.py` | Claims Office Matrix lookup for the adjuster address (path from `FCM_LM_MATRIX`, else the default locations, `matrix_path:256`) |
| `Deploy-Ready/body_part.py`, `injury_match.py` | Re-export `AI/injury_classification.py`. AI owns those rules |
| `Stand-Alone/backend.py`, `launcher.py`, `frontend/` | `ManualAPI` worker with review gates and cancellation; WebView2 host; React form |
| `Stand-Alone/test_flow.py`, `test_manual.py`, `test_excel.py`, `smoke.py` | 70 offline unittest tests plus the native-window smoke test |

The manual flow searches and fills, but **never creates provider or attorney master records** or invents missing data. The operator selects or adds the record in RRS and then presses Continue.

## Build

`Stand-Alone/build.ps1` + `subject_line_builder.spec` → `dist/SubjectLineBuilder.exe`, with a `.sha256` and the input template. Tag family `subjectlinebuilder-v*` (latest v1.1.1, released with `--latest=false`). **The build regenerates the tracked `SubjectLineBuilder-Input.xlsx`**, so check its diff.

> [!warning] UAT database tool
> `Processes/SubjectLineBuilder/reset_test_claimant.py` resets a claimant's Subject Line Builder details in the **UAT RRS database**. Use it only for test claimants.

## Related

[[code/final-code]] · [[code/ai-shared-modules]] · [[code/legacy-code]] · [[code/unity-assignment]]

## Open questions

- `legacy_fcm.py` and SLB `Deploy-Ready/` still duplicate some address and provider rules. Both are marked for removal (`Final Code/PROCESS-MAP.md` §1).
