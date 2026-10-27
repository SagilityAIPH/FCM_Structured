# CMS Registration investigation

**Status:** Phase 0 documentation and interface scaffold; source design only. No live CMS, Unity, RRS, database, workbook contents, or referral tested. Recall from [[INSTRUCTIONS]] under the CMS Registration module section (FCM-1.1-97–105).

## Purpose and boundary

Modularise legacy `src/fcm_intake/legacy/CMS.py`'s `run_case` → `searchCase` → RRS Complete Registration as the process **after Unity**. Conclusion **B: sequential but decoupled**. Unity's case, attachments and transferred fields must exist, but its code does not launch registration (`Processes/Unity/Deploy-Ready/unity_flow.py:88-127`; `src/fcm_intake/legacy/CMS.py:2128-2167`). BRD slides 94–101 describe the handoff: Unity completion/assignment and acceptance, then supervisor assignment to a registration agent (slide 101), before that agent works the CMS case. The operator starts one standalone registration run per claim **after** that assignment, rather than chaining immediately to the Unity browser or Final Code's earlier CMS customer-search stage. See [[W1-unity-cms-connection]].

## Confirmed legacy defects

1. **Case selection disabled:** 141 of 153 lines of `CMS.py:996-1148` are commented out. The search supplies case/claim, but no executable latest-assigned-case selection or Medical/Vocational type verification remains (BRD 102–103). This is separate from Unity's date-only `CheckCaseUnity` lookup (`CMS.py:2024-2086`).
2. **RRS Case Id never entered on option 3:** `caseID` is declared global (`CMS.py:952`) but its assignments in the selection block are commented out (`CMS.py:1002-1140`). The RRS `Case Id` prompt uses that unset name, not `caseIDSelect`, and suppresses the resulting error (`CMS.py:1885-1897`). No successful Case Id entry or readback is established.
3. **Provider branch reversed against BRD 113:** provider search/Add executes only when no provider row exists (`CMS.py:1524-1558`); the slide says leave prepopulated provider and add additional providers where needed. No additional-provider path exists once a row is present.

## BRD 102–123 coverage

Status is for the slide as a whole, relative to executable `CMS.py`; prepopulation or other-system actions have not been live verified. Detailed per-slide evidence: [[W2-cms-registration-map]] §3; BRD source: [[brd/10-cms-case-setup]] and [[brd/11-complete-registration]].

| Slide | Status | Evidence |
| --- | --- | --- |
| 102 | Partial | Date-only Unity lookup; CMS case selection disabled (`CMS.py:1002-1140,2024-2086`). |
| 103 | Contradicts | No active CMS Select Case (`CMS.py:996-1000,1121-1148`). |
| 104 | Partial | Office matrix/adjuster address only (`CMS.py:1214-1279`). |
| 105 | Partial | Single diagnosis/body-part additions; other checks absent (`CMS.py:1150-1211`). |
| 106 | Missing, out of scope | Claimant click only; BRD special path marked out of scope (`CMS.py:1281-1287`). |
| 107 | Implemented ordinary case; special path excluded | Claimant tab left unchanged; prepopulation not verified (`CMS.py:1281-1287`). |
| 108 | Partial | Medical mapping only, no branch fallback (`CMS.py:1295-1296,1327-1383`). |
| 109 | Partial | Inventory/referral source set; dates and flags not verified (`CMS.py:1300-1323`). |
| 110 | Missing CMS write; partial assumption | Appointment and identifier writes commented out (`CMS.py:1315-1323`). |
| 111 | Partial | Missing employer searched; C02283 not explicitly selected (`CMS.py:1407-1446,1485-1519`). |
| 112 | Partial | Matrix Bill To location used without employer-specific policy (`CMS.py:1485-1519`). |
| 113 | Contradicts | Search/Add only if no provider row (`CMS.py:1533-1558`). |
| 114 | Partial | Four-character search and manual choice; retries/add-new absent (`CMS.py:1536-1558`). |
| 115 | Partial, potentially contradicts | Attorney branch polarity not established (`CMS.py:1619-1687`). |
| 116 | Partial | Name lookup omits phone and prescribed three-letter limit (`CMS.py:1625-1674`). |
| 117 | Partial | First matching sender, no date check (`CMS.py:1750-1772`). |
| 118 | Missing verification | Other Notes never opened (`CMS.py:1738-1782`). |
| 119 | Partial | Configures found CPD ERFS; no explicit additional creation (`CMS.py:1806-1841`). |
| 120 | Partial | Option 3 without tab-completion gate; Case Id error swallowed (`CMS.py:1858-1897`). |
| 121 | Not evidenced, external | Outlook draft not detected (`CMS.py:1860-1903`). |
| 122 | Partial | Option 10 based on daily workbook, not verified CEM request/CMU (`CMS.py:1858-1883,1937-1965`). |
| 123 | Not evidenced, external | No Outlook/CMU readback (`CMS.py:1872-1903`). |

