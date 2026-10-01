# FCM Intake V3

FCM Intake V3 is a structured, behavior-preserving migration of the V2 Windows automation app.

## Project context for future sessions

This is an existing, large Windows automation project. Running the entire
workflow end to end for every bug fix or new feature takes too much time.
The owner's ongoing goal is to break the workflow into business processes,
test and debug each independently, then reconnect the tested processes into
the main application.

Future AI sessions and contributors should read this context and the progress
table first, then inspect the relevant process README and current code before
making changes. Continue the modularization incrementally, one process at a
time. Avoid a wholesale rewrite or separate standalone copies of production
logic. A process must use the same tested implementation when run alone and
when called by the complete workflow.

Define clear inputs and outputs so a process can be exercised without running
every preceding step. The daily AI Excel workbook provides reusable extracted
input for downstream processes: testing Reopen-Check should not require another
PDF upload or Bedrock call. Its standalone runner already accepts a workbook
and Record ID; future processes should reuse the shared workbook reader.

Separate business decisions from browser automation, database access and UI
prompts incrementally. For a bug or feature, test the affected process first,
then its integration points. Retain targeted end-to-end checks to verify the
combined workflow. Offline tests verify decisions and data handling; they do
not establish that live CMS or Bedrock behavior has been validated.

Reopen-Check is the first extracted controller and is connected to the main
app. Its underlying CMS search, database eligibility, customer matching and
CEM implementations still rely on shared legacy code. Treat this as a starting
point for further separation, not completed modularization of those dependencies.

## Ongoing task: modularize the codebase

Use this structure for each process:

```text
Processes/
  <Process-Name>/
    README.md
    Deploy-Ready/        Shared process implementation used by the main app
    Stand-Alone/         Independent runner, offline scenarios and process tests
```

`Deploy-Ready` and `Stand-Alone` must use the same process implementation.
Keep application integration adapters thin, reuse shared browser sessions and
configuration, and document dependencies that still live elsewhere in the
repository. The folder name `Deploy-Ready` does not mean live validation or
executable packaging has already been completed.

For each process:

1. Map the existing steps, inputs, outputs, decisions and dependencies.
2. Extract the controller into its process folder, preserving existing business
   rules unless a change is explicitly requested. Document any intentional
   behavior fixes separately from the structural refactor.
3. Connect the main app and standalone runner to that shared implementation.
4. Provide offline scenarios and tests for completion, cancellation, handoffs
   and failures. Support individual stages where useful.
5. Document run/debug commands, live configuration, verification results and
   remaining work. Update the progress table below with each completed change.

### Progress

| Process | Modularization status | Verification | Remaining work |
| --- | --- | --- | --- |
| [Reopen-Check and customer validation](Processes/Reopen-Check/README.md) | Shared controller extracted; main app integrated; CMSCustomerSearch desktop EXE and CLI support both stages or either individually, plus daily Excel input by Record ID | Last recorded checks: 12 process tests, 37 repository tests, and packaged desktop smoke test passed | Live CMS verification; browser search, database eligibility, customer matching and CEM still use shared legacy implementations |
| Other intake processes | Not yet migrated to this folder structure | Not assessed for modularization | Identify and extract the next process |

Keep this table current as processes are migrated; distinguish offline tests
from live verification. Continue with the process selected by the user, using
the same folder structure and recording any remaining legacy dependencies.

## Run

```powershell
python -m fcm_intake
```

For direct local execution without installing the package:

```powershell
rtk proxy python main.py
```

## Layout

- `src/fcm_intake/app.py`: CustomTkinter desktop UI.
- `src/fcm_intake/config.py`: configuration defaults and local settings loader.
- `src/fcm_intake/legacy_loader.py`: dynamic loader for legacy scripts.
- `src/fcm_intake/runners/`: thin orchestration layer between UI and workflows.
- `src/fcm_intake/cms/`: shared CMS browser/session helpers.
- `src/fcm_intake/workflows/`: compatibility wrappers around legacy workflow scripts.
- `src/fcm_intake/legacy/`: V2 automation scripts preserved for behavior compatibility.
- `Processes/`: modular processes with `Deploy-Ready` and `Stand-Alone` folders.
- `tools/agent-pack/`: agent tooling isolated from the FCM app code.

The four modules directly under `src/` (`CMS.py`, `edge_auto.py`,
`CustomerCheckerV2_shared.py`, and `ReOpenCheck_shared.py`) support imports
still used by the legacy scripts. Keep these until those imports are migrated.
Python installation metadata (`*.egg-info/`) is generated locally and is not
source code.

