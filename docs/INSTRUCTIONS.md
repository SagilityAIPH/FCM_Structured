# Active work instructions

## Rules

- **ID rule:** Every item gets a permanent, incrementing ID -- `FCM-1.1-NN`. When adding a new item, use the next number after the highest ID used anywhere in this file or `docs/completed.md`. IDs are never reused or renumbered, even after an item moves to `docs/completed.md`.
- **Status legend:** `[ ]` not started - `[~]` in progress - `[X]` completed
- **Completed-item format:** When an item is finished, cut it from its active-priority section and append it under **Completed** at the bottom using exactly: `- [X] [Date Completed: MM/DD/YYYY] **FCM-1.1-NN -- Item title.** Supporting note.`
- **Completed-item date placement:** Repeat the same `[Date Completed: MM/DD/YYYY]` marker at the end of the completed item line. The complete line is `- [X] [Date Completed: MM/DD/YYYY] **FCM-1.1-NN -- Item title.** Supporting note. [Date Completed: MM/DD/YYYY]`
- **Follow-up rule:** If finishing one item surfaces a risk, a possible bug, or a worthwhile improvement that is out of scope for that item, add it as a NEW item and note which item's execution uncovered it -- do not expand the item you were shipping to cover it.
- **Closing an item:** Note the test or packaged-build evidence that shows it works when you check it off. If live behavior was not tested, say so.

## Mission and working rules

1. Get the process out of the original legacy code.
2. Break it into stand-alone and deploy-ready form (`Processes/`).
3. Merge the mini processes into a final code (`Final Code/`).
4. Create a Visio flowchart afterwards -- **only on the owner's explicit signal**.
5. Merge another local repo containing the further post-Unity process; the owner will supply that repo later.
6. Use graphify for mapping; orient with the knowledge graph before changing code.

Delegate coding to workers; use at most two workers. Do not infer authorization for steps 4 or 5 from completion of earlier steps.

## Orientation

| Topic | Working instruction |
| --- | --- |
| Process layout | `Processes/<Name>/Deploy-Ready/` holds the shared controller/integration source; `Stand-Alone/` holds an independent runner, offline scenarios, tests and possibly a desktop/EXE. Both use the same implementation; the folder name does not prove live deployment readiness. Current folders: `Reopen-Check`, `SubjectLineBuilder`, `Unity`. |
| Merged chain | `Final Code/finalcode/` contains the orchestrator and adapters. Read `Final Code/PROCESS-MAP.md` for the architecture/data contracts, but verify its historical line numbers and baseline counts against current code. |
| One implementation | Do not introduce a third copy of a business rule. Reuse shared logic in `AI/`; keep integration adapters thin. |
| PHI | Do not put real claims, names, DOBs, addresses, identifiers or excerpts into docs, tests or reports. Treat `Samples for AI/`, `Output/`, `AI/.sample_runs/` and sample PDFs as sensitive; use synthetic examples. |
| Python | From the repo root use `.venv-bedrock/Scripts/python.exe` (`python3` is unavailable). |

Baseline checks (last verified 10/15/2026; these are not live RRS/CMS/Unity tests):

```bash
.venv-bedrock/Scripts/python.exe -m pytest tests/unit -q -p no:cacheprovider
# Expected: 366 passed, 1 skipped, 56 subtests passed
.venv-bedrock/Scripts/python.exe -m unittest discover -s Processes/SubjectLineBuilder/Stand-Alone -p "test_*.py"
# Expected: 36 tests, OK
```

## Current state

`Final Code/finalcode/orchestrator.py:34` defines `run(*, capture, extract, review, cms, subject_line, on_stage=None, today=None, adapt=None)`. Implemented order: `capture()` → `extract()` → `review()` → `completeness()` gate → `cms()` → one-way field adapter → `subject_line()`. CMS must resolve a nonblank customer before the Subject Line Builder stage. Its live factory now completes triage, answers the legacy prompts and exports the attachment through the existing shared RRS adapter only after a completed builder result; the same stage returns completion only after export returns. The orchestrator remains an in-memory state machine; the launcher and review hooks now persist one referral JSON through the shared writer (FCM-1.1-81).

| Condition                                                  | Outcome / reason                                         | Source                                                 |
| ---------------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------ |
| No attachment (`attachment_name is None`)                  | `ended / no_referral_attached`                           | `Final Code/finalcode/orchestrator.py:77-78`           |
| Review returns `None`                                      | `ended / operator_cancelled`                             | `Final Code/finalcode/orchestrator.py:84-88`           |
| Completeness gate is not `Passed`                          | `ended / incomplete`                                     | `Final Code/finalcode/orchestrator.py:90-96`           |
| Required CMS inputs missing                                | `failed / missing_cms_inputs`                            | `Final Code/finalcode/orchestrator.py:98-106`          |
| CMS returns stopped or failed                              | `stopped` / `failed`, with returned reason (or fallback) | `Final Code/finalcode/orchestrator.py:107-115`         |
| CMS claims completion without a resolved nonblank customer | `failed / exception`                                     | `Final Code/finalcode/orchestrator.py:116-120,135-139` |
| Callback raises, including `SystemExit`                    | `failed / exception`                                     | `Final Code/finalcode/orchestrator.py:135-139`         |

