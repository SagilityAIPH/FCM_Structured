# Unity desktop

Unity is a Python pywebview / WebView2 desktop app with a React TypeScript, Vite,
Tailwind and house shadcn frontend. It runs the existing shared Unity assignment
controller in `Deploy-Ready/unity_flow.py`. Form data stays in
memory; the app does not save referral edits or live output logs.

From the repository root, using the existing virtual environment:

```powershell
npm --prefix Processes/Unity/Stand-Alone/frontend ci
npm --prefix Processes/Unity/Stand-Alone/frontend run build
.venv-bedrock/Scripts/python.exe Processes/Unity/Stand-Alone/run.py --desktop
```

`launcher.py` also opens the desktop directly. Windows, WebView2, pywebview,
openpyxl and the configured legacy automation dependencies are required. `run.py` with no
arguments retains the existing offline happy-path scenario; desktop is explicit.

## Workbook and manual workflows

1. Use `Unity-Input.xlsx`, or choose **Save template** in the app. The template
   contains no sample records. Its **Unity Input** sheet has 35 operator columns
   grouped as Claim, Claimant, Provider, Adjuster and Attorney, text formatting,
   header comments, dropdowns, frozen headers and an autofilter. Instructions are
   on a separate sheet. One referral and one provider per row; start on row 2.
2. Fill and save the workbook in Excel, then choose **Open workbook**. The app
   lists filled rows, including incomplete or malformed records with warnings.
   Choose the intended row and **Load row**. This replaces the form, clears prior
   optional values and resets claim jurisdiction. It never starts automation.
3. Edit the grouped form. Supply **Claim jurisdiction** separately if known.
   Claimant address State is never inferred as jurisdiction. Jurisdiction is
   optional derivation context outside the 35 operator columns; it is not stored
   in this workbook, and must be reviewed again when switching rows.
4. Select a stage and choose **Validate fields** to see normalized input,
   warnings and derived values. **Run selected stage** performs validation again
   and starts a background worker. Before live work, open the intended RRS claim
   and verify its claim number, claimant and customer.
5. **All** resolves the attachment, runs Unity, writes tracking, waits for
   iCaseManager approval and completes assignment in RRS. **Unity** performs
   attachment / portal / tracking only. **Assign** waits for approval and completes
   RRS assignment; it does not run the portal, resolve attachments or write tracking.

### RRS assignment continuation

All and Assign use the same shared `AI/rrs_assignment.py` implementation through
legacy `CompleteAssignment`; Unity-only still stops after tracking. After the
operator confirms iCaseManager approval, completion performs RRS Assign ->
literal `"19"` in the input box -> OK -> optional Unity Complete Yes ->
Unity case lookup for the selected form/workbook claim -> required RRS Case Id
entry and OK -> optional second Unity Complete Yes -> optional RRS OK.
`19` keeps its original literal value; its business meaning is not established.
The existing `legacy.CMS.CheckCaseUnity` searches Unity UAT and chooses the
latest valid assigned-date case. No CMS registration or CheckAdvNotice is added.

The selected claim argument replaces stale legacy global data. Lookup errors or
blank case IDs stop before Case Id entry/submission; required write/click errors
and present optional-dialog failures now report `complete_assignment_failed`.
Only an optional dialog's absence timeout is ignored, and clicks are never
retried. The assignment input and Case Id are read back exactly before OK;
Case Id must close after its single OK click before final confirmations.
Operator messages identify the failed stage without including case or
referral values, retaining the original exception cause internally. The lookup
browser is closed on success and failure. The operator must still verify the
intended RRS record; field/prompt checks do not verify server persistence or
add automatic approval.

The Unity spec includes the shared AI module and package-scoped CMS runtime
dependency; frozen smoke checks cover resource/import prerequisites. Focused
synthetic controller/delegate tests cover order, the approval gate, current-claim
lookup, blank/error results, UI failures and optional-dialog absence. Source work
at FCM-1.1-70 did not exercise live RRS, Unity, CMS, Bedrock or the database and did
not build an EXE. FCM-1.1-74 subsequently packages this source for v1.0.7, with
packaged synthetic and bundled-source/module correspondence checks. The later
bounded UAT test selected the first queue result but stopped before Assign on
customer mismatch; no upload, task completion, tracking or RRS completion was
verified. Its identity gate was session-only, not a new production safeguard.
Unity is not integrated into Final Code.

