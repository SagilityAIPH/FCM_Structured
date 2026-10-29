---
tags: [code, ai, shared, module, ai-pdf-analyzer]
aliases: [AI PDF Analyzer, AI PDF Analyzer module]
sources: [AI/bedrock_core.py, AI/bedrock_runtime.py, AI/referral_schema.py, AI/source_evidence.py, AI/field_review.py, AI/referral_json.py, AI/daily_output.py, AI/injury_classification.py, AI/referral_number.py, AI/icd10.py, AI/provider_evidence.py, AI/provider_records.py, AI/appointment_rules.py]
verified_at: b47ced0 (2026-10-28); module identity and the 2026-10-30 rules checked at 9774a34 (released in workbench-v1.2.0 / finalcode-v1.0.10)
---
# AI PDF Analyzer module (`AI/`)

**This folder is the modular process of the AI PDF Analyzer** (owner-confirmed 2026-10-30). Other processes live under `Processes/<name>/` with a `Deploy-Ready/` + `Stand-Alone/` split. The Analyzer doesn't: `AI/` itself is the module, and two apps run it.

| How it runs | Where | Notes |
| --- | --- | --- |
| **Stand-alone** | AI PDF Reader / FCM Workbench, `AI/workbench` → `AI-FCM-Workbench.exe` (tag family `workbench-v*`) | Loads a PDF/DOCX/TXT and writes the daily workbook and per-referral JSON. See [[code/ai-pdf-reader]] |
| **Embedded** | Final Code (`Final Code/finalcode`) imports `AI.workbench.backend`, `AI.referral_schema` and `AI.appointment_rules` | Uses text captured from RRS (`memory_only`). It doesn't keep its own copy. See [[code/final-code]] |
| Helper consumers | CMS Customer Search, Subject Line Builder, Unity | They import only helpers (`daily_output`, `injury_classification`, `rrs_assignment`, `unity_*`, `window_layout`), not the extraction rules |

A rule change in `AI/` therefore changes **both** the stand-alone Reader and Final Code, but users only get it after both EXEs are rebuilt and released. `final_code.spec`, `workbench.spec` and `bedrock.spec` bundle the module's data files, including `AI/data/icd10cm_2027.txt`.

**Summary.** `AI/` is the **one implementation** of referral extraction and its business rules. The AI PDF Reader, Final Code, CMSCustomerSearch, Subject Line Builder and Unity all import from it. Don't copy a rule from here into a process folder (`Final Code/PROCESS-MAP.md` §1). Nothing in `AI/` owns a window, except the small `*_ui.py` Streamlit helpers.

## Extraction pipeline (one model call, one retry)

```mermaid
flowchart TD
  T[Document text<br/>pages joined] --> P[FIELD_ONLY_PROMPT<br/>+ today's date for appointment years]
  P --> M[Bedrock call<br/>call_llm_once]
  M --> Y[reconcile_model_appointment_years]
  Y --> X[force_exact_field_output → parse_field_block]
  X -->|bad or truncated JSON, first time| P
  X --> F[ReferralFields + formatted block]
```

- **`bedrock_core.run_reasoning`** (`AI/bedrock_core.py:222`): builds the prompt, calls the model and post-processes the answer. On malformed JSON it retries once with a "return valid complete JSON" suffix, then raises (`:236-248`). It returns `(result_text, fields, raw, seconds)`. Final Code's `live_wiring.make_extract` uses the second item.
- **Model and transport.** The default model is `openai.gpt-oss-120b` through the OpenAI-compatible Bedrock endpoint (`bedrock_core.py:13`). The native Converse transport, `bedrock_runtime.py`, defaults to `openai.gpt-oss-120b-1:0` (`:14`), and the Reader backend imports it as `core`. Key resolution: a key typed in the app, then `OPENAI_API_KEY` (`bedrock_core.py:28-44`); the Runtime variant uses `AWS_BEARER_TOKEN_BEDROCK` (`ai_fcm_bedrock_runtime.py:97-117`).
- **What the prompt asks for.** Final JSON only, with no reasoning. The model's raw text is returned to the caller, but no UI shows it.

## Post-processing inside `parse_field_block` (`AI/referral_schema.py:345`)

In call order: `clean_special_instructions` → `merge_form_fields` / `explicit_form_fields` (labelled form values, which fill only blanks and flag disagreements) → `read_referral_number` (the printed page-1 number wins over the model) → `special_evidence` → `split_claims_manager_name` → `extract_special_instructions` → `split_address` → `enforce_source_roles` → `recover_provider_identity` / `recover_provider_records` → `merge_provider_records` / `provider_summary` → `normalize_appointment` → `review_formats` (format, 2099-placeholder and ICD-10-CM flags) → `classify`.