**Unity assignment is deliberately standalone and is NOT wired into Final Code.** The owner-approved post-builder boundary includes only RRS's Unity Entry attachment export, not `OpenUnity`, `CompleteAssignment`, `Processes/Unity` or database logging. The assignment process runs through `Processes/Unity/Stand-Alone/`; do not treat its absence from the chain as a defect.

## Blocked on owner signal or input

- [ ] **FCM-1.1-19 -- Draw the step-4 Visio flowchart only after explicit owner signal.** Follow `Flowcharts/Whole-Process-Visio-Specs.md`; blocked until the signal. Acceptance: owner authorization recorded, diagram checked against the style guide and the agreed process, with the source file reviewed.
- [ ] **FCM-1.1-20 -- Merge the separate repo's post-Unity process (step 5).** Blocked until the owner supplies its local repository and scope. Acceptance: supplied source mapped, integrated according to the agreed boundary, with process/integration tests and any applicable packaged-build evidence recorded.

## Housekeeping and investigation

- [ ] **FCM-1.1-21 -- Investigate graphify's 27 source files with zero nodes.** A refreshed graph reported 6,899 nodes, 10,529 edges and 801 communities from 336 files; why those 27 produced zero nodes is unverified. Acceptance: enumerate and classify the zero-node files, explain causes with graph/source evidence and record any follow-up as a separate ID.
- [ ] **FCM-1.1-22 -- Correct stale Final Code plan status.** `Final Code/PLAN.md:9` still says spec only/no code written, despite implemented `Final Code/finalcode/` modules. Acceptance: status reflects implemented scope without overstating live validation; review the doc diff and run relevant documentation/link checks.
- [ ] **FCM-1.1-23 -- Remove the duplicate claim-type selection in Subject Line Builder Create.** `Processes/SubjectLineBuilder/Deploy-Ready/rrs_ui.py:740-741` calls `select_claim_type('Lost Time')` twice in succession; the duplicate is apparently harmless. The hardcoded **'Lost Time' value is intentional per the owner and must NOT be changed**. Acceptance: only the redundant call is removed, the intended selection still executes and the standalone tests (plus relevant RRS UI tests) pass; live RRS remains unverified unless actually tested.
- [ ] **FCM-1.1-24 -- Correct the stale Unity EXE statement in the process README.** `Processes/Unity/README.md:21` says "No Unity EXE is built", but commit `0208d01` added `Processes/Unity/Stand-Alone/unity_assignment.spec` and `dist/UnityAssignment.exe` plus its `.sha256` exist on disk. The adjacent sentence -- that `Deploy-Ready/` is integration source rather than an independently packaged EXE -- remains true and should be preserved; only the "no EXE is built" claim is false. Uncovered while archiving FCM-1.1-17. Acceptance: README states where the Unity EXE is built from and what packaging evidence exists, without claiming live Unity validation.
- [ ] **FCM-1.1-25 -- Audit pre-existing address-like workbench test fixtures.** Address-like strings in `tests/unit/test_workbench.py` were introduced by commit `93a523a` and are already public, not newly introduced by this release; uncovered during the Start-gate release. Acceptance: confirm the fixtures are synthetic and record the evidence, or replace any that are not with clearly fictional placeholders without changing test coverage.
- [~] **FCM-1.1-26 -- Unblock Final Code attended review approval and cancellation.** An operator found the packaged app stuck at REVIEW on a live referral: the UI had no way to answer the pending handoff; the synthetic self-test masked this because its responder auto-answers. Source-only fix and synthetic verification are complete; no EXE rebuilt or live chain rechecked. Acceptance: Final Code alone shows pending review controls, saved edits approve, cancellation ends the run, and offline tests, scratch frontend build and synthetic self-test pass; packaged/live behavior remains separately unverified.
- [ ] **FCM-1.1-29 -- Review credential-storage threat model.** Assess the opt-in DPAPI storage added after the attended sign-in work: DPAPI is scoped to the current Windows user and does not defend against code running as that same user; a shared or roaming profile changes the threat model. Acceptance: document account/profile deployment assumptions, file ACLs, recovery/forget behavior, and any additional mitigations without recording credentials.

