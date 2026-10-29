---
tags: [cem, investigation, module, employer-request-add]
sources: [src/fcm_intake/legacy/legacy_cem.py, src/fcm_intake/legacy/legacy_customerchecker.py, src/fcm_intake/legacy/CMS.py, Processes/Reopen-Check/Deploy-Ready/reopen_flow.py, Processes/CMS-Registration/Deploy-Ready/cms_steps.py, Processes/CMS-Registration/Deploy-Ready/cms_registration_flow.py, "Final Code/finalcode/orchestrator.py", docs/brd/03-cms-reopen-and-customer-search.md, docs/brd/11-complete-registration.md]
verified_at: 9774a34 (2026-10-30)
---
# CEM (Employer Request Add) investigation

**Status:** Phase 0: investigation and owner decisions recorded. Nothing has been built yet; no live CEM, CMS, RRS or CMU system was touched. Backlog: [[INSTRUCTIONS]] → *CEM module* (FCM-1.1-124 to 130). Detailed reports: [[cem/W1-cem-code]] (legacy code, file:line) and [[cem/W2-cem-process-design]] (BRD position and proposed boundary). Where those reports differ from the owner decisions below, this note wins.

## Purpose and boundary

CEM is the **Employer Request Add** step: when CMS Customer Search finds no verified employer, a request is raised in the CEM portal so the CMU team can add the employer. The goal is a modular process `Processes/CEM/` with `Deploy-Ready/` + `Stand-Alone/`, following [[code/cms-registration]].

**In scope:** a new-employer request: search CEM, review, submit, confirm the request exists, then log it.
**Out of scope:** the CMU/Data Control approval itself, CMS Customer Search, Subject Line Builder employer typing, Unity employer selection, CMS case setup, RRS option 10/3 (CMS Registration owns it), and Outlook sending.

## What the code does today

| Step | Evidence |
| --- | --- |
| CMS Customer Search fails to resolve the employer, and the operator answers **Yes** to "Do you need to complete CEM?" | `legacy_customerchecker.py:743-755` |
| `legacy_cem.main(CustomerName, ClaimID, ClaimantName)` runs. **Loading the file opens a separate Edge browser** (not the CMS IE-mode session) | `legacy_cem.py:14-20,274-281` |
| Employer search on the CEM portal. The inline target is **UAT** | `legacy_cem.py:51-68` |
| No results table → Add Employer: name, a fixed bill-to customer `Liberty Mutual Commercial Market (C02283)`, and placeholder `Unknown` address values when there is no address | `legacy_cem.py:71-117` |
| A popup tells the operator to check the form and **click Submit by hand**. The code never clicks Submit or checks the result | `legacy_cem.py:119` |
| A row goes into the daily workbook `FCM CEM Checher.xlsx` (sheet `MMDDYYYY`; columns Claimant, Claim ID, Status) | `legacy_cem.py:120,289-409` |
| Customer Search returns nothing, Reopen-Check stops with `customer_unresolved_or_cem`, and Final Code stops before the Subject Line Builder | `reopen_flow.py:49-56`; `orchestrator.py:98-122` |
| Later, CMS Registration reads the workbook: if the row exists, RRS Complete Registration uses **option 10** (CMU); otherwise **option 3** | `CMS.py:1858-1883,1915-1965`; `cms_steps.py:815-842` |

## Confirmed legacy defects

1. **The log row is written without a verified submission.** It's written as soon as the operator closes the popup, even if Submit was never clicked. Status is always blank, and no request reference is captured (`legacy_cem.py:119-120`).
2. **Writer and reader use different keys.** CEM writes the PDF **Claim ID** into column B, but CMS Registration compares column B with the **claim number** (`CMS.py:1858`, `claim_exists(claimant_name, claim_number)`). Unless the two values are equal, a real CEM request never switches registration to option 10.
3. Errors are printed and swallowed, and `main` always returns `None` (`legacy_cem.py:274-281`).
4. The browser is created when the file is imported, and certificate checks are weakened (`legacy_cem.py:14-20`).
5. A table with no matching employer falls through silently, and the location branch has invalid selectors and never saves (`legacy_cem.py:121-159`). `custSearch` is never called. Neither is reusable as-is.
6. There are no behavioural tests of legacy CEM.

## Owner decisions (2026-10-30)

| Question | Decision |
| --- | --- |
| Who clicks Submit in CEM? | **The bot**, after an operator review **and** an explicit, separate submit confirmation |
| Default environment | **UAT**, as the legacy code does; testing only. Production needs a separate decision (FCM-1.1-130) |
| Scope of version 1 | **New employer request only.** The previous developer confirmed there is no employer linking or address add |
| How it starts | A **separate app** the operator starts after Customer Search stops. It never starts automatically, and nothing calls it in a chain |
| CEM log key | Record **both**: column B = **claim number** (what CMS Registration already reads) plus a new **Claim ID** column |

## Planned module (not built)

- **Stages:** START → VERIFY_SOURCE → SEARCH → REVIEW → SUBMIT → VERIFY_RECEIPT → TRACK.
- **Gates:**
  - The app opens idle and needs an explicit **Start**. Double starts are rejected.
  - Input is validated before any browser work: employer name (never `Not found` / `Not Given/Not Applicable`), claimant, claim number and Claim ID.
  - CEM search runs first. An existing employer or an ambiguous match is a stop, never a new request.
  - Operator review, then a separate irreversible-submit confirmation.
  - One bot submit, then readback of the request in the portal.
  - The log row is written **only after** readback.
  - An uncertain submit result is a stop, with no automatic retry, so a request is never sent twice.
- **Outcomes:** `completed` / `stopped` / `cancelled` / `failed`, with `reason`, `stage`, `stages`, `steps`, `request_status` and `tracking_status`, plus a sanitized `error`. `completed` means *request submitted*, not *employer approved*.
- **Layout:**
  - `Deploy-Ready/`: `contract.py`, `cem_flow.py` (pure controller), `cem_rules.py`, and `cem_steps.py` (lazy Edge adapter with an injected driver; it doesn't import `legacy_cem`).
  - `Stand-Alone/`: runner, desktop app, synthetic scenarios, `--self-test` and EXE.
- `legacy_cem.py` stays unedited as the reference.

## Open BA questions

- **FCM-1.1-128:** Are placeholder `Unknown` address values allowed in a new-employer request, or must the operator supply the address from the referral?
- **FCM-1.1-129:** After a request is **submitted** but not yet approved, does the referral continue with a placeholder employer (BRD 31/57), or wait for CMU approval?

## Related

[[code/cms-customer-search]] · [[code/cms-registration]] · [[code/legacy-code]] · [[brd/03-cms-reopen-and-customer-search]] · [[brd/11-complete-registration]] · parked [[process-wizard/W1-employer-and-cem]] (recall "JARVIS"; reference only)
