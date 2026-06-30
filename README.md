[ERROR] Message: Unable to obtain driver for internet explorer; For documentation on this error, please visit: https://www.selenium.dev/documentation/webdriver/troubleshooting/errors/driver_location
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


## Local Path Settings

Copy `config/local_settings.example.ini` to `config/local_settings.ini`, then edit `config/local_settings.ini` in Notepad to change machine-specific paths without touching Python code. Keep credentials and PHI out of this file.

Supported settings:

- `browser.edge_path`
- `browser.ie_driver_path`
- `browser.edge_driver_path`
- `folders.attachment_folder`
- `cms.login_url`
- `cms.case_search_url`