- [ ] **FCM-1.1-41 -- Validate RRS viewer capture against a live session.** Uncovered while executing FCM-1.1-10 (Final Code RRS-to-Reader integration): capture readiness, bounded retries and short-text rejection are verified only with synthetic UIA fakes. The current fix accepts two consecutive identical reads with at least 64 characters after trimming leading and trailing whitespace, within four attempts spaced 0.25 seconds apart; this rejects empty reads but can accept a stable first page or a thin capture. Acceptance: with operator authorization and a safe live RRS session, verify full multi-page text is exposed by DocumentRange, the character-count trace reflects the whole document, and a delayed viewer stabilizes without a manual re-run; establish an explicit page-coverage signal if UIA virtualizes pages. Do not record document content or identifiers.

  1. **Settle timing versus pagination with one probe.** Add a diagnostic path that captures and logs the character count, sends Ctrl+End / page-down to the Document control, then captures and logs the count again. Growth after scrolling indicates a virtualized viewer: `GetText(-1)` returns only materialized pages, not proof of whole-document coverage. If the count stays identical while fields are missing, investigate timing or text never exposed. One authorized live run can distinguish these paths; the probe is low risk and roughly twenty lines.
  2. **Replace the character floor with structural anchors.** Check the captured text against the document's own label strings already defined in `AI/referral_schema.py`, including anchors near both the head and tail. Head anchors present but tail anchors absent signal a truncated capture, not missing field data; all anchors present with a blank value indicate the value is genuinely absent. A 64-character floor cannot make that distinction and may cause an operator to retype a value present on a later page. Use only schema label constants, never document content, in diagnostics.
  3. **Fix the stability blind spot.** Accept only text that is both stable across reads and anchor-satisfied. If anchors are missing, keep reading through the bounded attempts even when the exposed text is identical; a stalled render is not success.
  4. **Never pass suspicious text to the model silently.** If anchors still fail after bounded attempts, do not extract. Show the character count and missing sections, and instruct the operator to scroll to the end of the document and retry. If the live probe confirms incomplete captures can reach the review form, raise the affected-field incomplete-capture badges as a separate follow-up uncovered by FCM-1.1-41, rather than silently presenting those blanks as absent data.
  5. **Log a capture fingerprint.** Log attempt number, character count, anchors hit and page count when available, never document text or identifiers, so the next live failure can be diagnosed.

  - **Scanned-page hypothesis.** UI Automation cannot expose text from image-only pages regardless of wait time; a text first page followed by a scanned page could make the same later fields disappear every time. Missing tail anchors flag this coverage problem immediately, but the live probe must distinguish a scan from virtualization or timing. If scanned pages are confirmed, raise OCR as its own larger follow-up uncovered by FCM-1.1-41; retries alone cannot recover image text.
  - **Deliberately out of scope.** Do not change extraction or the model: `make_extract` uses `temperature=0.0`, so identical captured input is effectively deterministic and extraction reports what capture handed it. Investigate the upstream text first.
  - **Deciding diagnostic.** Missing fields that vary between runs indicate a timing race the landed retry fix may resolve; the same fields missing on every run, especially toward the end, point to later pages not being exposed and the retry fix alone will not help. Confirm with the live probe rather than treating identical reads as page coverage.

- [ ] **FCM-1.1-42 -- Confirm remembered Bedrock model restore in live Reader and Final Code sessions.** Uncovered while executing FCM-1.1-29's credential-storage follow-up (the Bedrock remember-me model enhancement): key/model persistence, startup restore, UI visibility and a first-use availability check were verified only with synthetic fakes. Acceptance: with operator authorization, save a permitted model through the existing opt-in checkbox, restart both apps, confirm Settings displays that model and inference uses it; verify a retired or inaccessible model stops before extraction, selects the default visibly without silently submitting to the stale ID, and preserves the saved key. Do not record credentials or referral contents; source checks do not prove packaged behavior.

- [~] **FCM-1.1-44 -- Teach model extraction the advance-date convention for yearless appointments.** Uncovered by the operator's Appointment Date & Time Format (AI) request after FCM-1.1-43: the advance-date rule now exists in both the model prompt and Python; Python alone determines the final stored year after provider corroboration, and a conflicting model-supplied year is logged at warning level without document content. Synthetic fixed-date tests and source self-test cover the code path; live model behaviour under the new instruction remains unverified, and no EXE was rebuilt. Acceptance: confirm the live model follows the prompt on authorized input without putting referral contents in logs.

- [ ] **FCM-1.1-45 -- Confirm multi-provider extraction and review against a real referral.** Uncovered by the operator's Double Provider Issue in AI Analyzer / Multiple Provider Issue requests: per-provider JSON records, text/CSV rows and editable review groups have been checked with synthetic fixtures only. Acceptance: with operator authorization, confirm each distinct detected provider occupies one record and one separately editable review group, appointments remain attached to the correct provider, the completeness gate and downstream handoffs behave as intended, and no referral contents or identifiers enter test artifacts or logs. No live referral or packaged EXE was exercised.

