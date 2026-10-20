# SubjectLineBuilder

The standalone accepts **Excel input or manual entry**. It operates on the intended RRS
Email Display / Subject Line Builder already opened by the operator. It does not
read PDF attachments, call AI, connect to CMS or run reopen-check. The only
referral row it selects is the one for Complete Triage after Create. The legacy
main application's separate triage call is unchanged; Final Code wiring is
described below.

## Manual standalone flow

1. Open the intended referral's Email Display in RRS.
2. Fill `Stand-Alone/SubjectLineBuilder-Input.xlsx` (also supplied in `dist`).
   Use **Open Excel**, select a referral row, then **Load row** to populate the form.
   Review or edit customer/claimant/provider data before starting.
   Adjuster, nurse and attorney fields are available as optional groups.
3. Start. The application opens Subject Line Builder and fills identity fields.
4. It searches claimant, like items and provider; adjuster and attorney lookups
   run when their names/contact details are supplied. Select the correct record
   in RRS, or add the record there, close the lookup and Continue in this app.
5. It fills supplied claimant, appointment and claim details. Search and manual
   Add fields remain visible for reference. It does not automatically create
   provider/attorney master records or invent missing data.
6. Review all builder fields, including the selected referral type. Medical or
   Vocational is selected from the entered referral type; RRS determines the final
   subject format. Click **Create in RRS** explicitly to submit.
7. The app rechecks the claim number on the same builder window before Create.
   Completion is reported only after that window closes. If it stays open, inspect
   RRS before retrying because submission may already have happened.
8. Complete Triage (ported from legacy `CompleteTriageAndExportAttachment`): the
   app exits the Email Display and ticks only the work-window row whose Subject
   contains the claim number. It then clicks **Complete Triage** and answers the
   prompts as legacy did:
   - Zip Code?: provider ZIP for Full Case Management / One-Time RN Visit,
     otherwise the claimant ZIP.
   - Information Complete?, Unity ReTrigger and Customer Check: Yes.
   - ReferralRoutingSystem: OK.

   It then exports the attachment in Unity Entry and exits it. If no row (or more
   than one) matches the claim, it stops and you finish triage manually. Unity
   assignment (CMS case id) and Complete Assignment remain manual.

One provider per run. Data stays in session memory and is not automatically saved
to disk. Stop/close prevents subsequent automation after the current UI call; it
does not undo edits or master-record changes in RRS.

## Final Code completion boundary

`Final Code/finalcode/live_wiring.py::make_subject_line` runs the shared builder
with reviewed, CMS-validated `allData`. Only a builder result with
`status="completed"` then loads this process's `rrs_ui.py` through the shared
path loader and calls `RRSAdapter.complete_triage(allData)` once. It uses the
same dictionary, not a recapture or the builder's diagnostic `data` payload.
Stopped, failed and invalid builder results never start triage.

This reuses step 8 above: close any remaining Email Display, uniquely match the
claim's work row, click Complete Triage, answer the legacy ZIP/confirmation
prompts, export with Unity Entry's `btnDownload`, acknowledge export confirmation
and exit that window. Final Code returns the original builder result only after
export returns; adapter/load/triage/export exceptions fail the existing
**SUBJECT LINE BUILDER** stage. Unconfirmed export fails without exiting Unity
Entry. No automatic retry is added; inspect RRS before rerunning a failed stage.

The stop is **before Unity assignment**: no `OpenUnity`, `CompleteAssignment`,
`Processes/Unity`, database logging or legacy `main` is invoked. Shared
`subject_line_flow.run_flow` defaults are unchanged because legacy `main` already
calls triage separately. Supplied runtime identity, deferred legacy initialization
and Email Display reacquisition remain intact. FCM-1.1-39 is source-only; synthetic
boundary and actual-adapter sequence tests do not establish live RRS/CMS/Bedrock/
portal behavior or packaged EXE behavior.

## Excel input