### Standalone local referral document selection

Choose **Choose referral document** to select one existing PDF (`.pdf`), Outlook
message (`.msg`) or email (`.eml`), case-insensitively, with the native desktop
file picker. Review the displayed **Local document** basename
against the intended referral before running Unity or All. That exact absolute
path is passed to the existing legacy upload input; the app does not copy the
file, read/parse its contents, convert it to PDF, change the configured export folder, or put the path in
form fields, workbooks or configuration. The choice stays in session memory,
including across validation and workbook-row loading. Cancel keeps the prior
choice. Reloading the frontend obtains the current choice from the bridge;
restarting the app resets it.

**Use RRS export folder** clears the choice and restores the existing exactly-one
exported-file preflight (use RRS Complete Triage to produce that export). With a
local choice, zero or multiple export files do not matter. A moved, deleted or
invalid selected file fails explicitly, never falls back to exports, and is
checked again before the portal and upload. Local upload errors propagate to
the controller's failure/tracking policy rather than the legacy skip handler.
The attachment buttons are unavailable while busy; **Assign ignores attachments
entirely**, including a deleted local selection. Selection does not start a run.
Running Unity/All is live automation, not an offline document analyzer: normal portal,
tracking, and operator approval rules still apply.

Original PDF, MSG and EML selection is now packaged-synthetically verified in
the rebuilt EXE prepared for `unityassignment-v1.0.3` (FCM-1.1-54 below).
Server-side acceptance by the live Unity portal remains unverified; synthetic
metadata/path checks do not read actual Outlook files or prove portal acceptance.
The earlier `unityassignment-v1.0.2` artifact supports local PDF selection only;
actual publication of the replacement is recorded in GitHub releases.

`claimNumber` is always required. `customer`, `claimantFirst`, `claimantLast` are
also required for All / Unity. Every other operator field is optional. Blank
optional fields generate review warnings rather than blocking the controller.
Malformed supplied values still block all stages: dates, times, ZIPs, phones,
state choices, gender and service type. Dates accept MM/DD/YYYY or YYYY-MM-DD;
times accept HH:MM AM/PM or 24-hour HH:MM. ZIPs are five digits or ZIP+4. Identifiers
and ZIPs retain leading zeros. Excel dates/times and zero-padded numeric cells are
normalized; formulas and error cells are rejected. Duplicate recognized headers,
wrong sheets/extensions and empty workbooks are rejected. Partial recognized
columns can load for editing. Limits: 10,000 rows, 200 columns, **32,767 characters
for Special instructions** (Excel-compatible), and **1,000 characters for every
other form value**. Unknown form keys are rejected.

Special instructions uses a multiline text area. Embedded line breaks and
leading/trailing whitespace are preserved through workbook loading, validation
and the controller handoff; other fields retain their existing normalization.
The Python schema supplies each field's length limit to the form and synthetic
preview fixture. Values over the limit are rejected before running, not shortened.
Malformed workbook rows still load with warnings for correction. **Save template**
includes the current limits in its instructions and Special instructions header
comment; existing operator workbooks are not rewritten. Excel cells cannot hold
more than 32,767 characters, so keep the complete instructions within that limit
before saving a workbook. This change does not add portal note entry or readback;
legacy Unity uses Special instructions for facility matching.

Gender choices are Male, Female and Unknown. State choices are the 50 states from
the shared adapter. Service choices follow the legacy branches: Medical Full,
Medical Task, Vocational Full, Vocational Task, Employer and Other Services. Claim
type and injury descriptions remain free text because these Unity inputs are not
enumerations proven by the controller; values are not invented from another UI.

## Input counts and derivation

The supplied context contract has **39** keys. AST analysis of the actual
`legacy_unity.validate_and_complete_task` finds **39** keys, including
`nextApptTime` for the owner-approved missing-time flag guard. The test
`verify_legacy_keys` checks the exact consumption set. It parses
only the validation function, stopping before the next top-level definition,
without parsing the legacy sample dictionaries or relying on drifting sample
line numbers. All new fixtures and smoke data are synthetic.

The seven derivation keys are `claimStateAbbr`, `claimStateFull`, `refSource`,
`correctZipCode`, `ServiceType`, `refType`, `CaseObj`. Only five belong to the
39-key contract: `refSource` and `correctZipCode` do not. Therefore there are
**39 − 5 + 1 = 35 direct operator keys**, including the controller's extra
`claimNumber`. Appointment time remains optional; no flag checkbox or new
workbook input is required. Optional
claim jurisdiction is a separate derivation input, not an extra legacy operator
key or workbook column.

