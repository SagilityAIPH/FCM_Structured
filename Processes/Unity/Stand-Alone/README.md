# Unity desktop

Unity is a Python pywebview / WebView2 desktop app with a React TypeScript, Vite,
Tailwind and house shadcn frontend. It runs the existing Unity assignment
controller without changing `Deploy-Ready/unity_flow.py`. Form data stays in
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

`claimNumber` is always required. `customer`, `claimantFirst`, `claimantLast` are
also required for All / Unity. Every other operator field is optional. Blank
optional fields generate review warnings rather than blocking the controller.
Malformed supplied values still block all stages: dates, times, ZIPs, phones,
state choices, gender and service type. Dates accept MM/DD/YYYY or YYYY-MM-DD;
times accept HH:MM AM/PM or 24-hour HH:MM. ZIPs are five digits or ZIP+4. Identifiers
and ZIPs retain leading zeros. Excel dates/times and zero-padded numeric cells are
normalized; formulas and error cells are rejected. Duplicate recognized headers,
wrong sheets/extensions and empty workbooks are rejected. Partial recognized
columns can load for editing. Limits: 10,000 rows, 200 columns, 1,000 characters
per form value. Unknown form keys are rejected.

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
`verify_legacy_keys` checks both the exact set and this discrepancy. It replaces
lines 1464–1500 with blank lines during parsing and never inspects or copies the
prohibited commented record. All new fixtures and smoke data are synthetic.

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

- `attachment_missing`: export this referral through Complete Triage first.
- `attachment_ambiguous`: clear the export folder and re-export the intended
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
after a stop/failure. Export-folder resolution is a preflight check; the legacy
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
