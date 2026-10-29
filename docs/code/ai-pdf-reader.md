---
tags: [code, ai, app, reader]
sources: [AI/workbench/backend.py, AI/workbench/launcher.py, AI/workbench/window_layout.py, AI/workbench/secret_store.py, AI/workbench/CMS-UI.md, AI/workbench/README.md, AI/launch_bedrock.py]
verified_at: b47ced0 (2026-10-28)
---
# AI PDF Reader (FCM Workbench) app

**Summary.** The AI PDF Reader is the **stand-alone app of the AI PDF Analyzer module** (`AI/`, see [[code/ai-shared-modules]]). It is a narrow desktop window: pywebview on Edge WebView2, with a React + TypeScript + Vite + Tailwind front end. The operator loads a referral PDF/DOCX/TXT, runs Bedrock extraction through the shared `AI/` pipeline, reviews and edits the fields, then saves to the daily workbook and the per-referral JSON. **Final Code reuses the same backend and front end**, in `memory_only` mode with text captured from RRS ([[code/final-code]]). The field form is built from `FIELD_GROUPS` (`backend.py:449`), so a new schema field such as Referral Number appears without a front-end rebuild.

| | |
| --- | --- |
| Launcher | `python -m AI.workbench.launcher` → `AI/workbench/launcher.py:16` `launch_window` |
| Bridge | `AI/workbench/backend.py:59` `WorkbenchAPI`; the front end polls `get_state()` |
| Front end | `AI/workbench/frontend/src/` (`App.tsx`; components `FieldForm`, `CmsSection`, `LivePrompt`, `PdfPreview`, `SettingsForm`, `StatusBadge`) |
| Window | 480 × 900 logical, minimum height 600, fixed width, compact mode (`window_layout.py:3-5`) |
| Saved secrets | DPAPI-encrypted, opt-in, for the current Windows user only: `%LOCALAPPDATA%/FCM_Structured/credentials` (`secret_store.py:24`). Holds the Bedrock key and model, and CMS sign-in for Final Code |
| EXE | `dist/AI-FCM-Workbench.exe` from `AI/workbench/build.ps1` + `workbench.spec`; tag family `workbench-v*` (latest `workbench-v1.2.0`, 2026-10-30, GitHub **Latest**) |

## Bridge API (`WorkbenchAPI`, `AI/workbench/backend.py`)

- **State and window:** `get_state:141`, `set_compact:162`, `set_stage:178`, `set_unsaved:826`.
- **Documents:** `import_text:417` (Final Code's captured text), `choose_documents:421`, `get_document:441`, `render_page:475`, `export_document:803`, `open_output:834`.
- **Settings and model:** `save_settings:510`, `test_connection:566`, `forget_credential:265`.
- **Work:** `start_processing:646` (extraction on a daemon thread), `save_fields:726`, `confirm_appointment:779`, `retry_save:790`.
- **Attended prompts, used by Final Code:** `notify:233`, `confirm:237`, `request_cms_credentials:241`, `answer_prompt:277`, `wait_for_review:322`, `answer_review:344`, `set_workflow_result:197`.

Pattern: long work runs on a worker thread. Prompts and reviews wait on an `Event` **outside** the state lock, and the UI answers by prompt or review ID; stale IDs are rejected. Every blocking prompt leaves compact mode first, so it can't hide (`AI/workbench/CMS-UI.md`).

## How the front end presents CMS outcomes (`CMS-UI.md`)

completed = green; ended = slate (lists the missing fields); stopped = amber, a business stop with the manual instruction; failed = red, with stage, type and message. The resolved customer shown is the CMS value, never the extracted employer.

## Older readers (separate EXEs, not "the AI PDF Reader")

| Entry | UI | Notes |
| --- | --- | --- |
| `AI/launch_bedrock.py` (`BedrockApp:22`) | Native Tk | Built by `AI/bedrock.spec` → `AI-FCM-Bedrock-Runtime.exe`, tag family `bedrock-runtime-v*` (latest v1.5.6) |
| `AI/ai_fcm_bedrock.py`, `AI/ai_fcm_bedrock_runtime.py` | Streamlit | Excluded from the Workbench build (`workbench.spec:13`) |

## Related

[[code/ai-shared-modules]] · [[code/final-code]] · [[code/build-and-release]] · [[code/configuration]]

## Open questions

- None specific to the app. The extraction caveats live in [[code/ai-shared-modules]].
