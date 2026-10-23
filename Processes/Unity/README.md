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

Provider address confirmation keeps the existing details and Validate Address
workflow. Its shared legacy helper waits for an actionable Validate Address
button, then exactly one visible/enabled Use control inside a visible
`modal fade show` or legacy `modal fade in` container (class order is irrelevant).
Hidden controls and ambiguous matches are not clicked. It clicks Use once and
waits for that modal to close before returning True; click/wait failures retain
the existing False result and surrounding caller behavior.

During the owner-authorized bounded live check for FCM-1.1-56, Add new Provider
opened blank fields; the owner manually supplied test details. One Validate
Address click exposed exactly one enabled Use button whose immediate parent
Window had class `modal fade show`. One Use click closed that modal. This
establishes the observed UI structure and bounded interaction, not execution
of the source fix against the portal or server persistence. No Complete Task,
save or assignment was performed. Actual-source isolated synthetic tests cover
both modal class versions, hidden/disabled and ambiguous controls, click/wait
failures and confirmed closure. No EXE was rebuilt.

The owner-approved missing appointment-time flag is restored in the shared
legacy path only when provider/name details or an appointment date exist and
time is blank. It keeps the legacy reason selector and exact note
`Missing Provider Appointment Time`, verifies the textarea value and submits
once. After the modal closes, the existing Unity process continues. Flag-only
failures now raise stage-specific `UnityFlagError` through the legacy boundary,
retaining their original exception chain/type without exposing Selenium messages
or page/referral content in operator text. The desktop reports `run_unity_failed`
and, under the owner's explicit recovery policy, leaves detached Edge open for
manual recovery while releasing its driver service/connection. It does not
continue provider work, approval or RRS completion; default attempted-assignment
tracking is unchanged. Normal success and unrelated errors retain browser cleanup;
other driver callers default to no detach. No new input or broader flag
policy is added. See [standalone policy](Stand-Alone/README.md#owner-approved-missing-appointment-time-flag).
At FCM-1.1-58, the root of the reported flag failure remained unconfirmed. Bounded,
owner-authorized non-submitting inspection resolved all three existing relative
selectors, observed reason Missing information and verified exact note readback
with an enabled submit button; it did not submit a flag, Complete Task or
assignment. A zero-sized Angular host alone does not prove Selenium invisibility
or a selector defect. No source replay or server persistence was verified.
FCM-1.1-58 is source-only, with no EXE rebuild/release.

FCM-1.1-68 fixes the subsequently confirmed note-locator root cause. In a later
owner-authorized, non-submitting inspection, selecting Missing information made
the old numbered-div note XPath resolve nothing, while the textarea with ID
`intake-flag-for-intervention-description-text-area` remained visible/enabled
inside the same flag modal. The v1.0.5 error identified the same note-lookup stage.
The helper now waits for that stable ID within the modal; reason selection,
exact note/readback, one submission, closure, continuation and failure/browser
recovery behavior are unchanged. Focused synthetic regressions and source smoke
passed; no live source execution, flag submission, server readback or EXE
build/release was performed. FCM-1.1-59 remains blocked by the customer mismatch.

`completed` means injected callables returned normally, not that live records
were verified. In particular, `legacy_unity.main` catches exceptions and returns
None on success and failure; its upload handler also swallows failures. The live
runner preserves that behavior and can report completion after a hidden portal
failure. The controller cannot recover an error the dependency did not raise.
Use a future outcome-reporting adapter and independent live verification before
relying on results for unattended operation. See [integration](Deploy-Ready/README.md)
and [offline commands](Stand-Alone/README.md).
