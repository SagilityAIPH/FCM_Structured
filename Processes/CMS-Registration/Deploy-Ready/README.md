# CMS Registration — Deploy-Ready source

Registration is a **separate, operator-started** process after Unity has created and assigned a CMS case and a supervisor has assigned a registration agent (BRD slide 101). It does not auto-run after Unity or replace Final Code's earlier CMS customer-search step. This folder is source integration, **not** a packaged release; live CMS/RRS/DB execution has not been validated.

## API

Load `contract.py`, `cms_registration_flow.py` and `cms_steps.py` by `importlib.util.spec_from_file_location` from this hyphenated directory. `RegistrationRequest(claim_number, claimant_first_name, claimant_last_name, referral_type, cms_case_id='', referral_number='', cem_employer_request=None, record_id='')` is immutable. `record_id` is local metadata, never a CMS case ID. `CaseCandidate`, `StepResult` and `RegistrationStages` are the shared frozen contracts.

`cms_registration_flow.run_flow(request, *, stages, on_stage=None, on_step=None) -> dict` accepts injected stages for offline use. Result **always** includes `outcome`, `reason`, `stage`, `stages` (completed only), `case_id`, `candidates`, `steps`, `registration`, `cem`, `problems`, `error`. Stage callbacks report the stage starting; the setup callback forwards `StepResult` notifications, while its returned list alone is authoritative. `Exception` and `SystemExit` become structured failures; `KeyboardInterrupt` propagates. A `manual` step requires operator confirmation; it is not automated verification.

Only when the operator explicitly starts a live run, call `session = cms_steps.open_live_session(settings)` and `run_flow(request, stages=session.stages, ...)`, then `session.close()` in a `finally`. Closing twice is safe. The desktop may use `dataclasses.replace(session.stages, review=...)` for its own review UI. Importing these modules never opens a browser or imports Selenium/pyodbc/pywinauto. The live session opens one CMS IE-mode browser and never automatically starts registration.

| Stage | Action / gate |
| --- | --- |
| START | Validate required claim, claimant, Medical/Vocational type. |
| CASE | Search CMS and require exact confirmed case ID or unique latest valid assigned date of matching referral type. |
| DATA | Stored-procedure-first legacy mapper; lazy daily CEM checker exact claimant/claim/date-sheet lookup supplies a boolean only when the workbook and sheet are readable; otherwise stop at `cem_status_unknown` unless the request supplies an explicit Yes/No. |
| REVIEW | Attended review; false cancels. |
| CMS_SETUP | Per-tab automation with readback; unresolved/ambiguous/mismatched work becomes an operator confirmation gate. See step table below. |
| COMPLETE_REG | RRS option 3/10 (option 10 retains explicit CEM authorization prompt) and exact confirmed CMS Case Id prompt readback required. |

| CMS_SETUP step | Status / backlog |
| --- | --- |
| `select_case` | Automated exact case re-selection and ID/referral readback — FCM-1.1-98. |
| `claim`, `claimant`, `case` | Legacy diagnosis/body part, claimant-tab navigation, referral source/inventory actions. |
| `adjuster_address`, `case_supervisor` | Matrix/mapping lookup, legacy popup selection, saved-field readback; manual only on unresolved/ambiguous/mismatch — FCM-1.1-105. |
| `customer` | Employer search/assign and matrix-based Bill To location/contact search with tab readback for the legacy Liberty market; other customers and policy exceptions remain manual — FCM-1.1-103. |
| `providers` | Search missing providers; operator selects exact record and tab is re-read — FCM-1.1-100. |
| `attorneys` | Legacy search/add/attach and unique tab-row readback; unresolved identity/manual entry rules require confirmation. |
| `billing` | Legacy case-opening activity code/note/description, explicit Save and activity-code readback (legacy Save was commented out). |
| `attachments` | Unique today's Unity sender, referral suffix and Save; ambiguity requires manual confirmation. |
| `notes` | **Manual gate:** Other Notes — FCM-1.1-102. |
| `letters` | Existing CPD ERFS Configure and instructions readback; unresolved configuration manually checked. |
| `first_appointment_claim_identifier`, `bill_to_policy`, `additional_cpd_erfs` | **Manual gates:** appointment/identifier (101), employer-specific Bill To/C02283 (103), *additional* CPD ERFS (104). |

Reasons: `invalid_request`, `case_not_confirmed`, `no_matching_case`, `case_ambiguous`, `cem_status_unknown`, `operator_cancelled`, `cms_step_failed`, `registration_not_verified`, `exception`, `registered`. The first four case/validation and CEM reasons are business stops; cancellation is distinct; any portal/step/registration mismatch fails.

## Settings (names only)

