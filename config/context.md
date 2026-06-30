# FCM Intake V3 Context

## Current Goal
Clean and structure `FCM-Intake-V3` as a behavior-preserving migration of `FCM-Intake-V2`, so developers can work from a cleaner package layout without changing business logic.

## What Was Done
- Created `FCM-Intake-V3` as a separate cleaned copy; `FCM-Intake-V2` was left untouched.
- Moved app code into `src/fcm_intake/` with package folders for config, UI, runners, CMS/session helpers, workflow wrappers, automation helpers, and legacy scripts.
- Added `main.py`, `pyproject.toml`, `README.md`, `.gitignore`, and starter smoke/unit tests.
- Isolated agent-pack files under `tools/agent-pack/`.
- Added Notepad-editable local path config at `config/local_settings.ini`.
- Updated V3 path-sensitive modules to read file paths from `src/fcm_intake/config/__init__.py` instead of requiring Python code edits.

## Editable Local Settings
Developers should edit this file in Notepad for machine-specific paths:

`config/local_settings.ini`

It currently supports:
- `browser.edge_path`
- `browser.ie_driver_path`
- `browser.edge_driver_path`
- `folders.attachment_folder`
- `cms.login_url`
- `cms.case_search_url`

Credentials, PHI, screenshots, and production claim data should not be stored there.

## Guardrails
- Do not change workflow/business logic without explicit approval.
- Avoid rewriting Selenium selectors, sleeps, frame switching, CMS login/session behavior, pywinauto targeting, database logic, or claim/customer processing rules unless separately approved.
- Treat healthcare data as sensitive even if it appears synthetic.
- Keep examples and tests synthetic and masked.

## Verification Already Run
- Python syntax parse passed for all V3 Python files.
- Config smoke check passed.
- Environment override check passed.
- Dynamic legacy loader smoke check passed.
- Confirmed V3 source does not reference `FCM-Intake-V2`.
- Confirmed user-specific machine paths are no longer scattered through legacy/CMS modules.

## Known Gaps
- `pytest` was not installed in the current Python environment, so the pytest suite was not run.
- Runtime browser/CMS workflows were not manually executed.
- Legacy scripts are still behavior-sensitive and large; deeper cleanup should happen only after characterization tests exist.

## Recommended Next Step
Install dev dependencies in the V3 environment and run:

```powershell
cd C:\Users\Administrator\Desktop\Projects\FCM-Intake-V3
python -m pytest -q
```

Then launch manually with:

```powershell
python main.py
```