**Save template** creates another blank copy from the app. Enter one referral and
one provider per row in **Subject Line Input**, starting at row 2. The Instructions
sheet explains required fields, defaults and formatting. Keep the headers and
sheet name; column order may change and unused optional columns may be omitted.
The workbook includes 500 preformatted rows; import accepts up to 10,000 rows.

Dates need a year; use MM/DD/YYYY and optional appointment time such as 08:30 AM.
Keep identifiers and ZIP codes as text to preserve zeros. Formulas are rejected;
paste values instead. Incomplete rows load with validation guidance. Loading a row
replaces all form values and never starts automation. Unsaved form edits are not
written back to Excel. Blank market, referral type and source use the documented
defaults, which the operator must review. This template has its own schema;
AI PDF Reader daily output workbooks are not supported by this importer.

## UI and executable

React + TypeScript + Tailwind, compact shadcn-style controls, Lucide icons and
pywebview. Uses AI PDF Reader's light blue/slate theme, copied style baseline,
and shared native width constraint: 480 x 900 logical pixels, fixed width and
resizable height (minimum 600, monitor-aware). Bottom Fields / Review / Help
navigation appends panels; progress and action buttons stay visible.

```powershell
rtk proxy .venv-bedrock/Scripts/python.exe Processes/SubjectLineBuilder/Stand-Alone/run.py
rtk proxy powershell -NoProfile -File Processes/SubjectLineBuilder/Stand-Alone/build.ps1
```

Output: `dist/SubjectLineBuilder.exe`. Windows and Microsoft Edge WebView2 Runtime
are required; Python, React assets and pywinauto are bundled. RRS must be open in
the same interactive Windows session at a compatible privilege level. No AWS,
Selenium, database credentials or installed Python are needed by the EXE.

## Code boundaries

- `Deploy-Ready/manual_flow.py`: standalone schema, validation and guided workflow.
- `Deploy-Ready/excel_input.py`: Excel template and reusable workbook reader.
- `Deploy-Ready/rrs_ui.py`: focused RRS controls and submission boundary.
- `Deploy-Ready/body_part.py`, `injury_match.py`: re-export the RRS Body Part / Injury
  Type / Injury Cause rules and matcher, which the AI PDF Reader owns
  (`AI/injury_classification.py`). The EXE bundles that module.
- `Stand-Alone/backend.py`: worker, progress, review gates and cancellation.
- `Stand-Alone/frontend`: manual form; `launcher.py` hosts WebView2.
- `Deploy-Ready/legacy_steps.py` and `subject_line_flow.py`: shared main-app
  migration path with original upstream stages. Not imported by manual standalone.
- `src/fcm_intake/workflows/subject_line_builder.py`: unchanged main-app adapter.
  Do not switch the main workflow to the manual runner.

The shared `subject_line_flow.py` controller retains an ordinary exception behind
the legacy handler's `SystemExit`: failures include its type/message and builder
source filename/line in `error`, plus `type` metadata, without returning a raw
traceback or runtime data. Direct exceptions use the same diagnostics. Explicit
exits without an ordinary exception retain the generic error and exit code.
Final Code propagates these diagnostics.

The shared legacy Final Code path now fills blank/`None` Injury Type and Injury
Cause through the existing `RRSAdapter.fill_dropdown` and shared
`AI.injury_classification` matchers (FCM-1.1-38). It enumerates actual dropdown
options, preserves nonblank prefilled values, and never writes arbitrary input
text. Missing or unmatched input explicitly requests manual selection. This path
opts into option/readback verification: missing SelectionPattern is supported
through ValuePattern; unreadable values/options, failed writes and mismatched
readback fail the controller rather than claiming selection. Imports are local
to survive controller rebinding; the existing path loader locates `rrs_ui.py`
without requiring `Deploy-Ready` on `sys.path`. Standalone defaults, body part,
claim type and triage are unchanged. Synthetic actual-block/controller and
adapter tests passed: 64 tests across `test_flow.py` and `test_manual.py`. Read-only
inspection found blank enabled injury controls with ValuePattern but no
SelectionPattern; no live selection, workflow or EXE build validated this fix.