`cms_db_connection` (from `FCM_CMS_DB_CONNECTION`, **never** `FCM_RRS_DB_CONNECTION`), `reference_dir` (from `FCM_CMS_REFERENCE_DIR`), `cms_user`, `cms_password` (attended in memory only), optional `ie_driver_path`, `notify(title, message)`, `confirm(title, message) -> bool`. Optional `office_matrix_filename`, `supervisor_mapping_filename` override **only the filenames within** `reference_dir`; defaults are the legacy Liberty Claims Office Matrix (2019) and Dedicated Supervisor Mapping (2025). Neither secret nor connection is logged, persisted, or returned. Missing workbooks require a manual confirmation, not a fallback to a relative path.

## Deviations from CMS.py

- **FCM-1.1-98:** `CMS.py:996-1140` case selection is commented out. Read case-search/profile candidates, match Medical/Vocational and latest assigned date; ambiguous/missing dates require explicit case confirmation; reopen exact selected case before changing a tab. Does not rely on date-only `CheckCaseUnity`.
- **FCM-1.1-99:** `CMS.py:1885-1897` reads an unset global and swallows the Case Id prompt error. Type `case.case_id` from confirmed CMS selection, read back before clicking OK, and require exact result plus correct RRS option to report completion. For option 10, the Case Id prompt's availability remains unverified; absence fails rather than assuming success.
- **FCM-1.1-100:** `CMS.py:1524-1558` only searches when **no** provider row exists and truncates a name to four letters. Keep existing rows, search only missing providers, facility first word + phone or professional first/last + phone, retry city/state/ZIP on zero or over ten results; operator picks/adds under external Provider Entry Rules. Portal row identity is imperfect (name-based), so operator must adjudicate ambiguous records.
- **FCM-1.1-101:** `CMS.py:1315-1323` appointment/Claim Identifier writes are commented out; explicit manual verification instead of invented writes.
- **FCM-1.1-102:** `CMS.py:1738-1782` never verifies Other Notes; explicit manual check.
- **FCM-1.1-103:** `CMS.py:1485-1519` Bill To location is not employer-specific and does not select C02283. Missing employer search and matrix-based Bill To location/contact are restored with readback; employer-specific Bill To/C02283 policy remains an explicit manual gate.
- **FCM-1.1-104:** `CMS.py:1806-1841` configures a found ERFS, not an additional ERFS; the live adapter now configures the existing ERFS and reads its instructions back, then separately gates additional creation/verification.
- **FCM-1.1-105:** `CMS.py:40,790-814,1295-1296` relative-path workbooks now resolve from an explicit directory; mapped adjuster addresses and supervisor are applied using the legacy UI path and read back, with manual fallback for missing, ambiguous or mismatched reference/portal values.
- Legacy-parity recovery: missing employer search/Assign and matrix Bill To location/contact selection, attorney search/add/attach, opening billing activity, and existing CPD ERFS Configure are active rather than unconditional manual checklists. Billing explicitly saves before readback because the legacy save was commented out; attorney result selection and office/location matching require a unique match rather than taking the first. Employer-specific Bill To/C02283 and additional ERFS still need an operator.
- Other intentional safety differences: error propagation instead of `except: pass`; no legacy module-global driver; manual RRS row confirmation instead of unconditional Row 0, though claimant is the only machine-readable identity checked; attachment sender/date selection and idempotent suffix instead of first matching sender. Daily CEM membership uses legacy parity only as a routing signal, **not** proof of an authorized employer request: option 10 still requires operator confirmation.

Legacy imports on live entry: `CMS.create_ie_driver` (unless overridden driver path), `CMS.fetch_case_data_from_db`, and, for daily CEM routing, `CMS.get_excel_path`, `get_today_sheet_name`, `claim_exists` (lazy, never imported at module load). `claim_exists` reads the daily checker itself only after the adapter confirms the workbook and dated sheet exist. Missing/unreadable workbook or sheet, or a helper error, omits the key: the controller stops with `cem_status_unknown` and the operator must explicitly choose Yes/No. A readable sheet with no exact claimant+claim match yields `False` (option 3). Membership yields `True` (candidate option 10), subject to `complete_registration`'s separate operator confirmation. `CheckCaseUnity` is not used: Unity lookup checks date but not CMS referral type. The SP mapper returns flat display-safe strings but can still contain sensitive data in-memory; do not log results.

## Not verified live

No portal, database, RRS, reference/daily workbooks or Outlook accessed. Exact CMS HTML/frame and popup lifecycle, selectors, date format, search-result cardinality, adjuster/supervisor/employer/Bill To/attorney/billing/ERFS persistence, RRS option-10 Case Id prompt, provider search city/state/ZIP IDs, CEM/CMU status, Outlook drafts and recipient handling need attended UAT. A configured billing Save button and ERFS `instructions` readback require real-portal confirmation. The supervisor workbook is absent from the repository; the 2019 matrix may be stale. The current RRS grid readback only checks Row 0 claimant and uses an operator confirmation for claim, referral and work-row identity; it is **not** independently proven safe for unattended use. Do not release/build or run on live records from this source-only verification.

Offline verification: `.venv-bedrock/Scripts/python.exe -m unittest discover -s Processes/CMS-Registration/Deploy-Ready -p "test_*.py"` from the repository root, using synthetic records only.
