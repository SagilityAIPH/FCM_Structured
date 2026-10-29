---
tags: [code, testing]
sources: [tests/unit, tests/smoke, Processes/CMS-Registration, Processes/SubjectLineBuilder/Stand-Alone, Processes/Unity/Stand-Alone, Processes/Reopen-Check/Stand-Alone, AI/workbench/frontend/e2e]
verified_at: b47ced0 (2026-10-28)
---
# Testing

**Summary.** All automated tests are **synthetic and offline**: fake drivers, fake desktops, fake databases and made-up referrals. They prove the control flow, the business rules and the packaging. They **don't** prove live RRS, CMS, Unity, Bedrock or database behaviour. Run everything from the repo root with `.venv-bedrock/Scripts/python.exe` (`python3` isn't installed). Never use real referrals, `Samples for AI/` or `Output/` as fixtures.

## Suites and results (re-run 2026-10-30 at `9774a34`; smoke, scenarios and front end last run 2026-10-28 at `b47ced0`)

| Suite | Command (from the repo root) | Result |
| --- | --- | --- |
| Main unit (`tests/unit`, 36 files) | `.venv-bedrock/Scripts/python.exe -m pytest tests/unit -q -p no:cacheprovider` | 663 passed, 1 skipped, 82 subtests |
| Smoke (`tests/smoke`) | `… -m pytest tests/smoke -q -p no:cacheprovider` | 1 passed |
| Subject Line Builder standalone | `… -m unittest discover -s Processes/SubjectLineBuilder/Stand-Alone -p "test_*.py"` | 70 OK |
| CMS Registration core | `… -m unittest discover -s Processes/CMS-Registration/Deploy-Ready -p "test_*.py"` | 39 OK |
| CMS Registration app | `… -m unittest discover -s Processes/CMS-Registration/Stand-Alone -p "test_*.py"` | 14 OK |
| CMS Registration scenarios | `… Processes/CMS-Registration/Stand-Alone/run.py --self-test --report <file>` | 14/14 |
| Unity standalone | `… -m pytest Processes/Unity/Stand-Alone -q -p no:cacheprovider` | 153 passed, 559 subtests |
| CMS Customer Search standalone | `… -m pytest Processes/Reopen-Check/Stand-Alone -q -p no:cacheprovider` | 18 passed, **1 failed** (see below) |
| Reader front end | `npm --prefix AI/workbench/frontend run build`, then `run test:e2e` (Edge Playwright, 9 spec files) | not run for this note |

## What the main unit suite covers (`tests/unit`)

The AI pipeline (`test_referral_schema`, `test_source_evidence`, `test_field_review*`, `test_provider_*`, `test_injury_classification`, `test_address_enrichment`, `test_appointment_display`, `test_document_sections`). Persistence (`test_daily_output`, `test_referral_json*`, `test_secret_store`). The Reader (`test_workbench`, `test_bedrock_*`). Final Code (`test_final_code_*`: adapters, app, audit, orchestrator, package). CMS plumbing (`test_cms_*`). Configuration (`test_config_paths`, `test_local_settings`, `test_legacy_loader`). Unity's controller (`test_unity_flow`). Added 2026-10-30 from the 50-sample review: `test_sample_provider_regressions`, `test_sample_special_regressions`, `test_icd10_validation`, `test_referral_number` (all synthetic values).

## Known test-harness issues (observed, not fixed)

- **Unity with `unittest discover`.** The README's `unittest discover -s Processes/Unity/Stand-Alone` command fails 6 subtests of `ChromeDriverTests.test_shared_chrome_factory_manager_static_path_and_opt_in_detach`: "Options is not an instance of Options", which looks like Selenium being imported twice. The same tests **pass under pytest**. This is a test-isolation artifact, not a product failure.
- **CMS Customer Search on this machine.** `test_portable.PortableTests.test_frozen_settings_use_executable_folder_and_precedence` fails comparing a long temp path with its 8.3 short form (`ADMINI~1`). It's environment-dependent.
- **CMS Registration under one pytest run.** `pytest Processes/CMS-Registration` gives an **import file mismatch**, because both sub-folders have a `test_flow.py`. Run each folder separately (as above), or give the files unique basenames.

## Habits that keep tests meaningful

- Inject every stage callback and test both `Exception` and `SystemExit`.
- Load sibling standalone modules with `importlib` under **unique module names**, so the processes' `run.py` and `test_flow.py` files don't collide.
- For late Final Code stages, use a synthetic field set that **passes** the real completeness gate. An all-`Not found` fixture stops at GATE and tests nothing downstream.
- A green synthetic self-test that auto-answers a review doesn't prove the real UI has the control. Trace the state publication too.
- For packaged apps, run the EXE's own `--self-test --report` both inside and outside the repo.

## Related

[[code/build-and-release]] · [[code/CODE-MAP]]

## Open questions

- Should the three harness issues above be fixed? They're candidate backlog items, not yet allocated.
