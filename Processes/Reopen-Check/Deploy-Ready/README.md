# Integration

`reopen_flow.py` owns the process sequence and has no browser, database, UI or
third-party imports. `src/fcm_intake/workflows/reopen_flow.py` connects it to the
existing shared CMS session, re-open checker, customer checker and prompts.
`legacy_fcm.py` now calls this adapter instead of embedding the process.

```python
from fcm_intake.workflows.reopen_flow import run_live

result = run_live(data, app=app, notify=notify, stage="all")
if result["status"] == "completed":
    data["customer"] = result["customer"]
```

Inputs use the existing intake keys: `claimNumber`, `customer`, `claimID`,
`claimantFull`, and `referralType`. Re-open only requires `claimNumber`; provide
customer and referralType as well to exercise the tire-customer rule. Customer
only requires customer, claimID and claimantFull.

Results include `status` (completed/stopped), `reason`, `customer`, `cases`, and
`steps`. Stopped is a business outcome, not an exception. Technical failures
raise and must not be treated as permission to continue.

Deploy the repository's `src`, `config`, and `Processes/Reopen-Check/Deploy-Ready`
together. A future frozen intake build must bundle the controller at this same
relative location. The separate AI Bedrock executable does not run this flow.
Live operation needs the existing Windows browser automation dependencies,
Edge IE mode, IEDriverServer, CMS credentials and database access. The caller
owns the shared browser session; the integration adapter does not close it.
