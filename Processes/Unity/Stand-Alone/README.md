# Unity assignment — standalone CLI

Default execution is offline and uses invented records with fake claim numbers.
From the repository root, use the configured Python environment:

```bash
.venv-bedrock/Scripts/python.exe "Processes/Unity/Stand-Alone/run.py"
.venv-bedrock/Scripts/python.exe "Processes/Unity/Stand-Alone/run.py" --scenario "Processes/Unity/Stand-Alone/scenarios/icasemanager-declined.json"
.venv-bedrock/Scripts/python.exe "Processes/Unity/Stand-Alone/run.py" --all-scenarios
.venv-bedrock/Scripts/python.exe "Processes/Unity/Stand-Alone/run.py" --stage unity
.venv-bedrock/Scripts/python.exe "Processes/Unity/Stand-Alone/run.py" --stage assign
.venv-bedrock/Scripts/python.exe -m unittest discover -s Processes/Unity/Stand-Alone -p "test_*.py" -v
.venv-bedrock/Scripts/python.exe -m pytest tests/unit -q -p no:cacheprovider
```

Default fixture and controller paths resolve relative to the script. An explicit
--scenario path is relative to your current directory. No PDF needs to exist:
fixture filenames are synthetic strings returned by fakes, not files opened by
the runner. Set debugger breakpoints in ../Deploy-Ready/unity_flow.py and launch
run.py with a scenario. Examine steps, reason and error, not only terminal logs.

## Scenarios (all-stage expectations)

| File | Status / reason | What it proves |
| --- | --- | --- |
| happy-path.json | completed / empty | Full sequence and affirmative gate |
| icasemanager-declined.json | stopped / icasemanager_declined | No RRS completion after No |
| attachment-missing.json | stopped / attachment_missing | No upload without an export |
| attachment-ambiguous.json | stopped / attachment_ambiguous | No first-file guessing |
| run-unity-failed.json | failed / run_unity_failed | Tracking still attempted by default |
| record-assignment-failed.json | failed / record_assignment_failed | Tracking failure blocks gate |
| complete-assignment-failed.json | failed / complete_assignment_failed | RRS failure contained |
| run-unity-failed-no-tracking.json | failed / run_unity_failed | Explicit tracking opt-out |
| run-unity-failed-tracking-also-fails.json | failed / run_unity_failed | Original Unity failure retained |

Each JSON supplies input, attachments and icasemanager_approved. Optional
unity_error, record_error and assignment_error raise synthetic RuntimeError;
record_attempt_on_failure defaults to true. Change JSON for offline tracking
policy: CLI --record-attempt-on-failure affects only --live. --stage intentionally
changes scenario expectations; name/outcome assertions apply to default all.

Exit codes: 0 completed; 2 any stopped or failed result (including an expected
negative fixture); 1 caught input/loading errors. --all-scenarios prints fake
callback logs before the summary table and exits 2 because negative scenarios
are included. That is expected, not a test failure. unittest asserts the exact
outcomes and steps, including every fixture name, and tests SystemExit separately.

## Live path — attended and not production-certified

--live performs real portal, database and desktop actions, not a dry run. Only
run on an authorized configured Windows machine after the integration requirements
are satisfied. Example flag shape (replace placeholders only on that machine):

```bash
.venv-bedrock/Scripts/python.exe "Processes/Unity/Stand-Alone/run.py" --live --claim-number "YOUR-CLAIM" --customer "YOUR-CUSTOMER" --claimant-first "YOUR-FIRST" --claimant-last "YOUR-LAST" --record-attempt-on-failure no
```

The CLI's minimal inputs do not represent every field consumed by the large
legacy portal body. Do not regard this command as certification of full live
intake. It imports the legacy Unity module even for --stage assign. There is
no credential-entry or environment-selection implementation added here; use the
existing authorized deployment configuration and review its UAT portal target.

**Attachment trap:** clear stale exports and re-export this referral; exactly
one candidate must exist. Legacy chooses glob's first entry, not the newest,
and can upload the wrong document. Keep the folder exclusive/stable, free of
unrelated entries, and verify document identity yourself.

**Tracking trap:** default yes preserves legacy's write even when Unity raises.
Use --record-attempt-on-failure no to opt out; swallowed legacy errors still look
like normal returns and cannot activate that policy.

**Approval trap:** the prompt waits for the operator to approve in external
iCaseManager, which has no implementation here. Only then answer y/yes. n/no
returns icasemanager_declined without calling RRS completion.

Live completion cannot be trusted solely from the result: legacy_unity.main
swallows exceptions, and the RRS Unity Complete dialog handler also suppresses
errors. Offline tests verify sequencing, not authentication, portal DOM actions,
upload content, database persistence, RRS controls or external approval. Live
logs may contain claim information; do not publish them as fixture data.