`unity_model.py` loads `Final Code/finalcode/field_adapter.py` read-only and calls
its `to_all_data` with canonical fields. It reuses state-name mapping,
`correctZipCode = providerZip`, blank referral source, and default routing:
Medical Full / Medical / Coordination of Care/Services. Auto + Continental Tire
+ MI claim jurisdiction derives Medical Task / Task / MI MCCA Attendant Care.
The optional office-workbook lookup is disabled for this locally loaded adapter:
this contract supplies `adjAddrFull` directly and has no office-number input.
Before loading the adapter, the model adds the existing repository root (or
frozen extraction root) to Python's import path when absent. This lets the
adapter import shared `AI` rules through direct `run.py`, `launcher.py`, backend
or model startup without relying on `PYTHONPATH` or pytest's root-path setup.

The legacy writes capital `ServiceType` in its Continental branch but reads
lowercase `serviceType` when selecting service. The desktop always supplies
lowercase `serviceType` to the controller. **Blank operator serviceType uses the
derived value**, including Continental's Medical Task. **An explicit operator
serviceType wins for the lowercase selection**, even if capital `ServiceType`
and other routing metadata derive differently. Review the displayed values for
that mismatch; both behaviors are tested. The field is present in every form
and workbook row but is optional, as is the controller input. Two later legacy
checks search lowercase `medical full` in an unlowercased value, so their portal
fallback behavior remains inconsistent; the app does not rewrite that legacy
DOM automation.

## Owner-approved missing appointment-time flag

When provider facility/name details or an appointment date exist and
`nextApptTime` is blank, the shared legacy portal path submits the restored
legacy flag. No provider/name/date means no flag; supplied time means no flag.
It retains the original first-reason selector (observed as **Missing information**
in the bounded inspection described below) and the exact note
**Missing Provider Appointment Time**.
The helper waits for actionable controls, scopes reason/note/submit to the
visible flag modal, clears the note and verifies its exact textarea value,
clicks Submit once, then waits for that modal to hide or disappear.

Only after that UI confirmation does the existing Unity process continue;
flagging is not an early stop. Opening, visible-dialog wait, reason selection,
note lookup/clear/type/readback, submission and closure failures raise a typed
`UnityFlagError` with the failed stage and original exception chain/type retained
in memory. Operator text excludes Selenium messages and page/referral content.
The legacy validation boundary re-raises this flag error and the Customer/Employer
Defined Fields errors described below; unrelated errors retain the existing marker behavior.
The desktop reports `run_unity_failed`,
stops provider work and never proceeds to approval or RRS completion.

**Owner-selected recovery policy (FCM-1.1-58): leave the browser open on flagging
failure for manual recovery.** Desktop Edge uses `detach=True`; on this typed
failure it stops the driver service and releases the HTTP connection without
issuing browser Quit. No retained-driver collection is needed. The failure
message explicitly says the browser was left open, asks the operator to inspect
flag status before acting (do not blindly retry an uncertain submission), and
to close the browser manually afterward. Service-release errors do not replace
the flag failure and are reported without their underlying details. Normal
success and unrelated failures still Quit. Other `create_driver()` callers
default to `detach=False`; the CLI keeps its existing cleanup and reporting.
Default attempted-assignment tracking on failure is unchanged.

Customer Defined Fields failures separately raise `UnityCustomerFieldsError`.
The shared legacy helper preserves populated Date of First Appointment and Claim
Identifier values, fills blanks only from supplied nonblank `nextApptDate` and
`claimID`, and requires exact UI readback of each write within the existing bounded
wait. Read-only polling allows asynchronous updates without repeating writes or
clicks. Blank optional source
values remain allowed. Stage-only operator text excludes referral/DOM/Selenium
details; the original exception remains chained. Under the owner's selected
customer-fields recovery policy, desktop automation stops before employer fields,
the existing manual-validation gate, Complete Task, approval and RRS, leaving
detached Edge open while releasing its service/connection. Cleanup failures are
reported without replacing the customer-fields error. Flag recovery text and
semantics, normal-success cleanup and unrelated-failure cleanup are unchanged.
CLI cleanup remains unchanged.