- [ ] **FCM-1.1-46 -- Decide retention and access for referral records.** Uncovered by the operator's "[Final Code] Add JSON for each item worked" request. The earlier Final Code-only `AppData/Local/FCM_Structured/FinalCode/audit/` writer is replaced by FCM-1.1-81's shared Final Code/Reader records in `Referrals/` beside the EXE, an outside-Git override, or the visible `%LOCALAPPDATA%/FCM_Structured/<FinalCode|AIPDFReader>/Referrals/` fallback. **Files contain PHI, including claimant names in filenames; adjacent/shared EXE folders also need an access policy.** Retention duration, authorized access, deletion/backup and protection for a shared or roaming operator profile remain undefined. Acceptance: owner approves and documents a retention/access policy, operational cleanup and any required folder/profile ACL or encryption controls; verify with synthetic records only and do not expose referral contents in logs.

- [ ] **FCM-1.1-48 -- Verify Unity portal outcomes and attachment identity before relying on completion.** Reconfirmed during FCM-1.1-47 smoke review: the desktop recognizes the legacy outer failure marker, but inner upload/Complete Task handlers can swallow failures, and the CLI delegates to legacy `main`, which also catches errors. The controller's one-file preflight does not bind the selected file to the later legacy glob or verify its claim identity; tracking records an attempt even after a raised portal failure by default. The configured portal is UAT. Acceptance: with owner-approved environment and test scope, establish explicit upload/task readback and stable attachment binding using synthetic data, preserve the approval gate and owner-approved tracking policy, and record authorized live verification separately. Do not auto-run live assignments or integrate Unity into Final Code to resolve this item.


Owner-approved FCM-1.1-81 amendment always retains full source text (and distinct
sent text) for debugging. **FCM-1.1-46 must later define the expiry number of
days**, along with retention/access controls for those full-text records. No
expiry period or automatic deletion is implemented by FCM-1.1-81.

## Live verification follow-up

- [~] **FCM-1.1-72 -- Run the owner-authorized Unity portal and tracking live test.** Owner selected Unity portal/task completion and tracking only, explicitly excluding RRS Complete Assignment, using approved synthetic workbook row 2. The owner reports the earlier customer mismatch corrected. The configured RRS export folder was absent; the owner instead selected a local folder containing exactly one EML, bound to the source upload API without reading its contents into reports. Row 2 validates, and its present appointment time is preserved; this is not a forced missing-time flag test. Initial actual shared-controller/checked-helper execution stopped at two claimant-name results before row selection. The owner then explicitly approved selecting the first case (FCM-1.1-73). A fresh one-shot attempt selected that first exact-name result and read all four identity fields: claim number and claimant first/last names match, but the task-summary customer still does not match workbook row 2. The safety guard stopped before Assign. No upload, Complete Task, tracking or RRS completion occurred in either attempt. The checked boundary detected the source-caught guard failure, and the tracking guard refused the pre-identity write. Both test browsers remain open with driver services/executors released; original reports/attempt markers are preserved. Blocked on reconciling the first task's customer with the approved input, not on result ordering. Acceptance: owner reconciles identity, authorizes a fresh bounded attempt, and actual upload/task/tracking outcomes are independently reported without identifiers or claims based only on a normal legacy return; never replay an uncertain submission automatically.

- [ ] **FCM-1.1-71 -- Confirm safe Unity case selection when a result row cannot be read.** Uncovered while shipping FCM-1.1-70: existing `CMS.CheckCaseUnity` catches individual row failures and selects the latest valid assigned date among the remaining readable rows. A skipped row could contain a newer case, so a normal lookup return does not establish a complete result scan. The selection rule was preserved, not silently changed during extraction. Acceptance: owner approves the partial-result policy; synthetic lookup tests cover a newer unreadable row and prove that an unverified older case cannot silently reach RRS Case Id submission under the approved policy. Any live lookup or assignment requires separate authorization; record only value-free evidence, never referral contents or case identifiers.

- [~] **FCM-1.1-59 -- Complete the owner-authorized bounded Unity flagging live test.** Follow-up to FCM-1.1-58 using owner-approved synthetic UAT workbook input. Final scope is one actual missing-time flag attempt only, with appointment time cleared in memory; no provider changes, attachment upload, task completion, tracking or RRS Complete Assignment. Blocked before helper invocation: the task matches the selected row's claim number and claimant names, but both the populated task-summary customer and customer-section inputs fail the workbook customer check, including after the operator requested rechecking. No flag was submitted, and no workbook contents or identifiers were recorded in reports. Automated browser cleanup released services without Quit, leaving the windows for manual recovery. Acceptance: owner reconciles the workbook/customer identity, all four checks pass, the actual source helper is invoked once with safe stage/type diagnostics, and submission/closure and any separately authorized server readback are reported without claiming task completion.

## Process Wizard (parked -- recall with "JARVIS")

