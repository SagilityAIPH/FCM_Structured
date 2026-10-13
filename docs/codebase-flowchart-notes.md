# FCM codebase flowchart

Prepared on 2026-09-24 from the existing graphify graph and verified against current source. Diagram: `codebase-flowchart.mmd` (Mermaid). Miro publication is pending an available Miro connection in this session.

The diagram summarizes the desktop workflow, CMS compatibility layer, and separate AI tools. Solid arrows represent control, data, or delegation relationships; dotted arrows represent supporting configuration and logging. It is a static source map, not evidence that production automation succeeds.

## Source anchors

- `main.py` and `src/fcm_intake/__main__.py`: desktop entry point.
- `src/fcm_intake/app.py:359`: access check; `:401`: logging and worker cleanup; `:411`: worker launch.
- `src/fcm_intake/runners/fcm.py`: dynamic legacy loading and notification injection. Credential setup and module injection in this runner are commented out.
- `src/fcm_intake/legacy/legacy_fcm.py:3992`: referral parsing and Subject Line Template Builder workflow; `:4794`: reopen check; `:4849`: customer check; `:7063`: main orchestration and manual approval gate.
- `src/ReOpenCheck_shared.py` and `src/CustomerCheckerV2_shared.py`: re-export the packaged workflow wrappers. The full flow reaches those same wrappers through these compatibility modules.
- `src/fcm_intake/workflows/reopen_check.py` and `customer_checker.py`: shared session initialization, binding, and delegation to legacy modules.
- `src/fcm_intake/runners/customer_checker.py` and `reopen_check.py`: standalone runner entry points; these are not exposed as active buttons by the current desktop UI.
- `AI/ai_fcm_bedrock_runtime.py`: Streamlit extraction via Bedrock Converse, field cleanup, and one corrective retry.
- `AI/ai_fcm_bedrock.py`: alternate Streamlit extraction via the OpenAI-compatible Bedrock Mantle API.
- `AI/batch_samples.py`: runtime core extraction without importing the Streamlit UI, resumable batch runs, review export, and scoring.

## Current wiring caveats

- No automatic connection from the AI outputs into the desktop FCM workflow was identified; the diagram keeps those flows separate.
- The full-flow customer-check call supplies `app=app`, while the packaged `MainCustomerCheck` wrapper accepts only three positional parameters. That call can raise a `TypeError`; the diagram depicts intended delegation with this known source-level mismatch.
- The full-flow runner receives a context but currently leaves its credential/session setup commented out. The standalone runners explicitly set credentials.
- Branches inside large legacy routines are summarized. Missing information, case-specific rules, and operator decisions can stop automation before completion.

## Miro layout brief

Title: **FCM Intake — Codebase and Workflow**. Use three frames: Desktop Automation, CMS Integration, and AI Extraction. Keep the desktop workflow top-to-bottom; place CMS dependencies alongside its reopen/customer steps and AI in a separate frame. Blue = entry/UI; amber = decision; purple = external system; green = output. Add the current wiring caveats as a note beside the desktop frame. Do not connect AI output to the desktop flow.
