---
tags: [code, legacy, src]
sources: [src/fcm_intake/app.py, src/fcm_intake/runners/fcm.py, src/fcm_intake/legacy_loader.py, src/fcm_intake/cms/session.py, src/fcm_intake/cms/security_warning.py, src/fcm_intake/workflows, src/fcm_intake/legacy]
verified_at: b47ced0 (2026-10-28)
---
# Legacy code and the `src/fcm_intake` package

**Summary.** `src/fcm_intake/` holds the original V2 automation, now migrating out piece by piece, plus a thin application layer around it. The large legacy scripts in `src/fcm_intake/legacy/` still own **most of the live portal automation**. Newer processes load them lazily, by path, with `legacy_loader.load_module_from_path`. Keep them working. Change them only deliberately: the contributor actively edits `CMS.py`, `legacy_fcm.py` and `legacy_unity.py` for Unity.

## Application layer

| Path | Role |
| --- | --- |
| `main.py` (repo root) → `src/fcm_intake/__main__.py` | Starts the legacy CustomTkinter app `FcmBotApp` |
| `src/fcm_intake/app.py` | `FcmBotApp:52`: CMS login fields and the **Run Full FCM Flow**, **Close CMS Browser** and **Clear Log** buttons |
| `src/fcm_intake/runners/fcm.py` | `run_fcm:12`: sets the shared CMS credentials, then loads `legacy_fcm.py` by path and calls `main()` |
| `src/fcm_intake/legacy_loader.py` | `load_module_from_path:27`: imports a script by file path after `_ensure_legacy_compat` |
| `src/fcm_intake/config.py` | Paths (frozen-aware), `get_rrs_db_connection:38`, `get_local_setting:84`, the script constants (`FCM_SCRIPT`, `UNITY_SCRIPT`, …). See [[code/configuration]] |
| `src/fcm_intake/context.py` | `BotContext` (CMS username and password for the legacy app) |
| `src/fcm_intake/cms/session.py` | The **shared CMS IE-mode driver** and credentials (`create_ie_driver:73`, `get_shared_driver:114`, `init_shared_cms_session:303`, `close_shared_driver:349`), plus element helpers |
| `src/fcm_intake/cms/security_warning.py` | Handles the approved CMS certificate interstitial during navigation (`proceed_security_warning:99`, `CmsCertificateMonitor:143`) |
| `src/fcm_intake/cms/edge.py` | Finds Microsoft Edge and builds the Edge service |
| `src/fcm_intake/workflows/` | Thin adapters: `reopen_flow.run_live`, `reopen_check.MainReopenCheck`, `customer_checker.MainCustomerCheck`, `subject_line_builder.run_live` / `run_with_runtime` |
| `src/CMS.py`, `src/CustomerCheckerV2_shared.py`, `src/ReOpenCheck_shared.py`, `src/edge_auto.py` | One-line compatibility shims (`from fcm_intake… import *`) for old import names |

## Legacy scripts (`src/fcm_intake/legacy/`)

| Script | Lines | What it does | Used today by |
| --- | --- | --- | --- |
| `legacy_fcm.py` | 4,221 | The original end-to-end flow. `parse_referral_pdf:995` is the **regex referral parser (about 2,800 lines)**, which AI replaces. Also: `CreateSubjectLineBuilder:3991` (now delegates to SLB), `CompleteTriageAndExportAttachment:3996`, `InsertIntoTable:4100` (Unity tracking), `OpenUnity:4120`, `CheckAdvNotice:4144` (unused), `CompleteAssignment:4176` (delegates to `AI.rrs_assignment`), `main:4193` | The SLB runtime namespace (Final Code, legacy app), Unity tracking and completion |
| `CMS.py` | 2,191 | CMS case setup and RRS Complete Registration: `CaseData:55`, `fetch_case_data_from_db:112` (stored procedure), `create_ie_driver:289`, `login:925`, `searchCase:947`, `claim_exists:1937` (daily CEM check), `CheckCaseUnity:1967` (**Unity** case lookup), `run_case:2127`, `main:2165` | Unity (only `CheckCaseUnity`), CMS Registration (`fetch_case_data_from_db`, `create_ie_driver`, the CEM helpers). `run_case`/`searchCase` aren't called by anything |
| `legacy_unity.py` | 1,647 | Unity portal automation: `validate_and_complete_task:329`, defined fields, flags | Unity Assignment |
| `legacy_customerchecker.py` | 972 | CMS customer search and name matching (`SearchCustomerFirstWord:297`) | CMS Customer Search, through `workflows/customer_checker` |
| `legacy_reopencheck.py` | 640 | CMS re-open case check (`MainReopenCheck:606`, `ValidateCaseNumber:423`) | CMS Customer Search, through `workflows/reopen_check` |
| `legacy_cem.py` | 420 | CEM employer request (`employerSearch:51`, `custSearch:162`) and the **daily CEM workbook** helpers (`get_excel_path:302`, `get_today_sheet_name:309`, `add_claim_record:385`) | Customer check's CEM branch (`legacy_customerchecker.py:750-754` calls `legacy_cem.main`). It targets **UAT** ([[process-wizard/W1-employer-and-cem]]). Defects and the planned `Processes/CEM/` module: [[cem/INVESTIGATION]] (FCM-1.1-124 to 130); keep this file unedited |
| `legacy_googlesearch.py` | 1,067 | Google SERP / knowledge-panel provider lookup with a cache | `legacy_fcm.py:30`; SLB `legacy_steps.py:739` (`find_provider_address`), which Final Code's earlier completeness gate often skips |
| `legacy_providerresultchecker.py` | 371 | Provider address and phone matching | Imported by `CMS.py:30` and `legacy_fcm.py:27`; duplicated in SLB `provider_match.py` |

## Patterns and traps

- **Module globals.** Legacy helpers use module-global `driver`, `data` and `botStop`. New code passes the driver explicitly rather than mutating legacy globals (see `cms_steps.py`).
- **Swallowed errors.** Many legacy steps wrap their work in broad `try/except` and only print. A finished legacy call isn't proof that it succeeded.
- **`sys.exit()` inside legacy flows.** Controllers catch `SystemExit` separately (it isn't an `Exception`).
- **Lazy imports only.** Never import a legacy script at module import time in a process or test. Load it when a live run starts.
- **Hard-coded example values.** `CMS.py`'s `__main__` block holds a server name and username (FCM-1.1-107). Never copy them into docs.

## Related

[[code/architecture]] · [[code/configuration]] · [[code/cms-registration]] · [[code/unity-assignment]] · [[code/cms-customer-search]]

## Open questions

- Retiring `parse_referral_pdf` and the duplicated provider rules is planned but not scheduled ([[INSTRUCTIONS]]).