## Module table

| Module | Role | Key entry points |
| --- | --- | --- |
| `referral_schema.py` | **The referral contract**: field groups, required/optional/provider/derived fields, the prompt, parsing, completeness, export | `FIELD_GROUPS:21`, `REQUIRED_FIELDS:59`, `PROVIDER_FIELDS:102`, `ReferralFields:302`, `parse_field_block:345`, `completeness:502`, `export_payload:538`, `force_exact_field_output:592` |
| `bedrock_core.py` | OpenAI-compatible Bedrock client; extracting text from PDF, DOCX and TXT | `extract_document_pages:157`, `join_pages:173`, `call_llm_once:181`, `run_reasoning:222` |
| `bedrock_runtime.py` | Bedrock Runtime Converse transport for the native apps | `RuntimeClient:28`, `create_bedrock_client:78` |
| `source_evidence.py` | Recovers explicitly labelled values without crossing contact roles (claimant vs provider vs adjuster). Since 2026-10-30 it also takes the employer **contact person** (never the company or instruction text), takes the attorney **person** (not the firm), and only treats codes in diagnosis/ICD context as diagnosis codes | `explicit_form_fields:30`, `special_evidence:66`, `enforce_source_roles:167`, `_employer_person` |
| `field_review.py` | Non-blocking review metadata: AI-vs-form disagreement and format flags (FCM-1.1-81–83), the 01/01/2099 placeholder-date flag and ICD-10-CM flags | `merge_form_fields:64`, `review_formats:93`, switch `FLAG_INCOMPLETE_ICD10` |
| `icd10.py` + `data/icd10cm_2027.txt` | Checks diagnosis codes against the official CMS **FY2027 ICD-10-CM** list (98,403 codes, 74,879 billable). Regenerated by `scripts/build_icd10cm_list.py` | `check(code)` → `valid` / `incomplete` / `invalid` / `unchecked` |
| `referral_number.py` | Reads the printed **Referral Number** from the page-1 header (label on the same line or the next line; digits only) | `read_referral_number` |
| `document_sections.py` | Keeps Special Instructions verbatim across page breaks | `extract_special_instructions:36` |
| `provider_evidence.py`, `provider_records.py` | Provider records: recover from labels, merge compatible mentions, never invent a second provider. Since 2026-10-30: one physical visit = one record across Provider Information, Referral Instructions and Special Instructions; a named organisation is never split into a doctor's name; Provider Phone keeps the base number only | `recover_provider_records:80`, `merge_provider_records:76`, `provider_display_name:32`, `provider_phone_base` |
| `appointment_rules.py` | Appointment parsing, the year rule, past-date and holiday checks, runner confirmation. Since 2026-10-30: `M/D/YY` is read as written, and 01/01/2099 means no appointment | `normalize_appointment:59`, `reconcile_model_appointment_years:77`, `appointment_checks:140`, `confirm_appointments:176` |
| `address_normalization.py`, `address_enrichment.py` | Splitting addresses; explicit, reviewable US Census lookup. Never guesses an absent street | `split_address:17`, `suggest_addresses:62`, `apply_suggestions:118` |
| `injury_classification.py` | Maps free text to the RRS Body Part / Injury Type / Injury Cause dropdown values. SLB re-exports it | `resolve_body_part:69`, `resolve_cause:232`, `match_item:274` |
| `daily_output.py` | Daily Excel interchange (`Output/AI/` or `FCM_AI_OUTPUT_DIR`), read by CMSCustomerSearch | `output_directory:41`, `save_daily_output:88`, `read_record:217`, `reopen_input:249` |
| `referral_json.py` | **One JSON file per referral**: whitelisted, atomic, full source text kept by owner decision, credentials redacted | `ReferralRecord`; directory resolution `_directory:138` |
| `inference_settings.py` | Output-token budget and truncation check | `check_output_limit:7` |
| `referral_attachments.py` | Metadata-only validation of a selected referral document | `referral_document:8` |
| `rrs_assignment.py` | **RRS Complete Assignment** (option 19 + Unity case lookup + Case Id), used by Unity | `confirm_unity_login:5`, `complete_assignment:35` |
| `unity_browser.py`, `unity_completion.py`, `unity_ncm.py`, `unity_errors.py` | Unity Chrome session, the Complete Task click, post-approval NCM assignment, value-free error types | `UnityBrowserSession:8`, `complete_task:57`, `assign_ncm:91` |
| `export_rrs_dropdowns.py` | One-off capture of the live RRS dropdown lists | `capture:29` |
| `batch_samples.py` | Sample-PDF regression runner (uses `Samples for AI/`, which is sensitive) | `run_samples:233` |
| `ai_fcm_bedrock.py`, `ai_fcm_bedrock_runtime.py`, `launch_bedrock.py`, `*_ui.py` | Older Streamlit and Tk reader UIs; see [[code/ai-pdf-reader]] | — |

