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
  Legacy portal exceptions can still be swallowed. CompleteAssignment now delegates
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
