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

## One browser per All run (FCM-1.1-95; v1.0.12)

Desktop and live CLI **All** now retain one Unity WebDriver/session through
assignment, tracking, iCaseManager approval, case lookup and RRS completion.
The live boundary owns that session and closes it after RRS finishes or the run
stops/fails; there is no reuse across operations or referrals. **Unity** and
**Assign** remain independent operations with their existing owned-browser
lifecycles. The controller remains browser/database independent.

Both approval and the explicit manual Yes/No continue/sign-in pause remain,
even for an already-authenticated session. Sign in manually if needed. Borrowed
lookup waits for Yes before any search navigation or readiness probing, then
uses the same browser/tab without rerunning assignment login. It clears the old
claim before entering the current claim. Existing case-detail tabs/row selection
are unchanged. A lost session stops completion; it never creates a replacement,
replays assignment or opens a second authentication session.

Direct legacy calls still create/close their own browser by default. Borrowed
legacy assignment/lookup never quit their caller's driver; the All owner closes
it once. Desktop's three existing typed flag/customer/employer manual-recovery
errors still leave detached Chrome open and release service/executor resources.
Task-completion errors use normal cleanup. Cleanup failures are reported without
silently discarding the primary failure.

FCM-1.1-96 includes this lifecycle in the rebuilt **v1.0.12** release,
published on **10/27/2026**. The packaged synthetic self-test passed,
including `single_all_session_cleanup: true`; see the
[release record](Stand-Alone/README.md#v1012-single-browser-all-release-10272026-fcm-11-96).
The published **v1.0.11** EXE and historical FCM-1.1-88/90/94 release evidence
remain unchanged. No live portal, RRS, CMS, database or Bedrock validation
occurred during this build.

Historical FCM-1.1-95 source evidence (**10/27/2026, before the FCM-1.1-96
rebuild**): independent offline verification passed 156 primary JUnit cases with no
failures/errors/skips. Actual desktop/CLI boundaries were exercised with
synthetic external I/O: one factory call, identical borrowed driver, no early
quit/relogin/replacement, and cleanup after RRS or ordinary stop/failure.
Source smoke passed the one-session cleanup check, 39-key contract, main and
PDF/MSG/EML flows, and instruction limits. Non-target legacy functions and
unrelated owner files were unchanged.

## Unity browser (FCM-1.1-90, v1.0.11)

Initial assignment and post-approval Unity case lookup now use Chrome through
the shared `AI/unity_browser.py` factory. Install Chrome on the operator machine.
With a blank `browser.chrome_driver_path`, Selenium Manager discovers Chrome
and resolves its version-matched ChromeDriver at runtime; initial resolution
may require network access. To use a managed static driver, set
`FCM_CHROME_DRIVER_PATH`, then `CHROME_DRIVER_PATH`, or
`config\local_settings.ini` / `[browser] chrome_driver_path` in that precedence
order. Blank values defer to the next source; the default is blank. Explicit
paths must be valid and compatible: Chrome errors never fall back to Edge.
No developer driver, credentials or browser binary is bundled.

The desktop UI remains pywebview `edgechromium` / WebView2. Unrelated CMS
registration, IE-mode and other Edge automation are unchanged. Assignment keeps
opt-in detach and existing typed-error manual recovery (now in Chrome);
CLI/non-recovery cleanup and owned lookup's Quit remain; FCM-1.1-95 above
governs All ownership in source and the published v1.0.12 artifact.
The manual post-approval sign-in pause, modes, gates, selectors, tracking and
60-second page/script timeouts are preserved. Lookup's existing driver log is
now `chromedriver.log`; assignment adds no persistent driver log.

Dated Edge inspection/mock/release evidence below describes earlier versions,
not the current browser policy. FCM-1.1-94 includes this change in the rebuilt
v1.0.11 release. The earlier v1.0.10 release remains
unchanged. Packaging does not establish live portal, RRS, CMS, database or
Bedrock behavior.

## Complete Task targeting (FCM-1.1-91, v1.0.11)

After the unchanged attended manual-validation notice, the actual legacy flow
uses `AI.unity_completion.complete_task`, not a role-dependent button index.
Only native buttons whose visible, whitespace-normalized text is exactly
`Complete Task` ignoring letter case (FCM-1.1-93) qualify. Hidden matches are
ignored; multiple visible matches fail even when one is disabled. The helper
waits read-only for up to 15 seconds for a unique enabled, non-`aria-disabled`
target, scrolls, then
rechecks the same target and its eligibility before one normal click. There is
no positional/substring fallback, JavaScript click, or click retry.

Missing, ambiguous, changed or non-actionable targets and interaction failures
raise value-free `UnityTaskCompletionError`, chained to the original cause.
It propagates through legacy validation and CLI entrypoint. Desktop/controller
report `run_unity_failed`, stop before approval/RRS and preserve the existing
attempted-assignment tracking policy. Completion errors use normal browser quit;
they do not join the existing typed manual-recovery/browser-preservation list.

A returned click is not server completion confirmation. The existing post-click
sleep/sequence is unchanged. FCM-1.1-48's broader upload/task-outcome readback
limitation remains; this does not resolve other legacy swallowed errors.
FCM-1.1-94 includes this helper and FCM-1.1-93's comparison correction in the
rebuilt and published v1.0.11 artifact. The earlier v1.0.10 EXE
is unchanged. Portal/server, RRS, CMS, database and Bedrock outcomes were not
exercised or verified.

Historical FCM-1.1-91 verification used case-sensitive matching; FCM-1.1-93
adds case normalization to existing whitespace normalization, preserving exact
action identity and the other safeguards above. FCM-1.1-92's read-only accessibility inspection exposed
`Complete task` and `Delete task`; DOM-rendered text was not read, so that
inspection did not establish a DOM selector failure. The owner approved the
case-insensitive source policy; that source-only work performed no live click,
build or release. FCM-1.1-94 separately authorizes the v1.0.11 rebuild/release.

Historical FCM-1.1-91 verification passed 148 focused JUnit test cases and source smoke.
Twelve local synthetic Chrome DOM cases covered agent/supervisor/reordered
layouts, exact/nested/whitespace labels, hidden/duplicate/disabled controls and
post-scroll relabeling. Delete Task received zero clicks in every case.

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

### Manual lookup sign-in (FCM-1.1-88)

After iCaseManager approval and the existing initial RRS steps, the new lookup
browser opens Unity UAT and pauses indefinitely for manual sign-in. The desktop
uses its existing Yes/No prompt; live CLI uses its existing input confirmation.
Direct legacy callers default to an attended native Tk Yes/No dialog, never a
print-only notification. Sign in in that browser, then explicitly select Yes.
The prompt is required even if already signed in. No credentials are collected
or automated, and no authentication chooser, search, reload or navigation runs
while the answer is pending.

Only after Yes does the lookup check the existing claim input for visibility,
enabled state and absence of readonly. If necessary it navigates to the existing
case-search URL, then waits up to 15 seconds for that actionable input before
searching. No, a prompt error or readiness failure prevents search, Case Id entry
and final RRS confirmations; errors retain the original cause behind value-free
RRS stage text. The lookup browser still quits on success, cancellation or failure.
This adds no timeout-based consent, automatic login detection, retries or fixed
login delay. Unity-only and injected/offline flows gain no real sign-in prompt;
the first assignment browser, tracking policy, modes and business results are
unchanged. Synthetic source tests do not establish live portal/RRS/CMS/Bedrock
or database behavior. The initial FCM-1.1-88 source change did not rebuild an EXE.
FCM-1.1-89 packages it for v1.0.10 with a passing packaged synthetic self-test,
archive/source correspondence and isolated frozen confirmation checks; actual
publication and the source tag are recorded in GitHub releases. No live workflow
or previously submitted task was replayed.

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
and, under the owner's explicit recovery policy, leaves detached Chrome open for
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
fields, Complete Task, approval or RRS, leaves detached Chrome open for manual
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
approval and RRS, leaves detached Chrome open, and releases the driver service and
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

FCM-1.1-87 prepares Unity `unityassignment-v1.0.9` after integrating latest main,
including FCM-1.1-85's external RRS tracking configuration and preflight.
Artifact size is 48,484,396 bytes; SHA-256:
`017b06ded1bbd1e0dbe47188713318546e33f815396d1be4c1256c304cb0576f`.
The packaged self-test, four isolated frozen-resolver cases and 124 post-merge
source/config/packaging cases passed. Independent checks matched six raw sources,
ten compiled modules and three frontend files; `.env`, protected credential blobs
and operator/sample/session payloads were absent. Actual publication is recorded
in GitHub releases. Configure external `.env` or `AI\.env` beside the EXE (or the
process environment) and restart; the repository's `AI\.env` is not bundled or
searched through parent folders. No live authentication, database write or
already-submitted-task replay was performed. FCM-1.1-86 remains open.

`completed` means injected callables returned normally, not that live records
were verified. In particular, `legacy_unity.main` catches unrelated exceptions and
returns None on success and those failures; its upload handler also swallows
failures. Complete Task's `UnityTaskCompletionError` now propagates instead, as
described above. Other hidden legacy failures can still result in reported completion after a portal
failure. The controller cannot recover an error the dependency did not raise.
Use a future outcome-reporting adapter and independent live verification before
relying on results for unattended operation. See [integration](Deploy-Ready/README.md)
and [offline commands](Stand-Alone/README.md).
