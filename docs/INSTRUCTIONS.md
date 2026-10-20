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

`Final Code/finalcode/orchestrator.py:34` defines `run(*, capture, extract, review, cms, subject_line, on_stage=None, today=None, adapt=None)`. Implemented order: `capture()` → `extract()` → `review()` → `completeness()` gate → `cms()` → one-way field adapter → `subject_line()`. CMS must resolve a nonblank customer before the Subject Line Builder stage. Its live factory now completes triage, answers the legacy prompts and exports the attachment through the existing shared RRS adapter only after a completed builder result; the same stage returns completion only after export returns. The chain does not persist run data.

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

## Next up

Deliberately empty. The owner-approved post-builder triage/export source fix is archived as FCM-1.1-39; its release-preparation runtime-source packaging correction is archived as FCM-1.1-40 with static, rebuilt EXE, packaged self-test and archive evidence. Live end-to-end completion remains unverified. Final Code stops before Unity assignment; ask instead of inferring further integration.

## Completed

Finished items `FCM-1.1-01` through `FCM-1.1-18`, plus `FCM-1.1-27`, `FCM-1.1-28`, and `FCM-1.1-30` through `FCM-1.1-40`, are archived in `docs/completed.md`. Move future finished items out of their active section and append there in ID history with both date markers and test/build evidence; do not renumber.
