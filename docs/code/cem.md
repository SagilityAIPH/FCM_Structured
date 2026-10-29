---
tags: [code, process, cem, employer-request-add]
sources: [Processes/CEM/README.md, Processes/CEM/Deploy-Ready/contract.py, Processes/CEM/Deploy-Ready/cem_flow.py, Processes/CEM/Deploy-Ready/cem_rules.py, Processes/CEM/Deploy-Ready/cem_log.py, Processes/CEM/Deploy-Ready/cem_steps.py, Processes/CEM/Stand-Alone/run.py, Processes/CEM/Stand-Alone/backend.py, Processes/CEM/Stand-Alone/cem.spec]
verified_at: af24f11 + uncommitted Processes/CEM (2026-10-30)
---
# CEM (Employer Request Add) module

**Summary.** `Processes/CEM/` raises a **new-employer request** in the CEM portal when CMS Customer Search finds no verified employer. The operator starts it as a **separate app** (`CEMRequest.exe`) after Customer Search stops with `needs_cem`. Nothing starts it automatically, and it never chains to Final Code or CMS Registration. The background, defects and owner decisions are in [[cem/INVESTIGATION]]. The old `src/fcm_intake/legacy/legacy_cem.py` is kept unedited as a reference and is **never imported**, because importing it opens Edge.

## Layout

| Part | Files | Role |
| --- | --- | --- |
| Deploy-Ready | `contract.py`, `cem_rules.py`, `cem_flow.py`, `cem_log.py`, `cem_steps.py` | Contract and settings, matching rules, the pure controller, the CEM log, and the lazy live Edge adapter |
| Stand-Alone | `launcher.py`, `run.py`, `backend.py`, `smoke.py`, `scenarios/*.json`, `frontend/`, `cem.spec`, `build.ps1` | Operator app: CLI, desktop bridge, 17 synthetic scenarios, self-test, packaging |

## Contract

- **`CEMRequest`:** `employer_name`, `claim_number`, `claim_id` (the PDF Claim ID, kept separate from the claim number), `claimant_first_name`, `claimant_last_name`, address fields (`country='USA'`), and optional `referral_number` and `record_id`. `validate()` rejects a blank employer, `Not found`, `Not Given/Not Applicable` and `No Employer`.
- **Stages:** START → VERIFY_SOURCE → SEARCH → REVIEW → SUBMIT → VERIFY_RECEIPT → TRACK (`cem_flow.run`).
- **Result:** every key is always present: `outcome` (completed / stopped / cancelled / failed), `reason`, `stage`, `stages`, `steps`, `request_status`, `request_reference`, `tracking_status`, `cem_log_row`, `problems`, `error`, `warning`. `completed / request_submitted` means **submitted, not approved**.

## Gates

1. The app opens idle; only **Start** begins a run, and a second Start is rejected.
2. The input and settings are validated before any browser opens (HTTPS URLs, a log path, and an address unless `allow_placeholder_address`).
3. CEM search first. An existing or ambiguous employer is a stop; an empty or loading table is not treated as "no match".
4. A duplicate check (CEM log + portal) runs before filling the form, and again right before Submit.
5. The filled form is read back (name, bill-to `Liberty Mutual Commercial Market` / `C02283`, address), then the operator reviews it, then a **separate, irreversible submit confirmation** that names the environment.
6. The bot clicks Submit **once**. An uncertain result stops with "do not resubmit", and nothing is retried or logged.
7. The request is read back from the portal; only then is the CEM log row written.

## CEM log

`FCM CEM Checher.xlsx` (the typo is the legacy contract), one sheet per day named `MMDDYYYY`:

| Column | Holds |
| --- | --- |
| A | Claimant |
| B | **Claim number** (header kept as legacy "Claim ID") |
| C | `Submitted` |
| D | PDF Claim ID |
| E | Employer |
| F | Request reference |
| G | Submitted at |
| H | Environment |

The location comes from `[cem] cem_log_path`. When that's set, CMS Registration reads the same file through this module's reader and matches claimant + claim number (FCM-1.1-126); see [[code/cms-registration]].

## Settings (`config/local_settings.ini`, `[cem]`)

| Key | Env override | Default |
| --- | --- | --- |
| `environment` | `FCM_CEM_ENVIRONMENT` | `uat`; `production` must be set explicitly |
| `employer_search_url`, `employer_add_url` | `FCM_CEM_EMPLOYER_SEARCH_URL`, `FCM_CEM_EMPLOYER_ADD_URL` | none (a live run stops with `configuration_required`) |
| `cem_log_path` | `FCM_CEM_LOG_PATH` | none |
| `allow_placeholder_address` | `FCM_CEM_ALLOW_PLACEHOLDER_ADDRESS` | false (pending BA, FCM-1.1-128) |

The Edge driver comes from `[browser] edge_driver_path`.

## Verification (2026-10-30, synthetic only)

- **Tests:** Deploy-Ready 74 OK; Stand-Alone 8 OK; `run.py --self-test` passes 17/17 scenarios plus the bridge smoke check.
- **`CEMRequest.exe`:** 42,993,094 bytes. Its packaged self-test exited 0 from `dist/` and from a copy outside the repo. The EXE doesn't contain `legacy_cem`, and no browser was launched during the self-test. It isn't released yet.

## Not verified

- **No live portal run.** Every selector in `cem_steps.py` is **UNVERIFIED**.
- **The live adapter can't check the bill-to yet.** It stops at `bill_to_unverified` before review and Submit, until an attended UAT session identifies the selected bill-to, the no-results signal, the Submit control and the request receipt (FCM-1.1-130).
- **Still open:** placeholder addresses (FCM-1.1-128) and whether the referral continues before CMU approval (FCM-1.1-129).

## Related

[[cem/INVESTIGATION]] · [[code/cms-customer-search]] · [[code/cms-registration]] · [[code/configuration]] · [[code/build-and-release]]