## Where the per-referral JSON goes (`AI/referral_json.py:126-156`)

1. If `FCM_REFERRALS_DIR` is set (Final Code also accepts `FCM_FINAL_CODE_AUDIT_DIR`), use it. It must be absolute and outside any Git worktree.
2. A frozen EXE uses a `Referrals` folder next to the EXE, unless that folder is inside a Git worktree.
3. Otherwise, for example a source run, it falls back to `%LOCALAPPDATA%/FCM_Structured/<app>/Referrals`.

Treat these files as PHI: they hold the full captured text. Retention isn't decided yet (FCM-1.1-46).

## Rules worth remembering

- `Not found` is the model's "absent" value. Convert it to `""` before legacy truthiness checks (`Final Code/finalcode/field_adapter.py:91`).
- `completeness()` returns `Passed` or `Failed`. Final Code continues only on `Passed`. A green gate checks that fields are present, not that their formats are valid.
- Section-reader evidence may only fill blanks or raise a flag. It must never overwrite a model value (the fix in FCM-1.1-81).

## Rules added 2026-10-30 (50-sample review)

The owner reviewed 50 Opus extractions of owner-confirmed synthetic samples. Feeding hand-written correct answers through the real parser showed most errors came from **Python post-processing**, not the model. Synthetic regressions: `tests/unit/test_sample_provider_regressions.py`, `test_sample_special_regressions.py`, `test_icd10_validation.py`, `test_referral_number.py`.

- **Appointment source precedence stays.** The date comes from Special Instructions even when Referral Instructions prints another year for the same visit. A past Special Instructions year (an obvious typo, e.g. a two-digit `M/D/YY` year far in the past) is normalised as written and falls under the **past-date** review flag. It is never silently replaced by the other section's year.
- **01/01/2099** is a placeholder: the date becomes `Not found` and gets a non-blocking review flag. It never counts as a future appointment.
- **One visit, one provider record.** Repeated mentions are merged when the identity, address and time agree. Genuinely different providers or visits stay separate.
- **Facility vs doctor.** A named organisation (for example "… Occ Med", "… Partners") is a facility, not a doctor. `DR SURNAME FACILITY` keeps only the surname as the doctor.
- **Provider Phone** stores the base number without an extension. Attorney phones keep their extension.
- **Employer contact** is the person from "Employer name or contact" (or the Phone # line that follows it), never the company or instruction prose.
- **Attorney Name** is the person; the Attorney Information spelling wins over Special Instructions.
- **Claims Case Manager**: an identifier-shaped value is never split into a person's name.
- **NCM**: a lone given name is completed from a matching nurse e-mail (`first.last`).
- **Diagnosis codes.** Spine levels (T12, L4-L5, C5) are never codes. Codes are copied exactly as printed and checked against ICD-10-CM: **invalid** codes and codes that **couldn't be checked** are flagged. The **incomplete** flag (a real but non-billable category, such as M54.5) is switched off for now by owner request; set `FLAG_INCOMPLETE_ICD10 = True` in `AI/field_review.py` to turn it back on. Codes are never changed.
- **Referral Number.** A new optional field, read straight from the page-1 header. The form value wins over the model, and a model disagreement gets a review flag. With no label on page 1 it's `Not found`, even if the model guesses a number.

Still pending owner decisions: whether a doctor named only in the clinical objective ("please set up an appointment with …") counts as a provider; whether CMS Registration's attachment step should use the Referral Number. Released 2026-10-30 in `workbench-v1.2.0` (AI PDF Reader) and `finalcode-v1.0.10` (Final Code), both built from `9774a34` (FCM-1.1-131). Verified by unit suites and synthetic self-tests only; no live RRS, CMS or Opus run. The long-form rule log is `AI/EXTRACTION_RULES.md` (outside the vault).

## Related

[[code/ai-pdf-reader]] · [[code/final-code]] · [[code/data-contracts]] · [[code/testing]]

## Open questions

- Retention and expiry for per-referral JSON (FCM-1.1-46).
- Live viewer-text coverage (all pages captured?) is not proven. See the parked extraction diagnostic in [[INSTRUCTIONS]].