The shared legacy claimant lookup now matches the owner's confirmed standalone
behavior for exactly one result: click row 0's checkbox, then Select, without
requiring Source, DOB, DOI or LOI to match. It reports success only after both
clicks complete; click exceptions propagate to the existing failure handler.
Multiple-result EDI matching, manual notification, no-match and zero-row behavior
remain unchanged, as do search filters and date handling. Synthetic actual-source
closure tests cover these decisions and click failures (FCM-1.1-37). No live
claimant selection, full workflow or EXE build was performed for this fix.

Both shared legacy provider-search paths seed and verify the canonical provider
identity and any available canonical `providerPhone` before every Search, including
the first pass with prefilled RRS location or contact filters. A supplied phone
replaces blank or stale `tbPhone` text, retaining its formatting except surrounding
whitespace. With no canonical phone, the first pass preserves the existing phone
filter; later stages retain their existing clearing behavior. Other non-name
filters remain unchanged, and the first pass routes
matching by canonical facility versus doctor identity, not a stale/blank RRS
facility field. Existing staged queries remain: the main path uses the first
meaningful facility token (skipping `THE`), while the missing-information path
uses its existing cleaned full facility name and local validation-result tuple.
Conflicting doctor/facility fields must clear, and required name and supplied
phone writes (including the existing keystroke fallback) must pass exact readback before searching.
Missing identity or a failed write/readback stops execution before Search or
AddNew with control-ID-only, value-free diagnostics. Other optional filter handling and the
authoritative Final Code provider adapter are unchanged. Synthetic tests execute
the actual nested closures. FCM-1.1-35's subsequent bounded live main-path smoke
verified name entry and one zero-result synthetic search in about 19 seconds,
with no selection/AddNew/Create; the synthetic name was removed afterward.
FCM-1.1-36 phone behavior remains live-unverified: no live calls or field writes
were made for that change, and no app restart or EXE build was performed.

The shared legacy Employer write keeps UIA `ValuePattern.SetValue` as its normal
path, refreshing `tbEmployer` after the existing focus delay. Only
`NoPatternInterfaceError` triggers the native `WM_SETTEXT` fallback. A valid
same-control HWND is retained; a zero or invalid cached HWND instead triggers
native Edit enumeration strictly inside the current builder, requiring exactly
one independently resolved UIA `automation_id="tbEmployer"` match. Before writing,
the fallback verifies the native identity, same process and native child ancestry,
an actionable Edit without the read-only style, the native write result and
exact-case text readback. Missing or ambiguous matches fail explicitly. It does
not log the employer value, retry, send keystrokes or search another window;
other fields retain their existing writes. Synthetic tests cover this path and
controller containment. An owner-authorized live field-level check also executed
the actual Employer block with a simulated missing pattern and zero cached HWND:
native recovery wrote the existing value back unchanged and verified it. No
Create, submission or remaining stages ran; end-to-end completion is unverified.

## Verification

```powershell
rtk proxy .venv-bedrock/Scripts/python.exe -m unittest discover -s Processes/SubjectLineBuilder/Stand-Alone -p "test_*.py" -v
rtk proxy npm --prefix Processes/SubjectLineBuilder/Stand-Alone/frontend run test:e2e
rtk proxy .venv-bedrock/Scripts/python.exe Processes/SubjectLineBuilder/Stand-Alone/launcher.py --self-test --report Output/subject-line-smoke.txt
```

The EXE accepts the same `--self-test --report <path>` arguments. Tests use
synthetic input and a fake RRS adapter. Native checks validate the real WebView2
window and Python/React bridge. Live RRS execution still requires validation;
offline tests do not establish live selector compatibility.