Owner-authorized read-only UAT inspection resolved exactly one visible existing
Liberty Mutual Commercial Market / `20 fields` header and both existing field
locators. Both inputs were initially hidden and populated; one header expansion
made both visible, enabled and not readonly. No field values were changed or
submitted. Because the header toggles visibility, the helper leaves an already
expanded group alone. It clicks once only when both fields are hidden, then
waits for both to become visible; mixed visibility, ambiguous matches and
unreadable state stop safely without multi-click fallback. No `aria-expanded`
state is assumed.

The full Unity suite includes actual-source synthetic tests for these states,
blank/populated/whitespace handling, write-readback failures, stopped continuation
and desktop cleanup failures. Neither these tests nor the inspection confirms
the owner's original live failure trigger. The three-second wait, exact header
selector and existing field locators remain unchanged; the field-count constraint
remains brittle despite matching the inspected task. No live source replay,
RRS/CMS/Bedrock calls, submission, build or release was exercised for this fix.

**Employer Defined Fields (FCM-1.1-78, source-only):** one shared legacy helper
preserves any populated Facility selection. For a blank, it selects only a unique
enabled non-placeholder option: recognized special-instructions facilities take
precedence over a nonblank provider-city fallback. Multiple recognized facilities,
ambiguous options and no matches leave the field unchanged for the existing
no-match notice and attended manual-validation gate. A recognized facility absent
from the options does not fall back to city. Blank city never selects a placeholder.
An already-visible Facility leaves the header untouched; a hidden field permits
one header click followed by a visibility wait. The existing Goodyear-only
applicability, employer name / `4 fields` header requirement, Facility ID and 25 recognized
facilities are retained; no other employer-field policy is introduced.

Each selection is a single write with exact selected text/value verification
using bounded read-only polling. Locate, visibility, read, selection and readback
failures raise stage-only `UnityEmployerFieldsError`, retaining the original
exception cause without exposing referral/DOM/Selenium details. Desktop recovery
leaves detached Edge open for inspection and releases the service/connection
without Quit, reporting release failures without replacing the employer error.
Later portal work, Complete Task, approval and RRS do not run on that error.
Existing attempted-assignment tracking, other recovery messages, normal/unrelated
cleanup and CLI cleanup are unchanged. Actual-source synthetic regressions cover
these states and asynchronous readback; they do not prove live portal persistence.
No live source replay, RRS/CMS/Bedrock call, submission, EXE build or release was
performed for this source change.

**Header capitalization correction (FCM-1.1-79, source-only):** the employer
header XPath normalizes only capitalization of the same Goodyear name, retaining
its whitespace normalization and `4 fields` requirement. Exactly one visible
matching header is required; count token boundaries exclude `14 fields` and `24 fields`.
That header must be enabled; duplicate visible headers, read failures and
an unavailable actionable header stop safely. Owner-authorized read-only UAT
inspection found exactly one visible header after case normalization, but none
with the old case-sensitive name predicate. The Facility select was visible and
enabled, with 37 options and a selected blank-text, empty-value placeholder.
It was not a populated Facility. No field values were changed, no options were
selected and no source fix was replayed live. Actual-XPath synthetic DOM coverage
includes mixed-case/whitespace headers, wrong employers/counts and duplicate or
hidden groups. This does not broaden employer applicability or relax field count;
no live writes, submission, build or release was performed.

Textarea readback and modal closure are **not server-side flag/task readback**.
At FCM-1.1-58, the original failure root remained **unconfirmed**. Before that source change,
owner-authorized, non-submitting inspection found the modal visible and all
three existing relative reason/note/submit XPaths resolving. The Angular host
had a zero-sized rectangle, which does not establish Selenium invisibility or
prove a selector defect. A bounded UI probe selected Missing information and
entered the exact note, confirmed exact readback and an enabled Flag Referral
button before/after blur, then closed the modal. No actual flag, Complete Task
or assignment was submitted. No source replay or server persistence was
verified. FCM-1.1-58 is source-only with synthetic regression/self-test evidence;
no frontend, EXE build or release was made. Published v1.0.4 is unchanged.

### Confirmed note layout change (10/23/2026, FCM-1.1-68)

