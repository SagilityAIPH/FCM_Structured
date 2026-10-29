---
tags: [code, process, cms, registration]
sources: [Processes/CMS-Registration/README.md, Processes/CMS-Registration/Deploy-Ready/README.md, Processes/CMS-Registration/Deploy-Ready/contract.py, Processes/CMS-Registration/Deploy-Ready/cms_registration_flow.py, Processes/CMS-Registration/Deploy-Ready/cms_rules.py, Processes/CMS-Registration/Deploy-Ready/cms_steps.py, Processes/CMS-Registration/Stand-Alone/backend.py, src/fcm_intake/legacy/CMS.py]
verified_at: b47ced0 (2026-10-28)
---
# CMS Registration (`Processes/CMS-Registration`)

**Summary.** CMS Registration covers **CMS case setup and RRS Complete Registration**, the step after Unity (BRD slides 102–123: [[brd/10-cms-case-setup]], [[brd/11-complete-registration]]). The operator starts it **per claim**, in its own app (`CMSRegistration.exe`), after a supervisor assigns the registration agent. It doesn't run automatically after Unity. Released as `cmsregistration-v1.0.0` (2026-10-28). It has been verified with synthetic data only; there has been **no live CMS/RRS run**. The investigation behind it is in [[cms-registration/INVESTIGATION]].

## Layout

| File | Role |
| --- | --- |
| `Deploy-Ready/contract.py` | Frozen dataclasses: `RegistrationRequest:31`, `CaseCandidate:56`, `StepResult:65`, `RegistrationStages:72`; plus `STAGES`, `OUTCOMES`, `REASONS` |
| `Deploy-Ready/cms_registration_flow.py` | Pure controller `run_flow(request, *, stages, on_stage=None, on_step=None)` (`:26`) |
| `Deploy-Ready/cms_rules.py` | Pure decisions: `select_case:6`, `inventory_type:72`, `supervisor_lookup:86`, `office_lookup:100`, `provider_search_plan:121` (slide 114), `providers_to_add:146` (slide 113), `attachment_subject:168`, `complete_reg_option:174` |
| `Deploy-Ready/cms_steps.py` | Live adapters, all imported lazily: `open_live_session(settings)` → `LiveSession(.stages, .close())`; `find_cases:104`; per-tab step functions; `complete_registration` |
| `Stand-Alone/run.py`, `backend.py`, `launcher.py`, `frontend/` | Offline scenarios, `--self-test --report`, `--desktop`, `--live`. The `CMSRegistrationAPI` bridge is idle until Start |
| `Stand-Alone/scenarios/*.json` | 14 synthetic scenarios, one for each outcome and reason |
| `Stand-Alone/cms_registration.spec`, `build.ps1` | The EXE build. It bundles the legacy `CMS.py` |

## Stages and outcomes

| Stage | Gate |
| --- | --- |
| START | Valid claim number, claimant names, referral type `Medical`/`Vocational` → else `stopped / invalid_request` |
| CASE | CMS search by claim. Keep candidates of the matching type, then require the operator-given case ID (`case_not_confirmed`) or a unique latest assigned date (`no_matching_case`, `case_ambiguous`) |
| DATA | Stored procedure `RRS_Sagility_Details_Lookup` (via legacy `fetch_case_data_from_db`, `CMS.py:112`). CEM comes from the request, or from the legacy daily CEM checker. If neither is available → `cem_status_unknown`. Caution: legacy CEM logs the PDF **Claim ID** in column B while this reader matches the **claim number**, so a real request can be missed (FCM-1.1-126, [[cem/INVESTIGATION]]) |
| REVIEW | Operator approves the case and data; declining → `cancelled / operator_cancelled` |
| CMS_SETUP | The per-tab steps below. Any `failed` step → `cms_step_failed`, and registration is not attempted |
| COMPLETE_REG | RRS `btnReg` → option `3` (normal) or `10` (CEM, with an extra operator confirmation) → Case Id typed in and read back. Only then `completed / registered`, otherwise `registration_not_verified` |

## CMS_SETUP steps (automated vs operator gate)

| Step | Behaviour |
| --- | --- |
| `select_case`, `claim`, `claimant`, `case` | Automated: diagnosis, body part, referral source, inventory type (`Medical - FEE` / `Vocational - FEE`) |
| `adjuster_address`, `case_supervisor` | Automated from the Claims Office Matrix and Dedicated Supervisor Mapping, read from `FCM_CMS_REFERENCE_DIR`, with readback. Manual if a lookup or readback fails (FCM-1.1-105) |
| `customer` | Employer search/assign plus the Bill To location and contact. Expects **"Liberty Mutual Commercial Market"**; anything else goes to operator review (FCM-1.1-103) |
| `providers` | Adds only the providers missing from the tab, using the slide-114 search rules; the operator picks or adds (FCM-1.1-100) |
| `attorneys`, `billing`, `attachments`, `letters` | Automated with readback (attachment: today's `UnityApiUser` row, plus ` - <referral number>`; letters: configures the existing CPD ERFS) |
| `notes`, `first_appointment_claim_identifier`, `bill_to_policy`, `additional_cpd_erfs` | **Manual gates**, because the BRD rules aren't supplied (FCM-1.1-102, 101, 103, 104) |

Fixes compared with legacy `CMS.py`: the case selection that was commented out (98), the Case Id that was never entered because of an unset global and a swallowed error (99), and the reversed provider-search condition (100). Details: `Deploy-Ready/README.md`, "Deviations from CMS.py".

## Settings (names only)

`FCM_CMS_DB_CONNECTION` (never falls back to Unity's `FCM_RRS_DB_CONNECTION`) and `FCM_CMS_REFERENCE_DIR`. CMS sign-in is collected per run and held in memory, never saved. Optional: `ie_driver_path`, `office_matrix_filename`, `supervisor_mapping_filename`. See [[code/configuration]].

## Related

[[cms-registration/INVESTIGATION]] · [[code/unity-assignment]] · [[code/cms-customer-search]] · [[code/legacy-code]] · [[code/build-and-release]]

## Open questions

- The live test is still pending. It needs the current supervisor mapping, confirmation of whether the office matrix is still current, the DB setting, and a UAT-or-production decision (FCM-1.1-97).
- `CMS.py`'s `__main__` example holds a hard-coded server name and username, and the file is bundled in this EXE (FCM-1.1-107; owned by the contributor).
