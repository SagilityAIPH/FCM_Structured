# CMS Registration stand-alone

This is an **operator-started** step after Unity assignment and supervisor handoff, not the earlier CMS customer search in Final Code. The default runner, every scenario and the desktop without `--live` are synthetic and offline. No run automatically starts when the desktop opens.

From the repository root:

```text
.venv-bedrock/Scripts/python.exe Processes/CMS-Registration/Stand-Alone/run.py
.venv-bedrock/Scripts/python.exe Processes/CMS-Registration/Stand-Alone/run.py --scenario registered-cem
.venv-bedrock/Scripts/python.exe Processes/CMS-Registration/Stand-Alone/run.py --all-scenarios
.venv-bedrock/Scripts/python.exe Processes/CMS-Registration/Stand-Alone/run.py --self-test --report C:/Users/Administrator/AppData/Local/hermes/profiles/omniroute/cache/scratch/cms-reg/standalone-selftest.txt
.venv-bedrock/Scripts/python.exe -m unittest discover -s Processes/CMS-Registration/Stand-Alone -p "test_*.py"
```

To build only the frontend, run `npm ci` and `npm run build` in `Stand-Alone/frontend/`. Launch `run.py --desktop` for an offline synthetic operator window, or `run.py --desktop --live` for the attended adapter. The latter requires `FCM_CMS_DB_CONNECTION` (dedicated stored-procedure connection, **not** a fallback to `FCM_RRS_DB_CONNECTION`) and `FCM_CMS_REFERENCE_DIR` (controlled current reference files). Missing setting **names** are shown before starting. Sign-in is prompted within the window only after Start; the password is masked and the pair lives only in the worker's in-memory settings for that run. No credential is placed in UI state, result, scenario/report file or application logging. Avoid putting a real connection string into shell history. Optional: `[cem] cem_log_path` in `config/local_settings.ini` (beside the EXE when frozen, repo `config/` in source mode) or env `FCM_CEM_LOG_PATH` names the CEM app's daily log `FCM CEM Checher.xlsx` (absolute path); when set, the live DATA stage reads the CEM hint from that file instead of the legacy checker beside CMS.py, and an unavailable file or missing today's sheet stops at `cem_status_unknown` for an explicit Yes/No. The desktop passes nothing extra: the adapter reads the setting itself. Details: [Deploy-Ready README](../Deploy-Ready/README.md#cem-routing-hint-fcm-11-126).

The UI shows idle form → running stage/step progress → blocking case/data review with Approve or Cancel → distinct completed/stopped/cancelled/failed result. Ambiguous or unconfirmed cases list candidates; **Use this case** fills the CMS case ID for a *separate* operator Start, never launches automation. Live notify/confirm prompts block for operator acknowledgement. Do not close the window mid-run. Any partially completed live portal changes require manual inspection.

`--self-test` runs the 14 offline JSON scenarios and bridge smoke, writing a plain UTF-8 report; exit 0 requires every fixture's expected outcome/reason and smoke checks to pass. It does not prove the stored procedure schema, real CMS/Unity/RRS state, IE-in-Edge compatibility, portal persistence, CEM correctness, reference workbook versions or live registration. The packaged spec and `build.ps1` have been exercised offline: the build compiles the frontend in place, packages `dist/CMSRegistration.exe`, runs the frozen synthetic self-test, and writes `dist/CMSRegistration.exe.sha256`. The build defaults its report to the profile scratch directory; pass `-ReportPath` with a native absolute path to choose another. The spec does not embed restricted reference workbooks. The v1.0.0 binary passed packaged synthetic self-test in-repo and outside-repo; live deployment approval and portal validation remain pending.
