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
frmInputBox, sets tbInput to literal `"19"`, clicks btnOk, answers Yes to an
optional `Unity Complete ?`, looks up the supplied current claim in Unity,
fills the required RRS `Case Id` and clicks OK, then answers the optional second
`Unity Complete ?` and final `ReferralRoutingSystem` OK. The existing
`CMS.CheckCaseUnity` lookup targets Unity UAT and selects the case with the
latest valid assigned date; it is not CMS registration or CheckAdvNotice.
Inspection of this call site and searches of src/ and
Processes/ found no business definition for `19`; do not label it a user, queue,
status or team code without RRS owner confirmation.

The sequence now has one implementation in `AI/rrs_assignment.py`; legacy
`CompleteAssignment` is a thin delegate shared by the standalone CLI and desktop.
Lookup uses the selected claim argument, never legacy global referral data, and
loads `legacy.CMS` lazily through the runtime package. A missing/blank case ID
fails before Case Id entry or submission. Required interactions and present
optional-dialog failures report `complete_assignment_failed` with value-free
stage text and the original exception cause retained. Only absence timeouts
skip optional dialogs; clicks are not retried. Both required input writes have
exact readback before OK, and Case Id must close after its single OK click.
The lookup browser is closed on
success and failure. Modes and the attended iCaseManager gate are unchanged.
Synthetic tests exercise this continuation and runtime resource prerequisites;
no live RRS/Unity/CMS/Bedrock/database workflow or EXE build was performed for
the FCM-1.1-70 source change. FCM-1.1-74 subsequently packages that source for
v1.0.7, with packaged synthetic and archive/source correspondence checks. The
bounded UAT attempt selected the first result but stopped before Assign on
customer mismatch; its identity gate is session-only, not a shipped safeguard.
Live upload, task completion, tracking and RRS completion remain unverified.
Unity remains standalone, outside Final Code.

## External tracking connection (FCM-1.1-85)

Live All / Unity runs now require the existing `FCM_RRS_DB_CONNECTION`.
The shared legacy insert resolves this value through `fcm_intake.config`,
passes it unchanged to the driver and retains the same INSERT, parameters,
commit and attempted-assignment policy. There is no legacy connection fallback,
new credential form or credential store. Keep credentials outside Git, workbook,
bridge payloads and logs.

Use the real environment or an external `.env` / `AI\.env`: under the repository
root for source execution, or beside the EXE for frozen execution (`SETTINGS_ROOT`
is the EXE directory, not `_MEIPASS`). A packaged app does not discover the source
repository's `AI\.env`; no `.env` is bundled or copied automatically. Existing
environment variables take precedence; dotenv files load without overriding them.
Restart the app after editing an external `.env`; the existing loader runs once
when configuration is imported.

Desktop and CLI check presence/nonblank configuration before starting live
All / Unity work. This is not a database connection/login test or authentication
proof. Assign-only, injected callbacks and offline scenarios do not require it.
Database driver failures report value-free text, retain the original cause
internally and stop before approval/RRS after a tracking failure; there are no
automatic retries or Unity replays. Verify any previous portal submission and
tracking outcome before manually running again, especially after uncertain writes.
This change is source-only: the published v1.0.8 EXE is unchanged. No live portal,
database, RRS, CMS or Bedrock workflow was exercised and no EXE was rebuilt.

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

Customer Defined Fields now uses one shared legacy UI helper for Date of First
Appointment (`nextApptDate`) and Claim Identifier (`claimID`). Populated values
are preserved; whitespace-only values are blank. Supplied nonblank values are
written only to blanks and must match exact UI readback before continuing.
Readback polls within the existing bounded wait to allow asynchronous updates;
it does not repeat writes or clicks.
Missing/blank source values add no new input requirement or fallback. The
existing manual-validation gate is unchanged.
Failures raise stage-specific `UnityCustomerFieldsError` with the original cause
retained and value-free operator text. Desktop automation stops before employer
fields, Complete Task, approval or RRS, leaves detached Edge open for manual
recovery under the owner's selected policy, and releases its service/connection;
cleanup failures are recorded without replacing the original error.

