# Run and debug this process only

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
