---
tags: [code, configuration, settings, security]
sources: [src/fcm_intake/config.py, config/local_settings.example.ini, config/context.md, AI/bedrock_core.py, AI/ai_fcm_bedrock_runtime.py, AI/referral_json.py, AI/daily_output.py, AI/workbench/secret_store.py, Processes/CMS-Registration/Deploy-Ready/cms_steps.py]
verified_at: b47ced0 (2026-10-28)
---
# Configuration and settings (names only)

**Summary.** Machine-specific paths go in `config/local_settings.ini`. Secrets and connection strings go in **environment variables or external `.env` files**, never in Git. Credentials typed by an operator stay in memory, except where the operator opts in to the DPAPI store. This note lists **setting names only**; never put values in the vault.

## Where settings are read from (`src/fcm_intake/config.py`)

| Concept | Source run | Frozen EXE |
| --- | --- | --- |
| `PROJECT_ROOT` (bundled resources) | the repo root | `sys._MEIPASS` (`:8`) |
| `SETTINGS_ROOT` (operator-editable files) | the repo root | **the EXE's folder** (`:11`) |
| `local_settings.ini` | `config/local_settings.ini` | `config/local_settings.ini` next to the EXE (`:12`) |
| `.env` files (never override real environment variables) | `.env`, `AI/.env`, `Processes/Reopen-Check/Stand-Alone/.env` under `SETTINGS_ROOT` (`:15-35`) | the same paths, relative to the EXE's folder |

`get_local_setting(section, key, *env_names)` (`:84`) resolves in this order: **environment variables, then the INI, then the built-in default** (`_DEFAULTS:62`).

## `local_settings.ini` keys (template: `config/local_settings.example.ini`)

| Section.key | Env overrides | Used by |
| --- | --- | --- |
| `browser.edge_path` | `FCM_EDGE_PATH`, `EDGE_PATH` | CMS IE mode in Edge |
| `browser.ie_driver_path` | `FCM_IE_DRIVER_PATH`, `IE_DRIVER_PATH` | CMS automation. Default: `dist/browser-drivers/IEDriverServer.exe` (source) or `drivers/IEDriverServer.exe` inside the EXE |
| `browser.edge_driver_path` | `FCM_EDGE_DRIVER_PATH`, `EDGE_DRIVER_PATH` | Edge service; blank uses Selenium Manager |
| `browser.chrome_driver_path` | `FCM_CHROME_DRIVER_PATH`, `CHROME_DRIVER_PATH` | **Unity only**; blank uses Selenium Manager with the installed Chrome. No Edge fallback |
| `folders.attachment_folder` | `FCM_ATTACHMENT_FOLDER` | Unity attachment export and pickup |
| `cms.login_url`, `cms.case_search_url` | `FCM_CMS_LOGIN_URL`, `FCM_CMS_CASESEARCH_URL` | CMS navigation |
| `cem.environment`, `cem.employer_search_url`, `cem.employer_add_url`, `cem.cem_log_path`, `cem.allow_placeholder_address` | `FCM_CEM_ENVIRONMENT`, `FCM_CEM_EMPLOYER_SEARCH_URL`, `FCM_CEM_EMPLOYER_ADD_URL`, `FCM_CEM_LOG_PATH`, `FCM_CEM_ALLOW_PLACEHOLDER_ADDRESS` | CEM app ([[code/cem]]); `cem_log_path` also CMS Registration. Environment defaults to `uat`; URLs and log path have no defaults |

## Environment variables by area

| Name | Purpose | Read at |
| --- | --- | --- |
| `FCM_RRS_DB_CONNECTION` | Unity **tracking** INSERT; also explicitly authorized for CMS Registration's RRS-mode stored-procedure lookup on 10/29/2026; not required for Excel setup mode | `config.get_rrs_db_connection:38`; Registration `Stand-Alone/backend.py` |
| `FCM_CMS_DB_CONNECTION` | CMS connection used by other CMS workflows; not the Registration lookup source or fallback | Existing CMS consumers; Registration RRS mode requires the RRS setting; Excel mode uses neither DB setting |
| `FCM_CMS_REFERENCE_DIR` | The folder holding the Claims Office Matrix and Dedicated Supervisor Mapping for CMS Registration | same |
| `FCM_LM_MATRIX` | Claims Office Matrix path for the SLB adjuster lookup | `Processes/SubjectLineBuilder/Deploy-Ready/office_matrix.py:258` |
| `OPENAI_API_KEY` | Bedrock key (OpenAI-compatible endpoint) when none is typed in the app | `AI/bedrock_core.py:28` |
| `AWS_BEARER_TOKEN_BEDROCK`, `AWS_REGION`, `BEDROCK_MODEL_ID` | Older Streamlit/runtime readers | `AI/ai_fcm_bedrock_runtime.py:97`, `AI/ai_fcm_bedrock.py:130-136` |
| `FCM_AI_OUTPUT_DIR` | Daily workbook folder (default `Output/AI/`, or next to the EXE) | `AI/daily_output.py:41` |
| `FCM_REFERRALS_DIR` (Final Code also accepts `FCM_FINAL_CODE_AUDIT_DIR`) | Per-referral JSON folder; must be absolute and outside Git | `AI/referral_json.py:138` |
| `FCM_CMS_USERNAME`, `FCM_CMS_PASSWORD` (also `CMS_USER`, `CMS_PASSWORD`) | Default sign-in for the CMSCustomerSearch CLI and desktop | `Processes/Reopen-Check/Stand-Alone/run.py:85`, `webview_app.py:50` |

## Credentials by app

| App | CMS sign-in | Bedrock key |
| --- | --- | --- |
| AI PDF Reader | — | Typed in Settings; optional DPAPI save |
| Final Code | Attended prompt; optional DPAPI save; a rejected saved pair is erased | as the Reader |
| CMSCustomerSearch | Form or prompt; env defaults above | — |
| Unity Assignment | Attended manual sign-in pause for Unity; DB from `FCM_RRS_DB_CONNECTION` | — |
| CMS Registration | UI fields or per-run prompt; optional env prefill, memory only; never in run state/results | — |
| Legacy app | `BotContext` from the CustomTkinter login fields → `cms/session.set_credentials` | — |

**DPAPI store** (`AI/workbench/secret_store.py:24`): `%LOCALAPPDATA%/FCM_Structured/credentials`, encrypted for the current Windows user. It doesn't protect against other code running as that same user.

## Rules

- Never commit `.env`, `config/local_settings.ini`, connection strings or credentials. Never reproduce them in notes, release assets or logs.
- `CMS.py`'s `__main__` example contains a hard-coded server name and username (FCM-1.1-107). Treat it as sensitive.
- A packaged EXE reads **its own folder's** `config/local_settings.ini` and `.env`, not the repo's.

## Related

[[code/CODE-MAP]] · [[code/build-and-release]] · [[code/legacy-code]]

## Open questions

- Registration lookup connection resolved on 10/29/2026 (FCM-1.1-165): read-only metadata found the lookup through RRS, and the owner explicitly authorized that setting for this lookup only. The initial filled form had no matching referral; a later guarded FCM-1.1-168 UI run completed DATA and reached REVIEW. This is not save-enabled end-to-end or RRS completion validation.
