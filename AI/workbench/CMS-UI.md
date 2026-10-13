# CMS section integration

The Reader owns the single 480px window. Six ui components are copied byte-for-byte from the standalone CMS frontend; its files remain unchanged. Tailwind v4 uses CSS @theme (no tailwind.config.js): styles.css supplies the copied components' border/ink/ink-muted/accent/surface-muted tokens. Existing button/input remain unchanged.

## In-process driver contract

From the orchestration worker, pass `notify=api.notify` and `confirm=api.confirm` to the existing `run_live(..., stage='all')`. These callbacks are deliberately raw Python callbacks, not @response envelopes: confirm returns bool, notify returns None after acknowledgement. Never invoke them on the native UI thread or while holding api._lock. No isolated worker or pipe is added.

Call `api.set_workflow_result(None)` when starting a new chain, then `api.set_workflow_result(result)` with the orchestrator result when it returns. Both methods use the bridge response envelope; check `ok`. The result is detached and kept in memory only, exposed as get_state().workflow_result. This UI surface does not launch or alter orchestration.

Prompts appear as get_state().pending_prompt with id/kind/title/message. `answer_prompt(id, bool)` rejects stale IDs, invalid answers, or no pending prompt. The waiting worker uses an Event outside the state lock, allowing polling and answers. Concurrent prompts are rejected rather than replacing an unanswered prompt. A native resize failure clears the pending prompt and propagates instead of hanging the caller.

Both notification and confirmation automatically leave compact mode before waiting. Re-entry is refused while a prompt is pending; the frontend also defensively expands if polling sees a compact prompt. Normal form drafts stay mounted. No automatic return to compact mode after an answer. Notifications require Acknowledge; confirmations require Yes/No. Escape/outside click/X cannot silently dismiss a blocking prompt. Bridge errors stay visible inside the dialog for retry.

## Presentation

- completed: green, 'workflow finished'.
- ended: slate, 'workflow did not continue'; incomplete lists missing fields and appointment confirmations.
- stopped: amber, 'business stop, not completed', prominent reason and manual/email instruction for tire_customer_open_tcm.
- failed: red, 'technical failure', error stage/type/message.

Resolved customer is the returned CMS value, never the extracted employer. Cases use vertical cards with stacked label/value pairs and wrapping. Unknown reasons are displayed rather than dropped.

The orchestrator can return failed from a downstream failed status without an error object. The UI explicitly says no structured error details were supplied in this case; it does not fabricate stage/type/message.

## Verification

Synthetic-only regression results: 324 passed / 1 skipped Python unit tests; 36 SLB unittest tests OK; 10 Edge Playwright tests passed; tsc -b and Vite build passed with output under the active profile scratch directory (not repo dist).

Playwright proves portals are outside the app root, z-index >= 50, hit-test above the page, fit the 480px viewport, expand compact mode and return Yes/No/Acknowledge. They are in-page dialogs, not separate native windows that could fall behind the always-on-top parent. Headless browser tests cannot prove Windows topmost ordering against other native applications, WebView2 native resize/focus behavior, or the live RRS/CMS/Bedrock chain. Those require an attended desktop smoke test; no EXE was rebuilt.

Added direct dependencies: @radix-ui/react-dialog ^1.3.1 (modal), @radix-ui/react-label ^2.1.17 (label), @radix-ui/react-scroll-area ^1.4.0 (scroll area), @radix-ui/react-select ^2.4.1 (select). Existing clsx, tailwind-merge and class-variance-authority were reused. npm also deduplicated react-slot from locked 1.4.0 to 1.5.0 within its existing range for the new Radix dependency graph. npm audit reported zero vulnerabilities.