Later owner-authorized read-only inspection opened Flag, selected Missing
information, inspected controls and closed the modal without entering a note or
submitting. After reason selection, the old numbered-div note XPath found no
element; the textarea with ID
`intake-flag-for-intervention-description-text-area` was present, visible and
enabled within that same modal. UI Automation confirmed one enabled field with
that ID. The reported v1.0.5 error, `Unity flagging failed while locating the flag
note`, corroborates this current root cause; the earlier FCM-1.1-58 observation
is historical, not proof of the post-selection layout.

The source now uses that stable ID with the existing modal-scoped actionable
wait. No reason/submit selector, trigger, note text/readback, single-submit,
closure/continuation or browser-recovery policy changed. A focused actual-source
regression removes the old path on reason selection while retaining the stable
ID and verifies modal-scoped lookup, exact note and one submission/continuation.
All existing failure cases remain covered. Focused Unity regressions passed
**87 methods / 330 JUnit cases including subtests**, zero failures/errors/skips;
the direct source self-test exited **0** with 39 consumed keys, no context-only
keys, the five-step flow and selected PDF/MSG/EML synthetic flows completed,
32,767-character instructions preserved and oversized input rejected.

This is source-only evidence: no live source replay, note entry, flag submission,
server validation, browser operation, frontend/EXE build or release occurred
during implementation. RRS, CMS, Bedrock, database and live portal integrations
were not exercised. Published v1.0.5 does not contain this source fix.
FCM-1.1-59 remains blocked by the customer mismatch; no full live flag is claimed.

## Outcomes, prompts and live limitations

The footer keeps stage and elapsed time visible. iCaseManager confirmation and
attachment notifications appear in an operator dialog. A UUID prompt and Event
are registered under a lock; the worker waits **outside** that lock. Polling is
responsive during confirmation. Duplicate starts, workbook replacement while
busy, non-boolean answers and stale prompt responses are rejected. A notification
must be acknowledged; Yes / No confirmation controls assignment completion.

Completed, stopped and failed are separate outcomes. Stops are prominent:

- `attachment_missing`: choose a local referral document or export through RRS Complete Triage.
- `attachment_ambiguous`: choose a local referral document or clear the export folder and re-export the intended
  referral; the controller requires exactly one candidate file.
- `icasemanager_declined`: Complete Assignment did not run after No.

Live wiring is the default for the desktop. Imports and COM initialization are
lazy on the worker; COM is released afterwards. The bridge loads the configured
legacy Unity module, creates/logs in its driver, calls the existing validation
stage and closes the driver. Tracking and Complete Assignment use the same
configured legacy FCM functions as the scenario runner's live path. Fakes can be
injected through `UnityAPI(callbacks_factory=...)`; no live dependency is needed
for regression tests or smoke.

Both legacy `main` and the validation stage swallow exceptions. The desktop
bypasses `main` and captures the validation call's stdout only in memory to
recognize its `error occurred:` failure marker. Marker failures become controller
failures. Inner legacy handlers that silently continue remain unverifiable;
completed means the selected callbacks returned without a recognized error,
not that every portal field has been independently audited. The stdout capture
is process-wide during the single portal call, so do not run concurrent automation
workers in this process. No real portal/database workflow was exercised during
implementation.

The tracking-on-Unity-failure checkbox defaults to **on**, preserving the existing
controller's legacy attempt-record behavior. Turning it off skips tracking only
on Unity failure; successful runs still record. There is no mid-operation cancel
or rollback. Finish pending dialogs before closing; the launcher blocks close
while a worker is active. Changes already made in Unity, tracking or RRS persist
after a stop/failure. Local document mode binds the exact selected path but does not
verify document contents or portal readback. FCM-1.1-48 remains open for export-mode
binding and live outcome verification. Export-folder resolution is a preflight check; the legacy
uploader still reads that folder, so keep it stable throughout the run. Existing
`run.py --live` CLI behavior remains available for compatibility; use desktop
for the complete grouped payload and guarded error reporting.

## Development and acceptance

```powershell
npm --prefix Processes/Unity/Stand-Alone/frontend run dev
# Open the displayed localhost URL with ?mock=1 for an explicit synthetic preview.
.venv-bedrock/Scripts/python.exe Processes/Unity/Stand-Alone/run.py --self-test
.venv-bedrock/Scripts/python.exe -m unittest discover -s Processes/Unity/Stand-Alone -p "test*.py" -v
.venv-bedrock/Scripts/python.exe Processes/Unity/Stand-Alone/run.py --all-scenarios
```

