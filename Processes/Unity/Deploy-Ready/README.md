# Integration

`unity_flow.py` owns sequencing and imports no browser, database, desktop or
third-party library. Deploy-Ready is integration source, not a packaged EXE.
There is no new src/ adapter and the main intake app is not changed by this folder.
Load this file by importlib (the directory name contains a hyphen), then inject:

```python
result = controller.run_flow(
    data,
    list_attachments=list_current_exports,       # () -> iterable of files
    run_unity=portal_stage,                     # (customer, claimant_full, data)
    record_assignment=write_tracking,           # (claimant_full, claim_number)
    notify=show_notice,                         # (title, message)
    confirm=ask_approval,                       # (title, message) -> bool
    complete_assignment=finish_rrs,             # (claim_number)
    stage="all",                               # all | unity | assign
    record_attempt_on_failure=True,
)
if result["status"] != "completed":
    return result  # Never advance on a business stop or technical failure.
```

All/unity require customer, claimantFirst, claimantLast and claimNumber. Assign
requires only claimNumber. Missing or whitespace-only values raise ValueError
naming the keys. The caller owns complete legacy input data; these minimum keys
are not a complete validation schema for every portal branch.

Results always contain status, reason, claimantFull, attachment, steps and error.
Steps are ordered **attempted** stages, including the failing step, not just
successful stages. Success is `completed` with an empty reason and error.
Business stops are `stopped` with attachment_missing, attachment_ambiguous or
icasemanager_declined. Technical results are `failed` with one of:

- resolve_attachment_failed
- run_unity_failed
- record_assignment_failed
- await_icasemanager_approval_failed
- complete_assignment_failed

Error contains stage, type and message; SystemExit also supplies exit_code.
Exception and SystemExit are contained for the five wrapped stage callables.
The notification callback is deliberately outside those wrappers: caller-owned
UI notification errors propagate. KeyboardInterrupt is not swallowed.

## Safety and deployment requirements