- [ ] **FCM-1.1-61 -- Design the Process Wizard from the parked investigation.** PARKED pending the owner's "JARVIS" trigger; review [[process-wizard/INVESTIGATION]] before deciding per-rule FIRST/MID/LAST checks or authority. Blocking inputs: (1) verified customer C02283 and employer E-code source, (2) live Facility dropdown labels, (3) whether the gate permits a blank SSN on applicable iCase referrals, (4) reliable iCase origin and previous-RGC evidence, and (5) whether the UAT CEM target is intentional. Acceptance: owner resolves the five inputs and approves a scoped rule/timing/verdict design before implementation; no code is authorized by this item.
- [ ] **FCM-1.1-62 -- Make the iCase blank-SSN completeness gate conditional (R9).** Uncovered by FCM-1.1-61's investigation; PARKED under JARVIS. `AI/referral_schema.py:496-505` requires SSN, so a correctly blank iCase SSN stops Final Code before CMS (`Final Code/finalcode/orchestrator.py:84-107`). Acceptance: once iCase provenance and new/existing claimant policy are approved, applicable blank SSNs pass the gate without weakening unrelated required fields; synthetic gate and orchestrator tests cover both paths.
- [ ] **FCM-1.1-63 -- Set and verify GAA checkbox state with complete scoped triggers (R37).** Uncovered by FCM-1.1-61's investigation; PARKED under JARVIS. `Processes/SubjectLineBuilder/Deploy-Ready/legacy_steps.py:1322-1325` calls `Toggle()` (which can untick a checked box) and only tests Texarkana city plus 'goodyear', omitting the other triggers and Cooper Tire. Acceptance: after verified customer/employer scope and live checkbox semantics are established, apply all approved triggers, set the desired state idempotently and confirm readback with synthetic prechecked/unchecked cases.
- [ ] **FCM-1.1-64 -- Exclude prohibited direct GAA FCM requests from Requested NCM (R29).** Uncovered by FCM-1.1-61's investigation; PARKED under JARVIS. Extraction treats a requested nurse as `NCM` (`AI/referral_schema.py:166-172`; `AI/source_evidence.py:66-70,126-137`), which the adapter sends to Requested NCM (`Final Code/finalcode/field_adapter.py:32-53,106-141`; `Processes/SubjectLineBuilder/Deploy-Ready/legacy_steps.py:1307-1321`) without the named-GAA-FCM exclusion. Acceptance: with verified customer scope and an owner-approved human permission/alternate workflow, a prohibited request is detected before that field is filled and cannot proceed as an approved assignment without recorded human resolution; synthetic negative and allowed cases pass.
- [ ] **FCM-1.1-65 -- Disambiguate Goodyear Co versus Company before employer selection (R34).** Uncovered by FCM-1.1-61's investigation; PARKED under JARVIS. CMS normalization equates `COMPANY` and `CO` (`src/fcm_intake/legacy/legacy_customerchecker.py:331-335`), while Unity searches only the first four characters and may click a sole wrong suggestion (`src/fcm_intake/legacy/legacy_unity.py:295-318`). Acceptance: verify E11483 and the exact authoritative record at CMS and Unity selection, reject ambiguous or wrong results, and cover sole-wrong/multiple-candidate synthetic cases.
- [ ] **FCM-1.1-66 -- Reconcile attended CEM portal and customer-approval workflow.** Uncovered by FCM-1.1-61's investigation; PARKED under JARVIS. The live checker invokes CEM (`src/fcm_intake/legacy/legacy_customerchecker.py:667-758`), but `src/fcm_intake/legacy/legacy_cem.py:14-20,52,162-163,274-281` launches Edge on import, targets UAT and calls employer search rather than customer search; Data Control approval is not tracked. Acceptance: owner confirms target environment, customer-exists-first sequencing and Data Control handoff; source and synthetic tests verify the approved flow and import safety, with live portal behavior reported separately.

## Next up

- [~] **FCM-1.1-87 -- Prepare and publish Unity v1.0.9 external-tracking release.** Owner requested rebuilding and publishing the FCM-1.1-85 fix and approved integrating latest main. Acceptance: upstream FCM-1.1-81 through 84 retained, source/config/packaging checks pass after integration, production frontend and Unity spec rebuilt, packaged self-test and archive/code/source correspondence verified, no `.env` or operator payload packaged, scoped source and exact tag pushed, and EXE/checksum digests verified before and after publication. No live database or Unity retry is authorized.