The browser mock is explicitly labeled and never touches live systems. It previews
fields, stage completion and approval/decline; workbook dialogs and full Python
validation require desktop. It is not a replacement for Python validation tests.

The original 17 tests and nine scenario JSONs are unchanged. The new 23 tests
cover workbook styling/read/bad inputs, counts/AST, validation/Continental routing,
worker states, attachment stops, live wiring, failure markers, tracking behavior,
COM lifecycle, confirmation polling and stale responses. Acceptance totals are
40 Unity tests and 36 SubjectLineBuilder sibling tests; baseline is 366 passed,
1 skipped. The scenario runner deliberately exits 2 because its fixtures include
stopped and failed outcomes. 

### Source startup verification (10/22/2026, FCM-1.1-47)

Using installed Python because the documented virtual environment was absent:

```powershell
python -m pytest Processes\Unity\Stand-Alone\test_flow.py Processes\Unity\Stand-Alone\test_unity_desktop.py -q -p no:cacheprovider -o addopts=
python Processes\Unity\Stand-Alone\run.py --self-test --report "$PWD\Output\Unity-source-self-test.json"
python Processes\Unity\Stand-Alone\run.py --all-scenarios
```

All **43 tests / 130 JUnit cases including subtests** passed. Three startup
regressions cover real `run.py` and `launcher.py` subprocess self-tests from the
repository root with `PYTHONPATH` removed, model/backend imports from the standalone
directory, and the actual spec's hidden imports against the raw adapter's `AI`
imports. Before the fix, both entrypoints, both imports and the spec check failed.
The direct source self-test completed the synthetic workbook roundtrip and all
five controller steps. All nine scenarios retained their expected outcomes
(one completed, three stopped, five failed; aggregate exit 2 is intentional).

The frontend initially lacked TypeScript dependencies. After restoring the lockfile
with `npm ci`, the production build and `node frontend\smoke.mjs` passed.
The headless Edge mock checked form editing, validation preview, a blocking
confirmation that Escape cannot dismiss, decline-to-stop and Unity-only
completion, with no browser page errors. This does not exercise the live bridge.

These are source and static packaging checks, not a desktop-window or executable
smoke test. `dist\UnityAssignment.exe` was absent and no EXE was built or run.
No live Unity portal, database, RRS, CMS or Bedrock was exercised; Unity remains
standalone and outside Final Code.

### Special instructions expansion verification (10/22/2026, FCM-1.1-49)

```powershell
python -m pytest Processes\Unity\Stand-Alone\test_flow.py Processes\Unity\Stand-Alone\test_unity_desktop.py -q -p no:cacheprovider -o addopts=
npm --prefix Processes\Unity\Stand-Alone\frontend run build
node Processes\Unity\Stand-Alone\frontend\smoke.mjs
```

All **49 Unity source tests** passed using installed Python (the documented
virtual environment was absent). Focused synthetic regressions accept 1,001 and
32,767 instruction characters, preserve exact leading/trailing whitespace,
newlines and the trailing sentinel through validation/controller callbacks, and
roundtrip a full 32,767-character Excel cell through row selection. They reject
32,768 instruction characters before worker creation or callbacks; every other
field still rejects 1,001 characters. The frontend fixture is checked against
the Python schema. Workbook styling, 35 columns, five dropdowns, blank-template
contents and malformed-row correction behavior remain covered.

The production frontend build and actual built-frontend headless Edge smoke
passed with zero page errors. Browser checks cover the textarea, schema-driven
length limits, exact long multiline content after editing/validation, explicit
over-limit validation without truncation, ordinary inputs and the existing
approval/decline flow. This is a synthetic browser mock, not live bridge or
portal readback evidence. No live Unity/RRS/CMS/Bedrock/database, EXE rebuild,
release, commit or push; operator workbook/sample files are unchanged.

## Windows executable

Install the pinned Python build/runtime dependencies from the repository root,
then build:

```powershell
.venv-bedrock/Scripts/python.exe -m pip install -r Processes/Unity/Stand-Alone/requirements-build.txt
powershell -ExecutionPolicy Bypass -File Processes/Unity/Stand-Alone/build.ps1
```

