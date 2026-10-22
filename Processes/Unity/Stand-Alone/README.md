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
`legacy_unity.validate_and_complete_task` finds **38** keys: `nextApptTime` is
absent from the function, so the advertised list is not an exact consumption
list. It remains an optional forward-compatible form/workbook field. The test
`verify_legacy_keys` checks both the exact set and this discrepancy. It parses
only the validation function, stopping before the next top-level definition,
without parsing the legacy sample dictionaries or relying on drifting sample
line numbers. All new fixtures and smoke data are synthetic.

The seven derivation keys are `claimStateAbbr`, `claimStateFull`, `refSource`,
`correctZipCode`, `ServiceType`, `refType`, `CaseObj`. Only five belong to the
39-key contract: `refSource` and `correctZipCode` do not. Therefore there are
**39 − 5 + 1 = 35 direct operator keys**, including the controller's extra
`claimNumber`. The 38 consumed keys imply 34 directly consumed operator keys;
the additional appointment-time field makes the desktop count 35. Optional
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
DOM automation. Appointment time is retained but not consumed by that code.

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
