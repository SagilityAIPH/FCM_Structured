# Unity assignment and RRS completion

This process wraps the post-triage Unity stage, tracking write, human approval
and RRS completion. It does not repeat Subject Line Builder or export triage.
The shared controller is exercised by an offline runner; the existing intake
application has not been rewired to call this controller.

```text
Unity/
  Deploy-Ready/
    unity_flow.py       Shared controller; injectable portal, tracking and UI calls
    README.md           Integration and deployment requirements
  Stand-Alone/
    run.py              Offline scenarios or explicit live execution
    test_flow.py        Standard-library contract and scenario tests
    scenarios/          Synthetic examples, no real claim information
    README.md           Commands and debugging instructions
```

Deploy-Ready is integration source, not an independently packaged EXE. No Unity
EXE is built. The large Selenium body remains in
`src/fcm_intake/legacy/legacy_unity.py`; it is not copied or rewritten here.

## Three operational traps

1. **Attachment identity is a safety gate.** Legacy takes the first result of
   `glob.glob(ATTACHMENT_FOLDER + "/*")`, not the newest export. A stale referral
   can therefore upload the wrong document, and the upload handler swallows
   failures. The controller stops on zero or multiple candidates before calling
   Unity. Clear the folder and re-export the current referral. Exactly one file
   is necessary, not proof that its contents belong to this claim. The selected
   path is reported, not passed to the legacy uploader: keep the same configured
   folder stable and exclusive throughout the run. Concurrent exports, directories
   seen by legacy glob, or a single stale file are not solved by this count guard.
2. **Tracking is an attempted-assignment record, not proof of success.** Legacy
   `OpenUnity` writes from `finally`. By default this controller also attempts
   tracking after Unity raises. Set `record_attempt_on_failure=False` to omit that
   write on a raised Unity failure. A Unity error wins if tracking also fails;
   a tracking error after Unity returns is `record_assignment_failed` and stops.
3. **iCaseManager approval is external.** No iCaseManager client or approval
   verification is implemented here. `confirm` waits for an operator's attestation
   that approval happened in that separate system. No/false stops before RRS;
   Yes/true permits completion. Never auto-approve just to unblock automation.

## Preserved sequence and rules

`all`: resolve attachment -> run Unity -> record assignment -> await
 iCaseManager approval -> complete assignment. `unity` runs the first three
steps only; `assign` runs only the last two and relies on previously completed
Unity work. Required values are customer, claimantFirst, claimantLast and
claimNumber for all/unity; assign requires claimNumber only. Blank keys raise
ValueError before side effects. claimantFull joins trimmed first and last names.

RRS completion locates Referral Routing System, clicks btnAssign, waits for
frmInputBox, sets tbInput to literal `"19"`, clicks btnOk and answers Yes to
`Unity Complete ?`. Inspection of this call site and searches of src/ and
Processes/ found no business definition for `19`; do not label it a user, queue,
status or team code without RRS owner confirmation. The legacy function also
contains trailing CMS helper definitions; it was not extracted or changed.

## Limits of reported success

`completed` means injected callables returned normally, not that live records
were verified. In particular, `legacy_unity.main` catches exceptions and returns
None on success and failure; its upload handler also swallows failures. The live
runner preserves that behavior and can report completion after a hidden portal
failure. The controller cannot recover an error the dependency did not raise.
Use a future outcome-reporting adapter and independent live verification before
relying on results for unattended operation. See [integration](Deploy-Ready/README.md)
and [offline commands](Stand-Alone/README.md).