`requirements-build.txt` records the versions verified in `.venv-bedrock`; it
pins direct build/runtime dependencies, not the complete transitive environment.
The script builds the current frontend first, packages into a unique LocalAppData\Temp
work directory, then copies `UnityAssignment.exe` and `UnityAssignment.exe.sha256`
to the gitignored repository `dist/`. PyInstaller, npm, the existing virtual
environment, office matrix workbook and prepared IE driver are prerequisites.
The EXE opens the desktop by default. Run an offline check with
`dist/UnityAssignment.exe --self-test --report <absolute-report-path>`. Without
`--report`, self-test writes `UnityAssignment-self-test.txt` in the OS temp folder.
This synthetic check does not connect to Unity, RRS or the database. WebView2,
configured credentials, ODBC and the operator's local settings remain live prerequisites;
secrets and machine-specific settings are not bundled.

The bundle preserves repository-relative paths for the Unity controller, runner,
legacy modules, field adapter and office lookup. The desktop deliberately disables
the adapter's optional office-number lookup, but its module and workbook are
included so the adapter's complete resource layout remains intact.
Because the adapter is bundled as a raw file, the spec explicitly declares its
`AI.appointment_rules` dependency as a hidden import, along with the selected
document path validator `AI.referral_attachments`. Static regression checks cover
these dependencies; the current rebuilt executable also passed the packaged
checks below.

### v1.0.1 build and release preparation (10/22/2026, FCM-1.1-50)

The then-current production frontend and Unity EXE were built for
`unityassignment-v1.0.1`. Because `.venv-bedrock` was absent and `build.ps1` assumes
that environment, the build used installed **Python 3.13 / PyInstaller 6.22.3**
with the equivalent PyInstaller command and the existing Unity spec. The EXE
was copied to gitignored `dist\UnityAssignment.exe`; its checksum sidecar was
generated.

| Prepared artifact | Verified value |
| --- | --- |
| Size | 48,451,492 bytes |
| SHA-256 | `e3b1fa3dbca4a78bd72b71f33aab3e39da7ceab66de45a266d4d5cb7e986a54b` |

The rebuilt EXE's `--self-test` exited **0**. Its report begins
`Frozen resource layout and live import prerequisites: OK`, followed by JSON
reporting completion of all **five stages**, `instruction_length: 32767` and
`oversized_rejected: true`. The synthetic workbook roundtrip and injected
controller callbacks preserved exact instruction whitespace and the trailing
suffix. Frozen-resource and prerequisite-import checks passed; the callbacks
did not invoke live automation.

Independent source verification passed **49 tests / 184 JUnit cases including
subtests**, with zero failures, errors or skips. The production frontend build
and synthetic headless Edge smoke also passed with zero page errors. These
later checks supplement, rather than change, the source-only evidence recorded
for FCM-1.1-47 and FCM-1.1-49 above.

The artifact was prepared for `unityassignment-v1.0.1` after its successful
packaged check; publication is recorded in the repository's GitHub releases.
Windows with the WebView2 Runtime remains required for the desktop; live use
also requires the configured legacy automation/browser driver, ODBC/database
access, credentials and operator-local settings. Successful prerequisite imports
do not establish those services' availability. No native-window end-to-end or
live Unity, RRS, CMS, Bedrock or database workflow was exercised. Unity remains
standalone; operator workbook/sample files and graph output were excluded.

### v1.0.2 build and release preparation (10/22/2026, FCM-1.1-52)

The production frontend and Unity EXE were rebuilt with FCM-1.1-51's standalone
local PDF selection for tag `unityassignment-v1.0.2`. The absent documented
virtual environment again required installed **Python 3.13 / PyInstaller 6.22.3**
and the equivalent command using the existing Unity spec.
Gitignored `dist\UnityAssignment.exe` and `dist\UnityAssignment.exe.sha256`
contain the prepared artifact and checksum:

| Prepared artifact | Verified value |
| --- | --- |
| Size | 48,454,989 bytes |
| SHA-256 | `632adbef6dfe52459e95c3f44e7c2d516ce154d9975a647da73790a1276ad862` |

The packaged `--self-test` exited **0** with
`Frozen resource layout and live import prerequisites: OK`. Its original report
completed all **five steps**, retaining `instruction_length: 32767` and
`oversized_rejected: true`. The additional `local_pdf_result` completed
`resolve_attachment`, `run_unity` and `record_assignment` with the exact
synthetic-selected `.PDF` path through injected callbacks. No actual attachment
contents were read.