## Modular process debugging

The [re-open/customer process](Processes/Reopen-Check/README.md) has a shared
`Deploy-Ready` controller and a `Stand-Alone` runner. Run it independently from
the intake UI, with offline fixtures or a configured live CMS session:

```powershell
rtk proxy python Processes/Reopen-Check/Stand-Alone/run.py
rtk proxy python Processes/Reopen-Check/Stand-Alone/run.py --stage reopen
rtk proxy python -m unittest discover -s Processes/Reopen-Check/Stand-Alone -p "test_*.py" -v
```

See the [standalone instructions](Processes/Reopen-Check/Stand-Alone/README.md)
for customer-only runs, debugging, live inputs and connection settings.

For a desktop form, use `dist/CMSCustomerSearch.exe`. It is the standalone
Reopen-Check/customer process with daily Excel selection, manual input and
offline/live modes. Its shared source remains in `Processes/Reopen-Check`.
See [desktop setup and build instructions](Processes/Reopen-Check/Stand-Alone/README.md#windows-desktop-application).

## Configuration

Current V2 defaults are preserved. These environment variables can override local machine settings:

- `FCM_CMS_LOGIN_URL`
- `FCM_IE_DRIVER_PATH`

Do not commit real credentials, PHI, screenshots, or production claim data.

## AI sample regression workflow

The Bedrock extractor follows the PDF table's section order and Special
Instructions fallback rules. NEXT STEP shows Passed when all non-optional
fields and at least one complete provider record are present; otherwise it
shows Failed and lists missing fields. Optional gaps do not fail the referral.
See [field priorities and output formats](AI/README-exe.md#section-priority-and-next-step).

The October 2026 matrix adds separate doctor names, provider address lines,
compensable body parts, employer contacts, language and Special Instructions text
(58 matrix field rows, 61 canonical keys including supplemental data). Provider,
attorney and employer details prioritize Special Instructions. Appointment date
is required; time is optional (Date Only). Past, weekend and U.S. federal/observed
holiday appointments remain Failed until the runner confirms them. Workbook
schema 2 preserves these confirmations; use the matching CMSCustomerSearch build.

Customer Contact Name, Customer Contact Phone Number and Diagnosis Code are
optional. Reader UIs automatically append every completed extraction, including
Passed/Failed status, to one daily Excel workbook in `Output/AI` (beside the EXE
for packaged runs). Use `FCM_AI_OUTPUT_DIR` to choose a shared folder. Standalone
Reopen-Check accepts a workbook and Record ID as input; future standalone
processes should reuse the reader in `AI/daily_output.py`. See
[daily workbook details](AI/README-exe.md#daily-excel-output-and-standalone-input).

The reader also supports on-demand U.S. Census lookup of incomplete claimant,
provider and attorney addresses. Suggestions require review before updating
fields, NEXT STEP and the same daily Excel record. Existing values are preserved;
unresolvable street/unit gaps remain missing. Accepted changes keep their source
and original values in exports. See [address review](AI/README-exe.md#missing-address-lookup-and-review).

For a native Windows app without Streamlit, use `dist/AI-FCM-Bedrock-Runtime.exe`.
See [desktop EXE instructions](AI/README-exe.md) for building, testing, and use.

The PDFs in `Samples for AI/` can be scanned and batch-tested without importing
the Streamlit UI. Sample inputs and derived results are gitignored because they
can contain PHI.

```powershell
# Install the optional AI runtime once
python -m pip install -e ".[ai]"

# Local text-readability check; does not call Bedrock
python AI/batch_samples.py scan

# Run all samples with the normal AWS credential chain, or with
# AWS_BEARER_TOKEN_BEDROCK set in the environment
python AI/batch_samples.py run

# Export predictions for correction, then mark reviewed=yes in the CSV
python AI/batch_samples.py export-review
python AI/batch_samples.py score
```

Runs are resumable: successful document IDs already present in
`AI/.sample_runs/results.jsonl` with the current fields and prompt fingerprint
are skipped. Changed extraction rules cause old samples to run again. The score report provides overall
and per-field exact-match accuracy so prompt and validation changes can be
measured against reviewed examples.


## Local Path Settings

Copy `config/local_settings.example.ini` to `config/local_settings.ini`, then edit `config/local_settings.ini` in Notepad to change machine-specific paths without touching Python code. Keep credentials and PHI out of this file.

Supported settings:

- `browser.edge_path`
- `browser.ie_driver_path`
- `browser.edge_driver_path`
- `folders.attachment_folder`
- `cms.login_url`
- `cms.case_search_url`

