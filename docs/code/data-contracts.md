---
tags: [code, contracts, data]
sources: [AI/referral_schema.py, "Final Code/finalcode/cms_inputs.py", "Final Code/finalcode/field_adapter.py", "Final Code/MAPPING.md", Processes/Reopen-Check/Deploy-Ready/reopen_flow.py, Processes/Unity/Stand-Alone/unity_model.py, Processes/CMS-Registration/Deploy-Ready/contract.py, AI/referral_json.py, AI/daily_output.py]
verified_at: b47ced0 (2026-10-28)
---
# Data contracts across boundaries

**Summary.** These are the field sets that cross each process boundary, from the referral text through to registration. Display labels and stored keys differ. Always map from the **live definitions** below, not from screenshots or UI text. No values here are real.

## 1. The referral: `ReferralFields` (`AI/referral_schema.py`)

- **Groups** (`FIELD_GROUPS:21`): Claimant, Claim, RRS Classification, Case Manager, Provider, Attorney, Referral, Employer, Other, NCM.
- **Field lists:** `REQUIRED_FIELDS:59` (scalar keys the model must return), `OPTIONAL_FIELDS:80`, `PROVIDER_FIELDS:102` (one record per provider in the providers array), `DERIVED_FIELDS:89` (Body Part / Injury Type / Injury Cause, chosen after extraction), `SUPPLEMENTAL_FIELDS:91`. **Referral Number** (added 2026-10-30) is optional: it is read from the page-1 header and doesn't block completeness.
- **Absent value:** `Not found`. **Aliases** (`ALIASES:53`): `Customer Name` = `Employer Name`, and similar. These are labels only, never extra columns.
- **Completeness** (`completeness:502`): `{status: "Passed"|"Failed", missing_fields, …}`. Pending appointment confirmations also fail it.
- **Side metadata** travels with the fields through copies and review: AI-vs-form disagreement flags and format flags (`AI/field_review.py`).

## 2. Final Code CMS stage input (`Final Code/finalcode/cms_inputs.py:5`)

Exactly five keys: `claimNumber`, `claimID`, `customer`, `claimantFull`, `referralType`. Here `customer` is **Employer Name**, never a customer-contact label. Required: claimNumber, customer, claimID, claimantFull (`missing_cms_inputs:16`).

## 3. CMS Customer Search result (`reopen_flow.run_flow`)

`{status: completed|stopped, reason, customer, …}`. On `completed`, Final Code requires a nonblank resolved `customer` and passes **that** value, not the extracted employer, to the adapter.

## 4. Legacy Subject Line Builder input: `allData` (`Final Code/finalcode/field_adapter.py:106`)

About 57 camelCase keys, built one-way from `ReferralFields` with `cms_customer=`. Adjuster addresses are derived from `Claims Office Number` through the office matrix; `Not found` becomes `""`. Since 2026-10-30 `referralNumber` is mapped from **Referral Number** (`field_adapter.py:36`); before that it was always blank. The full key-by-key table is in **`Final Code/MAPPING.md`**. Audit any unmapped key against the legacy UI writes before you call the adapter complete.

## 5. Unity Assignment input (`Processes/Unity/Stand-Alone/unity_model.py`)

- 39 legacy context keys and 35 operator workbook/form columns (`schema:54`, `validate:88`, `to_controller:152`). Workbook: `Unity-Input.xlsx`, one referral and one provider per row, text identifiers, formulas rejected (`unity_excel.py`).
- The controller requires `customer`, `claimantFirst`, `claimantLast` and `claimNumber` (all/unity), or `claimNumber` only (assign). Optional `ncm` (v1.0.13).
- Result: `{status: completed|stopped|failed, reason, steps[], error{stage,type,message}}`.

## 6. CMS Registration (`Processes/CMS-Registration/Deploy-Ready/contract.py`)

- **Input** `RegistrationRequest(claim_number, claimant_first_name, claimant_last_name, referral_type 'Medical'|'Vocational', cms_case_id='', referral_number='', cem_employer_request: bool|None=None, record_id='')`.
- **Result** (every key always present): `outcome` (completed / stopped / cancelled / failed), `reason`, `stage`, `stages`, `case_id`, `candidates`, `steps`, `registration`, `cem`, `problems`, `error`.
- **Data source:** the stored procedure `RRS_Sagility_Details_Lookup`, about 31 columns read into legacy `CaseData` (`CMS.py:55,112`). See [[cms-registration/W3-cms-registration-data-and-module]] for the column-to-use map.

## 7. Per-referral JSON (`AI/referral_json.py`, schema version 2)

Top-level keys (`:193-196`): `schema_version`, `app` (`FinalCode` / `AIPDFReader`), `app_version`, `record_id`, `saves[]`, `model_id`, `ai_extracted` (the original model fields), `current` (after operator edits), `review_edits[]`, `completeness`, `source_text`, `sent_text`, plus the Final Code run-end summary (outcome, reason, stages). It holds full source text (PHI). One atomic file per referral; see [[code/ai-shared-modules]] for where it goes.

## 8. Daily workbook (`AI/daily_output.py`)

One workbook per day under the output folder, with a lock file. The Reader writes it (`save_daily_output:88`). CMSCustomerSearch reads a record by ID (`read_record:217`) and maps it with `reopen_input:249`. Final Code does **not** write it.

Since 2026-10-30 the workbook is **schema version 4**. **Referral Number** is appended as the **last** Referrals column, stored as text, because some code reads the first columns by position. A version-3 workbook is migrated without moving its existing columns. A **Review Flags** sheet records the non-blocking review flags, including ICD-10-CM and 2099-placeholder flags. Downstream readers use header names, so the new column doesn't break them.

## Related

[[code/architecture]] · [[code/final-code]] · [[code/cms-registration]] · [[code/unity-assignment]]

## Open questions

- Several Unity and Registration inputs (CMS case ID, attachments, CEM status) exist only in the portals at runtime. They can't come from the referral record. See [[cms-registration/W3-cms-registration-data-and-module]].