Owner-authorized read-only UAT inspection found one visible Liberty Mutual
Commercial Market / `20 fields` header matching the existing selector. Both
existing field locators resolved populated, initially hidden inputs; one header
expansion made both visible, enabled and not readonly. No field values were
changed or submitted. The helper now checks both fields before opening: already
visible fields require no toggle; both hidden fields permit one click followed
by a visibility wait. Ambiguous, inconsistent or unreadable state fails safely,
without multi-click fallback.

The full Unity suite passes with actual-source synthetic coverage; neither this
nor the inspection confirms the original live failure trigger or a live source
fix. The existing three-second wait, header selector, appointment XPath and Claim
Identifier ID remain unchanged. The exact field-count constraint is brittle
despite matching the inspected task; no other customer-group behavior is
inferred. No live source replay, RRS/CMS/Bedrock calls, submission, EXE build or
release was performed.

FCM-1.1-78 adds source-only Employer Defined Fields safeguards in one shared
legacy UI helper. The existing Goodyear applicability, employer name /
`4 fields` header requirement, Facility locator and 25 recognized facilities are retained.
An already-visible Facility does not toggle the header; a hidden Facility permits
one header click and a bounded visibility wait. Populated selections are preserved,
even when provider city differs. Blank selections are filled only from one
recognized special-instructions token matching one enabled, non-placeholder
option, or from one nonblank provider-city match when no token is recognized.
Multiple recognized tokens, ambiguous options and missing matches leave the
selection unchanged for the existing notice and attended manual-validation gate.
A recognized token that has no option never falls back to provider city.
Selection is written once and requires exact selected text/value readback within
a bounded read-only wait. Other employer fields remain manual; no yes/no rules
or new employer mappings are added.

Employer interaction/readback failures raise value-free `UnityEmployerFieldsError`
with the original cause retained. Desktop recovery stops subsequent portal work,
approval and RRS, leaves detached Edge open, and releases the driver service and
connection without Quit. Cleanup failures are reported without replacing the
employer error. Attempted-assignment tracking, flag/customer recovery, success
and unrelated-failure cleanup, and CLI cleanup remain unchanged. Actual-source
synthetic tests cover these safeguards; no live source replay, RRS, CMS, Bedrock,
submission, build or release was performed for this change.

FCM-1.1-79 narrowly normalizes capitalization of that same employer name in the
header XPath, retaining whitespace normalization and the `4 fields` constraint.
The count has whitespace-token boundaries, so `14 fields` and `24 fields` do not match.
Exactly one visible matching header must be actionable; multiple visible matches
or unreadable states fail safely. Owner-authorized read-only UAT inspection found
one visible matching header after case normalization, while the old case-sensitive
name predicate returned none. The Facility select was visible/enabled with 37
options and a selected blank-text, empty-value placeholder, not a populated Facility.
No field values were changed or selected, and no source replay was performed.
Synthetic DOM tests evaluate the actual XPath against mixed-case headers,
wrong employers/counts and duplicate/hidden groups. No new employer applicability,
field-count relaxation, live writes, submission, build or release is implied.

FCM-1.1-80 supplements the dated source-only FCM-1.1-75/78/79 evidence with a
rebuilt production frontend and Unity v1.0.8 EXE. The packaged synthetic self-test
passed, and independent archive checks matched the raw legacy/helper sources,
compiled error/recovery modules and all three frontend files to this worktree.
The prepared artifact is 48,483,856 bytes with SHA-256
`910adb3d318e8254f2d63b9b3216264b8057cba937e8f3c36e84525f49c1d89a`.
Source/packaging-boundary checks passed 93 tests, with zero failures/errors/skips.
Actual publication for `unityassignment-v1.0.8` is recorded in GitHub releases;
neither packaging nor prior read-only inspection proves live source-helper,
portal, RRS, CMS, Bedrock or database completion.

`completed` means injected callables returned normally, not that live records
were verified. In particular, `legacy_unity.main` catches exceptions and returns
None on success and failure; its upload handler also swallows failures. The live
runner preserves that behavior and can report completion after a hidden portal
failure. The controller cannot recover an error the dependency did not raise.
Use a future outcome-reporting adapter and independent live verification before
relying on results for unattended operation. See [integration](Deploy-Ready/README.md)
and [offline commands](Stand-Alone/README.md).