- **One session per All run (FCM-1.1-95; v1.0.12).** Desktop and live CLI
  boundaries retain one driver through assignment, tracking, iCaseManager
  approval, lookup and RRS completion, then close it once (also on stop/failure).
  There is no cross-operation/referral persistence. Unity-only and Assign-only
  remain independent; offline/custom callbacks create no browser. The controller
  has no browser/database lifecycle logic.
  Approval and explicit manual Yes/No continue/sign-in remain mandatory, even
  when already authenticated. Borrowed lookup waits for Yes before navigation
  or readiness probes, uses the same browser/tab, and does not rerun login.
  It clears the old claim before typing the exact current claim. Lost sessions
  stop without replacement, fallback or assignment replay. Detail-tab selection
  and existing partial-row handling are unchanged.
  Direct legacy calls retain owned create/cleanup defaults; optional borrowed
  drivers are never quit by assignment/lookup. Desktop's existing three typed
  flag/customer/employer recovery failures still release service/executor and
  retain detached Chrome; task-completion failures quit normally. Cleanup errors
  remain visible without silently hiding the primary process failure.
  FCM-1.1-96 includes this lifecycle in the rebuilt v1.0.12 release, published
  **10/27/2026**. Its packaged synthetic self-test passed,
  including `single_all_session_cleanup: true`; see the
  [release record](../Stand-Alone/README.md#v1012-single-browser-all-release-10272026-fcm-11-96).
  Historical FCM-1.1-95 source verification on 10/27/2026 preceded this rebuild
  and did not itself build an EXE. Published v1.0.11 and historical
  FCM-1.1-88/90/94 release evidence remain unchanged. No live
  portal/RRS/CMS/database/Bedrock validation occurred during this build.
- **Unity uses Chrome (FCM-1.1-90, v1.0.11).** Initial assignment and
  post-approval lookup share `AI/unity_browser.py`. Install Chrome; the blank
  `browser.chrome_driver_path` default enables Selenium Manager's runtime
  version-matched driver discovery (initial resolution may need network access).
  Static overrides resolve from `FCM_CHROME_DRIVER_PATH`, then
  `CHROME_DRIVER_PATH`, then `config\local_settings.ini`, then blank.
  Blank values defer to the next source; explicit invalid paths fail without
  fallback. Do not bundle developer drivers or credentials. The desktop UI stays
  pywebview `edgechromium` / WebView2; unrelated CMS registration, IE-mode and
  other Edge automation are unchanged. Typed-error manual recovery now leaves
  detached Chrome open; CLI/non-recovery and owned lookup cleanup remain.
  FCM-1.1-95 above governs All ownership in source and the published v1.0.12 artifact.
  Manual lookup sign-in, gates, modes, selectors, tracking and 60-second
  page/script timeouts are preserved. Lookup retains its driver log as
  `chromedriver.log`; assignment adds no persistent driver log.
  Dated Edge observations refer to earlier versions. FCM-1.1-94 includes this
  change in the rebuilt and published v1.0.11 artifact.
  Published v1.0.10 is unchanged; packaging does not imply live
  portal/RRS/CMS/database/Bedrock verification.
- **Use the same stable, exclusive attachment folder as legacy.** Zero/multiple
  files stop before the legacy first-glob-result uploader can choose a stale
  document. The reported attachment path does not bind legacy's subsequent glob;
  this is not a lock or document-content check. Exclude concurrent exports and
  unrelated directory entries and verify the one export belongs to this claim.
- **Tracking happens even after raised Unity failures by default**, preserving
  OpenUnity's finally behavior. Explicitly opt out with
  `record_attempt_on_failure=False`. It still records normal returns. If both
  Unity and tracking raise, the Unity error is retained; the secondary tracking
  error is not separately exposed by this result schema.
- **The iCaseManager gate waits on a system absent from this repository.** The
  integration owns an attended boolean confirmation; there is no automated
  approval lookup. Assign-only bypasses portal and attachment checks intentionally.
- Ship the repository src/, config/ and Processes/Unity layout together. Live
  execution requires Windows, the configured browser/driver and Selenium stack,
  pywinauto with an interactive RRS desktop, pyodbc/appropriate ODBC drivers,
  database connectivity and authorized portal/database credentials. Review
  machine-specific paths and ATTACHMENT_FOLDER through existing configuration.
- legacy_unity.py currently targets a UAT Azure Web Apps host via UNITY_URL.
  Confirm the intended environment before any live run; do not assume production.
- The runner delegates to legacy_unity.main, InsertIntoTable and CompleteAssignment.
  Unrelated legacy portal exceptions can still be swallowed. FCM-1.1-91's shared
  Complete Task helper instead raises `UnityTaskCompletionError` through both
  legacy boundaries: controller failure is `run_unity_failed`, approval/RRS stop,
  attempted-assignment tracking and normal browser quit remain unchanged.
  FCM-1.1-93 changes the original FCM-1.1-91 case-sensitive policy to exact
  whitespace-normalized, case-insensitive `Complete Task` matching; Delete Task
  and prefix/suffix/plural labels never qualify. The helper selects only a
  matching visible native button, requires
  uniqueness/actionability and revalidates after scroll before one normal click.
  It does not confirm server completion or solve FCM-1.1-48's broader readback
  limitation. FCM-1.1-94 includes the helper and comparison correction in the
  rebuilt and published v1.0.11 artifact; the earlier v1.0.10 EXE is
  unchanged and live outcomes remain unverified.
  See [targeting contract](../README.md#complete-task-targeting-fcm-11-91-v1011).
  CompleteAssignment now delegates
  to the shared `AI/rrs_assignment.py` sequence: Assign -> literal `19` -> input OK
  -> optional Unity Yes -> current-claim Unity case lookup -> required RRS Case Id
  and OK -> optional Unity Yes -> optional RRS OK. `legacy.CMS.CheckCaseUnity`
  retains the latest-valid-assigned-date selection in Unity UAT, not CMS
  registration; CheckAdvNotice remains disabled. Missing/blank lookup results,
  required write/click failures and present optional-dialog interaction failures
  propagate as value-free, stage-specific `RRSCompletionError` with the original
  cause. Only optional dialog absence timeouts are ignored; no click is retried.
  Required input writes are read back exactly before OK, and the Case Id prompt
  must close after its single OK click.
  The lookup browser is cleaned up even on failure. No-return
  is not an independently verified success. Reliable production integration
  requires outcome-reporting wrappers/read-back; offline tests do not certify it.

Literal `"19"` is preserved by the shared RRS callback. Its business
meaning is undocumented in the inspected code; obtain RRS owner confirmation.
The standalone CLI and desktop share the legacy delegate; All/Unity/Assign
boundaries and attended approval are unchanged. Ship the shared AI module and
legacy CMS runtime file as declared in the Unity spec; frozen smoke checks cover
their presence/import prerequisites without opening live systems. This source
change at FCM-1.1-70 was tested synthetically only, not against RRS, Unity, CMS,
Bedrock or the database. FCM-1.1-74 subsequently packages it for v1.0.7 with
synthetic packaged and source-correspondence checks. The later bounded UAT
attempt selected the first result but stopped before Assign on customer
mismatch; no upload, task completion, tracking or RRS completion was verified.
That identity gate is session-only, not a new production safeguard. No
credentials are bundled.
