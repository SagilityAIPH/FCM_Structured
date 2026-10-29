---
tags: [code, process, cms, reopen-check]
sources: [Processes/Reopen-Check/README.md, Processes/Reopen-Check/Deploy-Ready/reopen_flow.py, src/fcm_intake/workflows/reopen_flow.py, src/fcm_intake/workflows/reopen_check.py, src/fcm_intake/workflows/customer_checker.py, Processes/Reopen-Check/Stand-Alone/CMSCustomerSearch.py]
verified_at: b47ced0 (2026-10-28)
---
# CMS Customer Search (`Processes/Reopen-Check`)

**Summary.** This process searches CMS for existing cases on the claim (the re-open check), shows any open or closed cases, asks the operator whether to continue, and then validates the **customer**. Final Code runs it as its **CMS** stage. It also ships as the standalone `CMSCustomerSearch.exe`. The folder keeps the name `Reopen-Check` for existing integrations. BRD: [[brd/03-cms-reopen-and-customer-search]] (slides 17–18).

> [!note] This is not CMS Registration
> This process only *searches*. Case setup and Complete Registration after Unity are [[code/cms-registration]].

## Controller

`run_flow(data, *, search_cases, check_customer, notify, confirm, stage="all")` at `Processes/Reopen-Check/Deploy-Ready/reopen_flow.py:8`. `stage` is `all`, `reopen` or `customer`.

| Situation | Result | Line |
| --- | --- | --- |
| Goodyear/Cooper Tire with an **open TCM** case | notify the manual instruction → `stopped / tire_customer_open_tcm` | `:20-31` |
| Open or closed cases found | notify the list → operator confirms; declining gives `stopped / user_declined` | `:34-39` |
| No cases | notify "No Open or Closed Cases Found in CMS", then continue to the customer check | `:41` |
| Customer unresolved, or handed off to CEM | `stopped / customer_unresolved_or_cem` (see [[cem/INVESTIGATION]]) | `:46` |
| Otherwise | `completed`, with the resolved `customer` | `:13,49` |

## Live wiring

`src/fcm_intake/workflows/reopen_flow.py:12` `run_live` imports the live code only when it runs:

- `search_cases` → `workflows/reopen_check.MainReopenCheck` → legacy `legacy_reopencheck.MainReopenCheck:606` (CMS case search in IE mode, `ValidateCaseNumber:423`).
- `check_customer` → `workflows/customer_checker.MainCustomerCheck` → legacy `legacy_customerchecker.py` (`SearchCustomerFirstWord:297`; name similarity via `normalize_business_name:445`, `jaccard:467`, `seq_ratio:473`). The CEM branch is in `legacy_cem.py` ([[process-wizard/W1-employer-and-cem]]: partial, and it targets UAT).
- Prompts fall back to Tk message boxes when no app callbacks are passed. Final Code passes the Reader bridge's `notify`/`confirm`.

## Stand-alone app (`Processes/Reopen-Check/Stand-Alone/`)

| File | Role |
| --- | --- |
| `CMSCustomerSearch.py` | EXE entry (`main:88`): `--version`, `--self-test-report PATH`, `--legacy-ui` (the Tk form in `desktop.py`); the default is the pywebview app |
| `webview_app.py` | pywebview + React front end (`ui/`). The `Api` bridge (`:96`) runs the live work in an isolated **worker process**; prompts cross a pipe (`PipePrompts:61`) |
| `desktop.py` | Tk form plus the shared worker (`execute_request:83`, `worker_main:120`). Input comes from the AI Reader's daily workbook by Record ID (`read_record`, `reopen_input`) |
| `run.py` | CLI: an offline fixture by default, `--live` for CMS. Credentials come from `FCM_CMS_USERNAME` / `FCM_CMS_PASSWORD` or a prompt (`:85-86`) |
| `prepare_drivers.py` | Fetches the pinned IE-mode driver for a reproducible build |
| `test_flow.py`, `test_portable.py`, `smoke_exe.py` | Offline tests and the packaged smoke test |

EXE: `dist/CMSCustomerSearch.exe` from `CMSCustomerSearch.spec` + `build.ps1`; tag family `cmscustomersearch-v*`, latest v1.1.0.

## Related

[[code/final-code]] · [[code/legacy-code]] · [[code/architecture]] · [[process-wizard/INVESTIGATION]]

## Open questions

- CEM targets the UAT portal (FCM-1.1-66 in [[INSTRUCTIONS]]).
- The live customer check runs legacy CEM **inside itself** when the operator answers Yes to "Do you need to complete CEM?" (`legacy_customerchecker.py:743-755`), then stops. Replacing that with a structured handoff to the planned `Processes/CEM/` app is FCM-1.1-127 ([[cem/INVESTIGATION]]).
- AI-based customer matching and the alternative stop/filter rules from the proposal table are not enabled (`Processes/Reopen-Check/README.md`).
