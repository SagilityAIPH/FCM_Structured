# CEM Stand-Alone operator app — source only (phase 2a)

Starts idle. No predecessor auto-start or Final Code chaining. CLI runs are **invented synthetic data**, never portal, workbook, database, or live network calls. Completed means *request submitted*, not employer approved.

From the repository root:

```bash
.venv-bedrock/Scripts/python.exe Processes/CEM/Stand-Alone/run.py --scenario request-submitted
.venv-bedrock/Scripts/python.exe Processes/CEM/Stand-Alone/run.py --all-scenarios
.venv-bedrock/Scripts/python.exe Processes/CEM/Stand-Alone/run.py --self-test --report C:/path/to/selftest.txt
.venv-bedrock/Scripts/python.exe -m unittest discover -s Processes/CEM/Stand-Alone -p "test_*.py"
```

Build UI within `Processes/CEM/Stand-Alone/frontend`: `npm ci && npm run build`. Then `run.py --desktop` opens the offline window; `run.py --desktop --live` opens an *attended* window, but browser creation occurs only after Start and valid input/config. PyWebView/WebView2 required. `cem.spec` and `build.ps1` are future source recipes; **do not run the EXE build in phase 2a**.

## Live local settings

Use `config/local_settings.ini` relative to repository root in source mode or next to a frozen EXE in `config/`. Environment variables override INI. Keys in `[cem]`: `environment` (`FCM_CEM_ENVIRONMENT`, default `uat`; `production` must be explicit), `employer_search_url` (`FCM_CEM_EMPLOYER_SEARCH_URL`), `employer_add_url` (`FCM_CEM_EMPLOYER_ADD_URL`), `cem_log_path` (`FCM_CEM_LOG_PATH`), `allow_placeholder_address` (`FCM_CEM_ALLOW_PLACEHOLDER_ADDRESS`, default false). `[browser] edge_driver_path` (`FCM_EDGE_DRIVER_PATH` or `EDGE_DRIVER_PATH`), blank activates Selenium Manager. URLs must be HTTPS. URLs and workbook path deliberately have **no defaults**. Never commit machine-specific settings or real claims. No credentials are supplied by this app.

Live selectors in `Deploy-Ready/cem_steps.py` are **UNVERIFIED**. The bill-to code cannot be independently read back; the live adapter fails closed (`bill_to_unverified`) before operator review and Submit. An attended UAT DOM inspection must establish the selected bill-to code and verify employer search, duplicate request ledger, form fields, submit control and receipt readback. Do not assume a green synthetic run validates the portal. Even after successful review, a separate irreversible Submit confirmation is required. An uncertain submit or tracking failure must be reconciled manually, **never blindly resubmitted**. Placeholder addresses require policy authorization.
