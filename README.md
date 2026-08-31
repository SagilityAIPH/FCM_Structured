# FCM Intake V3

FCM Intake V3 is a structured, behavior-preserving migration of the V2 Windows automation app.

## Run

```powershell
python -m fcm_intake
```

For direct local execution without installing the package:`r`n`r`n```powershell`r`npython main.py`r`n```

## Layout

- `src/fcm_intake/app.py`: CustomTkinter desktop UI.
- `src/fcm_intake/runners/`: thin orchestration layer between UI and workflows.
- `src/fcm_intake/cms/`: shared CMS browser/session helpers.
- `src/fcm_intake/workflows/`: compatibility wrappers around legacy workflow scripts.
- `src/fcm_intake/legacy/`: V2 automation scripts preserved for behavior compatibility.
- `tools/agent-pack/`: agent tooling isolated from the FCM app code.

## Configuration

Current V2 defaults are preserved. These environment variables can override local machine settings:

- `FCM_CMS_LOGIN_URL`
- `FCM_IE_DRIVER_PATH`

Do not commit real credentials, PHI, screenshots, or production claim data.

## AI sample regression workflow

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
`AI/.sample_runs/results.jsonl` are skipped. The score report provides overall
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