## Data provenance and approved design

- **Primary parity source:** caller-supplied connection to `RRS_Sagility_Details_Lookup(?,?,?)` using claimant, claim and market. Legacy reads 31 named columns into `CaseData`; this is not a proven exhaustive stored-procedure schema. `CMS.py:112-278`; field provenance and canonical/Unity/JSON distinctions: [[W3-cms-registration-data-and-module]].
- **Two static reference workbooks:** `Liberty Mutual Claims Office Matrix_08-29-19.xlsx` (dated 2019; physical/mailing adjuster and Bill To location), and `Liberty Mutual Medical Dedicated Supervisor Mapping 04-07-2025.xlsx` (not found in repository; prefix mapping). Both are read by bare relative path (`CMS.py:40,790-814,1214-1217,1295-1296,1327-1369`). No contents inspected.
- **Daily CEM workbook:** `FCM CEM Checher.xlsx`, date-named sheet, exact claimant/claim membership selects option 10 rather than 3 (`CMS.py:1915-1965`). Its membership is not proof of a CEM employer request or CMU status.
- **Portal-only state:** live CMS case/referral type/assignment, supervisor/employer/provider/attorney, attachments, Other Notes/letters, and selected RRS work row and registration readback must be verified at runtime (`CMS.py:1295-1444,1524-1841,1843-1897`). Local referral JSON `record_id` is not a CMS case ID.

**Owner-approved direction:** Create `Processes/CMS-Registration/` with `Deploy-Ready/` and `Stand-Alone/`, following Unity's pattern. Start operator-controlled per claim after registration-agent assignment; use the stored procedure first for parity. Fix each of the three confirmed defects in the **new module** as separate backlog items. Leave `CMS.py` unedited because another contributor is changing its Unity lookup; import reusable helpers and reimplement the step sequence. Tell that contributor about the boundary. No live test or release until owner signal.

**Module layout:** `Deploy-Ready/contract.py` shared immutable request/candidate/result/stage interface; Phase 1 `cms_registration_flow.py` pure controller and `cms_steps.py` live-stage factory (reuse legacy helpers, not monolithic `run_case`/`searchCase`); Phase 2 `Stand-Alone/` operator launcher, synthetic scenarios/tests, desktop review, packaging and offline self-test. `START → CASE → DATA → REVIEW → CMS_SETUP → COMPLETE_REG`; stop on identity ambiguity/cancellation/step failure. Phase 0 contract is uncommitted by design. Phase 1/2 code, UI and live wiring are not yet implemented.

## Owner / IT inputs still needed

1. Current, authorized Dedicated Supervisor Mapping and Claims Office Matrix versions, provenance and deployable path; define absent/stale-reference behavior.
2. Which setting/approved secret channel supplies the CMS stored-procedure connection; is it the same database as Unity's `FCM_RRS_DB_CONNECTION` tracking connection? Do not assume equivalence or store secrets in docs.
3. UAT versus production environment and scope for any owner-approved live test; no live execution implied here.
4. Bill To employer-specific and C02283 selection rules, including employer location/contact and CEM exceptions.
5. Provider/Attorney entry and identity/ambiguity rules, including additional providers and missing records.

**Investigation notes:** [[W1-unity-cms-connection]] · [[W2-cms-registration-map]] · [[W3-cms-registration-data-and-module]]. Static code/BRD evidence, not proof of portal persistence.