- [ ] **FCM-1.1-86 -- Verify RRS authentication and reconcile the already-submitted Unity item without replay.** Uncovered during FCM-1.1-85: supplying the configured connection and passing offline tests cannot establish successful live authentication, whether the prior task actually persisted, or whether a tracking row exists. Owner reports the failure after Unity submission and before approval. Do not retry Unity, bypass required tracking via Assign-only, or repeat an uncertain write automatically. Acceptance: owner approves the environment and a bounded database/connectivity/reconciliation scope, confirms portal/task and tracking status without putting identifiers into reports, and authorizes the specific remaining tracking/approval/RRS actions. Record actual outcomes separately from the source fix; no new credentials may enter Git or release assets.
- [~] **FCM-1.1-81 -- Save one referral JSON from Final Code and standalone Reader.** Shipped in Final Code v1.0.9 and AI PDF Reader v1.1.1; synthetic source and packaged self-tests passed, live confirmation pending. Shared `AI/referral_json.py` persists extraction, saved edits, completeness/approval and Final Code run-end metadata in one whitelisted, versioned record. **Owner amendment: always store full raw `source_text` for debugging at the first after-extraction write and preserve it on later overwrites; Final Code uses the full RRS viewer capture and Reader uses extracted document text after `join_pages`. If model input differs, also store exact `sent_text`. No opt-in. Earlier endings before extraction may lack text.** Frozen apps create `Referrals/` beside the EXE; source, Git worktree or unwritable locations fall back visibly to `%LOCALAPPDATA%/FCM_Structured/<FinalCode|AIPDFReader>/Referrals/`. Absolute `FCM_REFERRALS_DIR` overrides this, with Final Code's `FCM_FINAL_CODE_AUDIT_DIR` retained as an alias; every target must be outside Git. Files contain full referral PHI, including claimant names in filenames: **FCM-1.1-46 retention/access remains unresolved and applies to both locations and apps; expiry number of days will be added later under 46, with no expiry/automatic deletion implemented here**. Preserve original/current fields, providers, rename/collision protection and atomic saves; redact known secrets in all fields including source/sent text and exclude CMS payloads, credentials and raw model responses. Synthetic verification and exact evidence are recorded in the referral JSON SITREP; the full-text amendment is packaged in these builds. Live RRS/CMS/Bedrock/portal behavior remains unverified.
- [~] **FCM-1.1-82 -- Resolve section-reader overrides of correct AI fields.** Shipped in Final Code v1.0.9 and AI PDF Reader v1.1.1; S1-S10 synthetic orderings tested: valid AI values survive contradictory/blank reader evidence, and format-valid reader evidence fills blank AI fields; disagreements are non-blocking review flags. Live viewer order and packaged operator clicks remain unconfirmed. Authorized live confirmation remains open.
- [~] **FCM-1.1-83 -- Add field-specific format review flags.** Shipped in Final Code v1.0.9 and AI PDF Reader v1.1.1; synthetically tested for claimant/provider ZIP, DOB and injury date, SSN, phone and gender. Malformed values remain unchanged with non-blocking review flags; saving edits rechecks and clears resolved disagreements. Live viewer order and packaged operator clicks remain unconfirmed.

- [ ] **FCM-1.1-76 -- Confirm Customer Defined Fields group applicability before relaxing its locator.** Uncovered during FCM-1.1-75: the current group locator requires the literal Liberty Mutual Commercial Market name and `20 fields`. Read-only inspection of the affected task found exactly one matching visible 20-field header, so this inspection does not establish a locator mismatch and the production name/count must not be changed speculatively. A portal field-count change or another customer group would not match this locator. Acceptance: owner confirms supported customer groups and any applicable mapping, then an evidence-backed group locator handles approved groups without relying on display-count metadata; synthetic negative/ambiguous-group tests and any separately authorized live verification establish the new boundary without copying referral contents.

The owner-approved post-builder triage/export source fix is archived as FCM-1.1-39; its release-preparation runtime-source packaging correction is archived as FCM-1.1-40 with static, rebuilt EXE, packaged self-test and archive evidence. Live end-to-end completion remains unverified. Final Code stops before Unity assignment; ask instead of inferring further integration.

At the original local allocation, the highest ID was FCM-1.1-69; after the contributor published 70-74, the unpublished items moved to 75-77, then to 81-83 after the contributor published 75-80. FCM-1.1-84 records release preparation; FCM-1.1-81 remains in progress pending live evidence. The owner-approved post-builder triage/export source fix is archived as FCM-1.1-39; its release-preparation runtime-source packaging correction is archived as FCM-1.1-40 with static, rebuilt EXE, packaged self-test and archive evidence. Live end-to-end completion remains unverified. Final Code stops before Unity assignment; ask instead of inferring further integration.

FCM-1.1-81 acceptance correction: exact core `saves[].reason` values are
`after_extraction`, `save_changes`, `complete`, `run_end`. Final Code saves
`complete` only after operator approval and an actual `Passed` orchestrator
gate, at CMS entry before CMS input checks/callback; incomplete/cancelled/failed
gate paths retain their early-stop record without `complete`. Additional
address-check, confirmation and retry reasons remain distinct. Earlier evidence
below predates this correction and used the old extraction/edit labels.

