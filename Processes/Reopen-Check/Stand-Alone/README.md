# CMSCustomerSearch — standalone desktop and CLI

The desktop application is named **CMSCustomerSearch**. It runs the existing
re-open/customer flow; the `Reopen-Check` folder name remains for compatibility
with the main app and existing commands.

## Windows desktop application

Open `dist/CMSCustomerSearch.exe` from the repository build output, or run
`CMSCustomerSearch.py` with the configured Python environment. Python is bundled
in the EXE. No console window is required.

1. Choose **Offline scenario** or **Live CMS**, and select both stages, re-open
   only, or customer only. Offline mode uses the selected synthetic scenario
   and ignores workbook/manual inputs; it does not connect to CMS.
2. For live input, choose a daily Excel workbook and Record ID, or select
   **Use manual input** and enter the required process fields. Excel fields are
   read-only in this form. The app shows recalculated completeness and rechecks
   the record immediately before a live run.
3. Enter CMS username/password for live runs, then select **Run selected process**.
   Live prompts open as dialogs. The application remains responsive while the
   process runs in an isolated worker. Finish its prompts before closing the app.
4. Review the result and optionally save it as JSON. The app does not modify the
   source workbook or process every row automatically. Credentials are not saved
   in result files or configuration.

The EXE bundles Selenium, IEDriverServer 4.14.0 and Selenium Manager. No separate
Python or Selenium installation is needed. The default IE driver path resolves
inside the EXE bundle. For the separate Chromium Edge workflow used by CEM,
Selenium Manager selects/downloads a driver matching the installed Edge version;
its first run needs internet access unless a compatible driver is already cached.
For offline/restricted machines, supply `FCM_EDGE_DRIVER_PATH` or an INI path to
a matching `msedgedriver.exe`.

Live requirements: installed Microsoft Edge with IE mode,
network access to CMS, and the SQL Server ODBC driver/database access for case
validation. Microsoft Edge, the SQL Server ODBC driver and credentials are not bundled.

Put `config/local_settings.ini` beside the EXE (copy the repository's
`config/local_settings.example.ini` and enter machine paths). Omit or leave blank
the driver path settings to use the bundled IE driver and automatic Edge management.
Remove any old placeholder paths: explicit INI/environment settings take precedence.
Existing environment
overrides still apply. Set `FCM_CMS_DB_CONNECTION` and `FCM_RRS_DB_CONNECTION` for
database access, and optionally `FCM_CMS_USERNAME` / `FCM_CMS_PASSWORD` for login.
Do not put passwords in the INI file.

Build and offline packaged smoke test from the repository root:

```powershell
rtk proxy .venv-bedrock/Scripts/python.exe -m pip install -r Processes/Reopen-Check/Stand-Alone/requirements-build.txt
rtk proxy .venv-bedrock/Scripts/python.exe Processes/Reopen-Check/Stand-Alone/prepare_drivers.py
rtk proxy .venv-bedrock/Scripts/python.exe -m PyInstaller --noconfirm Processes/Reopen-Check/Stand-Alone/CMSCustomerSearch.spec
rtk proxy .venv-bedrock/Scripts/python.exe Processes/Reopen-Check/Stand-Alone/smoke_exe.py
```

The EXE bundles the shared controller, synthetic scenarios and required legacy
sources. It resolves code from the bundle but reads machine settings beside
the EXE. The smoke test launches from outside the repository, exercises Excel
input and the worker, and checks both completion and stop outcomes. CEM source
is checked without importing it because its legacy import opens a browser.
The packaged test also imports Selenium, executes Selenium Manager and starts
the bundled IE driver service without opening a browser or contacting CMS.
The build downloads the official Selenium driver archive and verifies its pinned
SHA-256 checksum. Live CMS behavior requires separate verification on a configured machine.

### Browser stays on localhost

Localhost is IEDriver's bootstrap page, not the CMS server. A 120-second HTTP
read timeout against localhost means a WebDriver command did not respond.
Startup uses IEDriver's original local bootstrap page before navigating to the CMS login URL,
requests a 30-second browser-attach timeout and a 45-second page-load timeout,
and reports stages in the desktop status/result box. Error results include the
last stage so attachment failures can be distinguished from navigation/login failures.

