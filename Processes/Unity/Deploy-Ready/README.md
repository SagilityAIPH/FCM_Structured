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
  Legacy portal exceptions and some RRS dialog failures are swallowed. No-return
  is not an independently verified success. Reliable production integration
  requires outcome-reporting wrappers/read-back; offline tests do not certify it.

Literal `"19"` is preserved by the unchanged legacy RRS callback. Its business
meaning is undocumented in the inspected code; obtain RRS owner confirmation.
No portal body was copied, no credentials are bundled, and no EXE is produced.