The new shared per-referral JSON uses **`schema_version: 2`**, distinct from the
legacy Final Code audit schema 1. Only the shared writer's schema constant is
bumped; the metadata-only adapter may retain its internal legacy version 1.
Version-bump verification: **532 passed, 1 skipped, 56 subtests passed**;
SLB **70 tests, OK**. Both app outputs are explicitly tested as version 2.
Distinct source self-test output `selftest-schema2/Referrals/` was inspected for
`schema_version: 2` and exact saves `after_extraction`, `complete`, `run_end`.
Reports: `pytest-schema2.txt`, `slb-schema2.txt`,
`finalcode-selftest-schema2.json`, `selftest-schema2-inspection.txt`, `SITREP.md`
under the existing referral JSON scratch folder. This is historical source-stage evidence; no build or live run occurred at that stage.

FCM-1.1-81 source verification (10/24/2026): repository unit suite **518 passed,
1 skipped, 56 subtests passed**, versus the observed **484/1/56** baseline;
SLB standalone **70 tests, OK**; frontend scratch production build passed and
**21 browser tests passed**. Final Code source self-test completed all six stages
and saved one synthetic JSON with `extraction`, `complete`, `run_end` history.
Reports, synthetic record, hook/schema SITREP and raw Git status/diff are under
`C:/Users/Administrator/AppData/Local/hermes/profiles/omniroute/cache/scratch/referrals-json/`.
Both PyInstaller specs passed static path/import checks; no spec execution,
EXE build or live RRS/CMS/Bedrock/portal run was performed at that source stage; later builds are recorded in FCM-1.1-84.

Owner-approved full-text amendment verification: repository unit suite **527
passed, 1 skipped, 56 subtests passed** (prior source baseline 518/1/56); SLB
standalone **70 tests, OK**. Source Final Code self-test retained the complete
synthetic capture in one JSON through `extraction`, `complete`, `run_end`.
Synthetic tests cover uploaded two-page PDF text after `join_pages`, truncated
model input in `sent_text`, preservation across edits/renames, and credential
redaction in full text. Updated reports and SITREP are in the same scratch
folder. No build or frontend change was performed at this amendment stage.

Acceptance-fix verification: **530 passed, 1 skipped, 56 subtests passed**;
SLB **70 tests, OK**. Source self-test saves exactly `after_extraction`,
`complete`, `run_end`. Regressions exclude `complete` for incomplete approval,
cancellation, gate exceptions and fabricated custom stage events, and verify
that a passed gate saves `complete` before the CMS callback/input checks.
Reader's real model-prompt builder is exercised with a synthetic clipped
document: stored `sent_text` matches the prompt document input and the excluded
source tail stays out of that prompt while full `source_text` remains in JSON.
Evidence: `pytest-acceptance.txt`, `slb-acceptance.txt`,
`finalcode-selftest-acceptance.json`, `selftest-acceptance-inspection.txt` and
updated `SITREP.md` in the same scratch folder. This predates the release builds; no live run.
FCM-1.1-51 adds exact session-selected local PDF binding, packaged and
synthetically verified by FCM-1.1-52 for `unityassignment-v1.0.2`. FCM-1.1-53 extends
the standalone source to original PDF, MSG and EML documents without conversion.
FCM-1.1-54 supplements that dated source-only evidence with the rebuilt EXE and
packaged synthetic checks prepared for `unityassignment-v1.0.3`; actual
publication is recorded in GitHub releases. The earlier v1.0.2 artifact remains
PDF-only. Live portal acceptance of MSG/EML remains unverified. FCM-1.1-48 remains
open: the legacy export-folder fallback still re-globs, inner non-upload handlers
can swallow errors, and neither document identity nor portal/task readback is
verified by synthetic checks. Neither the source change nor packaging authorizes
live execution.

FCM-1.1-55 restores only the owner-approved legacy missing appointment-time
flag in shared Unity source. Provider/name details or an appointment date plus
blank time trigger the legacy reason selector and exact note; the existing
process continues only after a single submission and modal closure. Flag errors
fail the desktop checked controller before approval/RRS completion; default
attempt tracking is unchanged. Synthetic source tests and self-test passed,
but neither live flag UI/server persistence nor a rebuilt EXE was verified.
FCM-1.1-48 remains open; this change does not authorize live execution.

FCM-1.1-56 fixes only provider address Use-modal detection in shared Unity
source, accepting visible `modal fade show` and legacy `modal fade in` with
class-order-independent matching and confirming modal closure before True.
The owner-authorized bounded live UI check clicked Validate Address and Use
once each after the owner supplied test details; Use's immediate parent was
`modal fade show`, and it closed. This was not a live run of the source fix
and proved no save, task completion, assignment or server persistence.
Actual-source synthetic tests and source self-test passed; no EXE was rebuilt.
FCM-1.1-48 remains open and Unity remains standalone.

FCM-1.1-57 supplements the dated source-only evidence for FCM-1.1-55 and
FCM-1.1-56 with a rebuilt Unity v1.0.4 EXE and packaged synthetic self-test.
Both the missing-time flag and provider address Use-modal fix are included.
Actual publication is recorded in GitHub releases; packaging does not verify
live flag persistence, server-side address acceptance or task completion.

