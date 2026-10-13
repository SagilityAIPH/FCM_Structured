# Graph Report - .  (2026-09-01)

## Corpus Check
- Large corpus: 737 files · ~395,419 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 486 nodes · 830 edges · 42 communities (33 shown, 9 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 41 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Bedrock Runtime AI Integration
- Bedrock AI Integration
- Customer Checker V2 / Address Lookup
- Legacy Google Search Automation
- CMS Selenium Automation
- FCM Intake V3 Migration Context
- FCM Bot App UI
- Legacy Customer Checker Automation
- Legacy CEM Claim Automation
- Edge Browser Driver Setup
- Shared Browser Session Management
- Legacy Reopen Check Automation
- Legacy Module Loader
- Local Settings Config
- Customer/Reopen Check Shared Workflows
- Environment Config Assumptions
- Customer Checker Entry Point
- Reopen Check Entry Point
- Migration Gaps & Next Steps
- Dependency Manifest Gap
- Main Entry Point
- Verification Status Note
- Exception Handling Note
- FCM Intake Package Marker
- IE Driver Path Config

## God Nodes (most connected - your core abstractions)
1. `searchCase()` - 21 edges
2. `force_exact_field_output()` - 16 edges
3. `force_exact_field_output()` - 16 edges
4. `FcmBotApp` - 16 edges
5. `CreateSubjectLineBuilder()` - 16 edges
6. `App` - 15 edges
7. `ValidateCustomer()` - 12 edges
8. `is_bad_value()` - 11 edges
9. `is_bad_value()` - 11 edges
10. `normalize_employer_contact_fields()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `app_ui_v2.py` --semantically_similar_to--> `src/fcm_intake/app.py (CustomTkinter UI)`  [INFERRED] [semantically similar]
  docs/v2_assessment.md → README.md
- `runners/` --semantically_similar_to--> `src/fcm_intake/runners/`  [INFERRED] [semantically similar]
  docs/v2_assessment.md → README.md
- `cms_session.py` --semantically_similar_to--> `src/fcm_intake/cms/`  [INFERRED] [semantically similar]
  docs/v2_assessment.md → README.md
- `CustomerCheckerV2_shared.py` --semantically_similar_to--> `src/fcm_intake/workflows/`  [INFERRED] [semantically similar]
  docs/v2_assessment.md → README.md
- `ReOpenCheck_shared.py` --semantically_similar_to--> `src/fcm_intake/workflows/`  [INFERRED] [semantically similar]
  docs/v2_assessment.md → README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **V2-to-V3 Module Migration Mapping** — docs_v2_assessment_app_ui_v2_py, docs_v2_assessment_cms_session_py, docs_v2_assessment_runners, docs_v2_assessment_legacy, readme_src_fcm_intake_app_py, readme_src_fcm_intake_cms, readme_src_fcm_intake_runners, readme_src_fcm_intake_legacy [INFERRED 0.85]
- **FCM V2 Codebase Structural Issues** — docs_v2_assessment_mixed_responsibility, docs_v2_assessment_duplicated_concepts, docs_v2_assessment_hardcoded_environment_assumptions, docs_v2_assessment_global_shared_state, docs_v2_assessment_broad_exception_handling, docs_v2_assessment_no_dependency_manifest, docs_v2_assessment_no_test_coverage [INFERRED 0.85]
- **V3 Cleanup Verification Flow** — config_context_current_goal, config_context_verification_run, config_context_known_gaps, config_context_recommended_next_step [INFERRED 0.75]

## Communities (42 total, 9 thin omitted)

### Community 0 - "Bedrock Runtime AI Integration"
Cohesion: 0.06
Nodes (62): add_date_fix_suggestion(), call_llm_once(), clean_appointment_fields(), clean_employer_contact_name(), clean_joined_value(), clean_ncm_value(), clean_plain_text_output(), clean_provider_name() (+54 more)

### Community 1 - "Bedrock AI Integration"
Cohesion: 0.07
Nodes (60): add_date_fix_suggestion(), call_llm_once(), clean_appointment_fields(), clean_employer_contact_name(), clean_joined_value(), clean_ncm_value(), clean_plain_text_output(), clean_provider_name() (+52 more)

### Community 2 - "Customer Checker V2 / Address Lookup"
Cohesion: 0.08
Nodes (44): AddrParts, address_callback(), apply_google_provider_result(), build_provider_search_text(), CompleteAssignment(), CompleteTriageAndExportAttachment(), CreateSubjectLineBuilder(), extract_appt_address_block() (+36 more)

### Community 3 - "Legacy Google Search Automation"
Cohesion: 0.09
Nodes (29): accept_google_consent_if_any(), address_score(), App, _clean(), clean_provider_name(), compute_confidence(), detect_google_block_or_captcha(), _digits_only() (+21 more)

### Community 4 - "CMS Selenium Automation"
Cohesion: 0.12
Nodes (35): Ie, CaseData, claim_exists(), create_ie_driver(), element_check(), element_click(), elementExist(), ensure_executable_path() (+27 more)

### Community 5 - "FCM Intake V3 Migration Context"
Cohesion: 0.07
Nodes (31): src/fcm_intake/config/__init__.py, Current Goal: Behavior-Preserving Migration, FCM-Intake-V2, FCM Intake V3 Context, Guardrails (do not change business logic), src/fcm_intake/ package, Starter smoke/unit tests, tools/agent-pack/ (+23 more)

### Community 6 - "FCM Bot App UI"
Cohesion: 0.13
Nodes (6): Queue, FcmBotApp, QueueWriter, resolve_current_user(), BotContext, main()

### Community 7 - "Legacy Customer Checker Automation"
Cohesion: 0.16
Nodes (25): create_ie_driver(), customer_prompter_and_cem(), element_check(), element_click(), elementExist(), find_iedriver_path(), get_driver(), get_ecode_for_customer() (+17 more)

### Community 8 - "Legacy CEM Claim Automation"
Cohesion: 0.14
Nodes (22): add_claim_record(), create_workbook_if_missing(), custSearch(), elementExist(), employerSearch(), ensure_headers(), get_excel_path(), get_next_empty_row() (+14 more)

### Community 9 - "Edge Browser Driver Setup"
Cohesion: 0.14
Nodes (12): build_edge_service(), find_msedge_path(), CheckCaseUnity(), find_msedge_path(), Try to locate msedge.exe from common Windows install paths.     You can also ov, create_driver(), login(), main() (+4 more)

### Community 10 - "Shared Browser Session Management"
Cohesion: 0.22
Nodes (13): create_ie_driver(), _driver_alive(), element_check(), element_click(), element_exist(), execute_js_with_refresh(), find_iedriver_path(), get_shared_driver() (+5 more)

### Community 11 - "Legacy Reopen Check Automation"
Cohesion: 0.25
Nodes (15): create_ie_driver(), element_check(), element_click(), elementExist(), get_driver(), init_cms_session(), legacy_safe_type(), MainReopenCheck() (+7 more)

### Community 12 - "Legacy Module Loader"
Cohesion: 0.29
Nodes (8): _ensure_legacy_compat(), load_module_from_path(), Path, run_fcm(), Path, test_load_module_from_path_loads_temp_module(), test_load_module_from_path_missing_file_raises(), test_load_module_from_path_supports_legacy_absolute_imports()

### Community 13 - "Local Settings Config"
Cohesion: 0.50
Nodes (4): ConfigParser, get_local_setting(), _load_local_settings(), Read a local machine setting from env, Notepad-editable INI, then defaults.

### Community 14 - "Customer/Reopen Check Shared Workflows"
Cohesion: 0.40
Nodes (5): CustomerCheckerV2_shared.py, legacy_customerchecker.py (~902 lines), legacy_reopencheck.py (~592 lines), ReOpenCheck_shared.py, src/fcm_intake/workflows/

### Community 15 - "Environment Config Assumptions"
Cohesion: 0.50
Nodes (4): config/local_settings.ini, Hardcoded Environment Assumptions, FCM_CMS_LOGIN_URL env var, config/local_settings.ini

## Ambiguous Edges - Review These
- `cms_session.py` → `CMS.py`  [AMBIGUOUS]
  docs/v2_assessment.md · relation: conceptually_related_to
- `CustomerCheckerV2_shared.py` → `legacy_customerchecker.py (~902 lines)`  [AMBIGUOUS]
  docs/v2_assessment.md · relation: conceptually_related_to
- `ReOpenCheck_shared.py` → `legacy_reopencheck.py (~592 lines)`  [AMBIGUOUS]
  docs/v2_assessment.md · relation: conceptually_related_to

## Knowledge Gaps
- **21 isolated node(s):** `fcm-intake`, `FCM Intake V3`, `src/fcm_intake/app.py (CustomTkinter UI)`, `src/fcm_intake/runners/`, `FCM_CMS_LOGIN_URL env var` (+16 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `cms_session.py` and `CMS.py`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `CustomerCheckerV2_shared.py` and `legacy_customerchecker.py (~902 lines)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `ReOpenCheck_shared.py` and `legacy_reopencheck.py (~592 lines)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `CheckCaseUnity()` connect `Edge Browser Driver Setup` to `CMS Selenium Automation`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Why does `find_msedge_path()` connect `Edge Browser Driver Setup` to `Legacy Customer Checker Automation`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `FcmBotApp` (e.g. with `BotContext` and `main()`) actually correct?**
  _`FcmBotApp` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `CreateSubjectLineBuilder()` (e.g. with `address_callback()` and `find_provider_address()`) actually correct?**
  _`CreateSubjectLineBuilder()` has 4 INFERRED edges - model-reasoned connections that need verification._