If attachment still fails, verify CMS opens manually in Edge IE mode, browser
zoom is 100%, and ask IT to check IE-mode policies and consistent Windows Internet
Options Protected Mode settings. Do not disable security protections merely to
remove the warning banner. The `--ie-mode-force` warning itself is separate from
the connection timeout; CMS requires IE mode.

### CMS certificate warning

The shared browser session uses `pywinauto.Desktop(backend="uia")` to click
**More information** when CMS displays **This site is not secure**. It selects
only a uniquely identified new browser window and verifies the CMS hostname in
its address bar before clicking. Existing/unrelated browser windows are untouched.
If Edge reuses a window or multiple new windows prevent a unique match, the app
reports that the window could not be identified instead of guessing.

This action expands certificate details; it does not click Continue or bypass
certificate validation. The process reports a certificate-specific error before
typing credentials when the warning is detected. The underlying certificate/trust
problem must still be resolved. The helper also checks for the warning following
a navigation error, so it is not misreported as an ordinary page-load timeout.

The main FCM runner now passes its CMS credentials to the same shared session,
matching the standalone setup. Browser creation remains deferred until needed.

## Input from the AI reader's daily workbook

Choose a Record ID from the workbook's `Referrals` sheet:

```powershell
rtk proxy python run.py --excel "C:\path\AI-FCM-Output-2026-09-29.xlsx" --record-id "RECORD-ID"
rtk proxy python run.py --live --stage reopen --excel "C:\path\AI-FCM-Output-2026-09-29.xlsx" --record-id "RECORD-ID"
```

Without `--live`, this only previews the selected row's mapped input and its
recalculated completeness; no CMS session opens. With `--live`, a Passed record
is required. Failed rows remain available for review in the workbook. Excel
input cannot be combined with direct claim/customer arguments.

Mapping: Claim Number -> claimNumber, Employer Name -> customer, Claim ID ->
claimID, First Name + Last Name -> claimantFull, Referral Type -> referralType.
The shared reader in `AI/daily_output.py` preserves the provider records for
future standalone processes too. The runner does not edit the daily workbook
or automatically process all rows.

## Scenario and direct-input modes

From this folder, run the offline example or tests:

```powershell
rtk proxy python run.py
rtk proxy python run.py --stage reopen
rtk proxy python run.py --stage customer
rtk proxy python run.py --scenario scenarios/no-cases.json
rtk proxy python run.py --scenario scenarios/decline.json
rtk proxy python -m unittest discover -s . -p "test_*.py" -v
```

Offline scenarios supply synthetic case-search and customer-check results.
They exercise the real controller but do not verify Selenium, SQL, matching
accuracy or CEM. Edit/copy a scenario to reproduce a decision path. In your
debugger, launch `run.py` and set breakpoints in
`../Deploy-Ready/reopen_flow.py`. All paths resolve relative to the script, so
you can also invoke it by its full path from any working directory.

To use real CMS, run with the project's configured Python environment:

```powershell
rtk proxy python run.py --live --stage reopen --claim-number "YOUR-CLAIM"
rtk proxy python run.py --live --stage customer --customer "YOUR-CUSTOMER" --claim-id "YOUR-ID" --claimant "YOUR-CLAIMANT"
rtk proxy python run.py --live --claim-number "YOUR-CLAIM" --customer "YOUR-CUSTOMER" --claim-id "YOUR-ID" --claimant "YOUR-CLAIMANT" --referral-type "Full Case Management"
```

The live runner prompts for CMS username/password (password is hidden), or
reads `FCM_CMS_USERNAME` and `FCM_CMS_PASSWORD`. Configure browser paths and CMS
URLs using the existing `config/local_settings.ini` or supported environment
variables. Set `FCM_CMS_DB_CONNECTION` and `FCM_RRS_DB_CONNECTION` to valid ODBC
connection strings for database validation; otherwise the existing legacy
connection defaults are used (their passwords are blank). Database validation
failures stop the process rather than being interpreted as no matching cases. Live customer
validation can enter the existing CEM workflow after your confirmation; it is
not an offline simulation. The runner closes its CMS session on exit.

Exit codes: `0` completed; `2` stopped by a business decision, cancellation or
CEM handoff; `1` invalid input or technical failure. Result output may contain
claim information in live mode; no result files are saved automatically.