FCM-1.1-58 adds stage-specific, value-free Unity flag diagnostics and the owner's
explicit desktop recovery policy: leave Edge open on flagging failure for manual
recovery, releasing the detached driver service/connection without Quit. Normal
success and unrelated failures retain cleanup; provider work, approval and RRS
completion stop on a flag failure while default attempted tracking is unchanged.
At FCM-1.1-58, the reported root failure was still unconfirmed: bounded non-submitting inspection
resolved all three existing modal-relative selectors and verified reason/note
entry, but neither source replay nor a flag submission/server persistence.
Synthetic checks only; source-only, no build or release. Published v1.0.4 remains
unchanged. FCM-1.1-48 remains open and Unity remains standalone.

FCM-1.1-60 supplements FCM-1.1-58's dated source-only evidence with a rebuilt
Unity v1.0.5 EXE, recovery-module packaging checks and offline self-test.
Actual publication is recorded in GitHub releases. FCM-1.1-59 remains blocked
before flag submission by the live-test customer mismatch; neither packaging
nor release establishes the root flagging failure or server persistence.

FCM-1.1-68 fixes the subsequently confirmed note XPath mismatch after selecting
Missing information: the old numbered-div path resolves nothing while the stable
textarea ID remains visible/enabled in the same modal. The helper now uses the
modal-scoped ID with the existing actionable wait; reason/submit selectors,
trigger, exact note/readback, single submission, continuation and browser
preservation are unchanged. Focused synthetic regressions and source smoke
passed; no live helper execution, flag submission, server validation, build or
release occurred. FCM-1.1-58's earlier root-unconfirmed evidence is historical.
FCM-1.1-59 remains active and blocked by the customer mismatch.

FCM-1.1-69 supplements the note fix in FCM-1.1-68 with a rebuilt Unity v1.0.6
EXE and packaged synthetic verification. Actual publication is recorded in
GitHub releases. Read-only live inspection confirmed the selector mismatch,
but no corrected live flag submission or server persistence was verified.

## Completed

`FCM-1.1-73` is also archived after the owner confirmed first-result selection and the bounded live attempt verified that selection. `FCM-1.1-74` records the rebuilt v1.0.7 artifact, packaged checks and source correspondence; actual publication is recorded in GitHub releases. `FCM-1.1-72` remains active and blocked because the first task's customer does not match the approved workbook row; no task mutation or tracking occurred.

`FCM-1.1-75` is archived with source-only Customer Defined Fields entry, idempotent section opening and desktop failure recovery. Independent synthetic checks passed; read-only inspection confirmed the existing locators and populated values, not the original closure or live execution of the source fix. The published v1.0.7 EXE remains unchanged. `FCM-1.1-76` retains the separate customer-group/count applicability question.

`FCM-1.1-77` through `FCM-1.1-79` are archived after Employer Defined Fields inspection and the owner's approved source safeguards/header-capitalization correction. Independent combined Unity and packaging-boundary checks passed 93 tests; no live values were changed or source helper replayed. Other employer fields remain manual, and the published v1.0.7 EXE remains unchanged.

`FCM-1.1-80` supplements those source-only records with a rebuilt v1.0.8 EXE, packaged synthetic self-test and independently verified archive/source/frontend correspondence. Actual publication and assets for `unityassignment-v1.0.8` are recorded in GitHub releases; live integrations remain unverified.

`FCM-1.1-85` fixes external RRS tracking configuration and missing-config preflight in source; `FCM-1.1-86` retains live authentication and safe recovery of the already-submitted item as owner-dependent work. The owner approved correcting the unpublished local IDs 81/82 to 85/86 after concurrent upstream work reserved 81 through 84. `FCM-1.1-87` tracks the requested v1.0.9 build/release.

Finished items `FCM-1.1-01` through `FCM-1.1-18`, plus `FCM-1.1-27`, `FCM-1.1-28`, `FCM-1.1-30` through `FCM-1.1-40`, `FCM-1.1-43`, `FCM-1.1-47`, `FCM-1.1-49` through `FCM-1.1-58`, `FCM-1.1-60`, and `FCM-1.1-67` through `FCM-1.1-70`, are archived in `docs/completed.md`. FCM-1.1-59 remains active and blocked; FCM-1.1-61 through FCM-1.1-66 remain parked Process Wizard items. The owner approved correcting the unpublished note-fix ID from 61 to 68 after the concurrent upstream allocation; upstream IDs are preserved, and 69 records v1.0.6 packaging. FCM-1.1-70 connects the standalone completion adapter through the shared RRS sequence with selected-claim lookup, mandatory field readback and Case Id closure; its source-only synthetic checks do not update the released EXE. FCM-1.1-71 tracks partial-result lookup safety separately. Earlier source-only entries remain historical. These checks do not establish live or native-window end-to-end behavior. Move future finished items out of their active section and append there in ID history with both date markers and test/build evidence; do not renumber.
