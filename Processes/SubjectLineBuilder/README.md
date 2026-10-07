# SubjectLineBuilder

Standalone entry point for the existing RRS subject-line workflow. The main
application and this runner execute the same implementation in this folder.

## Layout

- `Deploy-Ready/legacy_steps.py`: moved original UI implementation, with its
  function body unchanged. Debug the existing UI steps here.
- `Deploy-Ready/subject_line_flow.py`: shared execution/result controller.
- `Stand-Alone/run.py`: offline scenarios and explicit live CLI entry point.
- `Stand-Alone/test_flow.py`: independent controller tests.
- `src/fcm_intake/workflows/subject_line_builder.py`: thin application adapter.

## Current boundary and inputs

Live input is the **first referral row (row 0)** in the open Referral Routing
System window, not an arbitrary selected row. The original implementation opens
Email Display and captures the matching PDF attachment. It validates the data,
runs existing reopen/customer checks and provider/address searches when required,
then opens and populates Subject Line Builder, runs the claimant/provider/attorney
and referral-source lookups, and asks the operator to review before Create.

The standalone runner stops after creation and closing Email Display. It does
not call CompleteTriageAndExportAttachment, OpenUnity or CompleteAssignment.
The main app still continues to those stages when the builder completes.

This first extraction does **not** isolate the individual lookup stages or
replace PDF capture with the daily AI workbook. Those dependencies remain in
the moved implementation. Next, separate data acquisition and field population
so daily workbook input can use `AI.daily_output.read_record` without rerunning
PDF capture or reopen checks. Do not create a second copy of the UI rules.

## Run from the repository root

```powershell
rtk proxy .venv-bedrock/Scripts/python.exe processes/SubjectLineBuilder/Stand-Alone/run.py
rtk proxy .venv-bedrock/Scripts/python.exe processes/SubjectLineBuilder/Stand-Alone/run.py --scenario stopped
rtk proxy .venv-bedrock/Scripts/python.exe processes/SubjectLineBuilder/Stand-Alone/run.py --scenario failure
rtk proxy .venv-bedrock/Scripts/python.exe -m unittest discover -s processes/SubjectLineBuilder/Stand-Alone -p "test_*.py" -v
```

The default is a synthetic offline controller simulation, not a simulated RRS
screen interaction. It needs no credentials or live applications.

To operate the real RRS interface:

```powershell
rtk proxy .venv-bedrock/Scripts/python.exe processes/SubjectLineBuilder/Stand-Alone/run.py --live
```

Use the full application's configured Windows environment: RRS logged in with
the intended referral at row 0, accessible PDF attachments, pywinauto/pywin32,
the existing PDF and provider-search dependencies, and configured CMS/database
access where required. Existing review dialogs remain interactive. This command
changes live RRS records when you proceed through those dialogs.

## Results and migration limits

Results have `status` (`completed`, `stopped`, `failed`) and `stage`.
The Python API also returns captured legacy `data` on normal return. The CLI
omits that data from its JSON summary; existing legacy diagnostics/dialogs may
still display referral details. Exit codes are 0 completed, 2 stopped, 1 failed.

The adapter binds the moved function to the original legacy module dictionary
with `FunctionType`, preserving helper resolution and global state for the main
workflow. This is a transitional dependency bridge, not fully isolated business
logic. Do not run concurrent sessions against the same desktop/runtime.
The controller clears stale result data at entry and converts legacy SystemExit
into a failed result, keeping `botStop=True` so downstream automation cannot run.

Verification covers unchanged moved-function AST, offline completion/stop/error
handling, shared runtime state, and the downstream boundary. Live RRS execution
has not been performed. No EXE or release is built by this extraction.