Independent focused source verification passed **56 tests / 195 JUnit cases
including subtests**, with zero failures, errors or skips. The refreshed production
frontend build and built-frontend headless Edge synthetic mock passed with zero
page errors. This supplements FCM-1.1-51's dated source-only evidence with packaged
synthetic verification, not live upload or portal/task readback.

The artifact is prepared for `unityassignment-v1.0.2`; actual publication is
recorded in the repository's GitHub releases. The desktop requires Windows and
the WebView2 Runtime. Live use additionally requires the configured legacy
automation/browser driver, ODBC/database access, credentials and operator-local
settings; successful frozen prerequisite imports do not prove their availability.
No native-window end-to-end or live Unity portal, database, RRS, CMS or Bedrock
workflow was exercised. Unity remains standalone and FCM-1.1-48 remains open.

### v1.0.3 Outlook build and release preparation (10/22/2026, FCM-1.1-54)

The production frontend and Unity EXE were rebuilt with FCM-1.1-53's original
PDF, MSG and EML selection for tag `unityassignment-v1.0.3`. With the documented
virtual environment absent, the build used installed **Python 3.13 /
PyInstaller 6.22.3** and the existing Unity spec.
Gitignored `dist\UnityAssignment.exe` and `dist\UnityAssignment.exe.sha256`
contain the prepared artifact and checksum:

| Prepared artifact | Verified value |
| --- | --- |
| Size | 48,454,618 bytes |
| SHA-256 | `901bbc87834682160ab4a4a0f57e97abdb98be396e5d397337666f91e2f54939` |

Packaged `--self-test` exited **0** with
`Frozen resource layout and live import prerequisites: OK`, including the new
shared `AI.referral_attachments` dependency. The original report completed all
**five steps**, retaining `instruction_length: 32767` and
`oversized_rejected: true`. Additional selected-PDF, MSG and EML cases each
completed `resolve_attachment`, `run_unity` and `record_assignment` using the
exact original synthetic-selected path through injected callbacks, without
conversion or reading actual attachment contents.

Source verification passed **73 test methods / 273 JUnit cases including
subtests**, with zero failures, errors or skips. The production frontend build
and built-frontend headless Edge synthetic mock passed with zero page errors.
This supplements FCM-1.1-53's dated source-only/no-rebuild evidence; it does not
change that historical record.

The artifact is prepared for `unityassignment-v1.0.3`; actual publication is
recorded in GitHub releases. Windows/WebView2 Runtime, configured legacy
automation/browser driver, ODBC/database access, credentials and operator-local
settings remain prerequisites. No native-window end-to-end or live Unity portal,
database, RRS, CMS or Bedrock workflow was exercised, and no actual Outlook file
contents were read. Synthetic metadata/path handling does not establish MSG/EML
server acceptance or portal/task readback. Unity remains standalone;
FCM-1.1-48 remains open. Operator workbook/sample files and graph output were
excluded.

### v1.0.8 field recovery build (10/23/2026, FCM-1.1-80)

Rebuilt the production frontend and existing Unity spec with installed Python
and PyInstaller, including FCM-1.1-75 customer fields and FCM-1.1-78/79 employer
Facility safeguards, header capitalization and desktop browser recovery.
The artifact prepared for `unityassignment-v1.0.8` is 48,483,856 bytes; SHA-256:
`910adb3d318e8254f2d63b9b3216264b8057cba937e8f3c36e84525f49c1d89a`.
The EXE and its `.sha256` sidecar belong in ignored `dist`, not source control.

Packaged `--self-test` exited 0 with frozen resource/import prerequisites OK,
39 consumed keys and no context-only keys. The five-step main flow and selected
PDF/MSG/EML three-step flows completed through synthetic callbacks; 32,767-character
instructions and oversized rejection passed. Independent archive checks matched
six raw sources, six compiled modules (including both new error classes and the
legacy UI helper), and all three built frontend files to the worktree. No
operator/sample/session payload assets were found. Source/Final Code packaging
boundary checks passed 93 test cases with no failures, errors or skips.

This supplements the dated source-only records, not live validation: no corrected
helper was replayed against the portal and no live RRS, CMS, Bedrock, tracking,
upload or task submission was performed. Existing Windows/WebView2 and live
environment prerequisites remain. Other employer fields remain manual; Unity
remains standalone. Actual publication is recorded in GitHub releases.
