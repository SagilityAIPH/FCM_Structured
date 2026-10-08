# SubjectLineBuilder

The standalone accepts **Excel input or manual entry**. It operates on the intended RRS
Email Display / Subject Line Builder already opened by the operator. It does not
select RRS referral rows, read PDF attachments, call AI, connect to CMS or
run reopen-check. Main application behavior is unchanged.

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

One provider per run. Data stays in session memory and is not automatically saved
to disk. Stop/close prevents subsequent automation after the current UI call; it
does not undo edits or master-record changes in RRS.

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
- `Stand-Alone/backend.py`: worker, progress, review gates and cancellation.
- `Stand-Alone/frontend`: manual form; `launcher.py` hosts WebView2.
- `Deploy-Ready/legacy_steps.py` and `subject_line_flow.py`: unchanged main-app
  migration path with original upstream stages. Not imported by manual standalone.
- `src/fcm_intake/workflows/subject_line_builder.py`: unchanged main-app adapter.
  Do not switch the main workflow to the manual runner.

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
