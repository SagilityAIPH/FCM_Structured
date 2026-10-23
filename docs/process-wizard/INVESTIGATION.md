No code has been changed by this investigation.

# Process Wizard investigation

## Status

**PARKED -- resume when the owner says 'JARVIS'.** Investigation only; Wizard authority to flag, pause or correct is deferred by rule.

## Purpose

Investigate a new AI call, the Process Wizard, to check business criteria at FIRST, MID or LAST points in a process. This source-level review covers the eight Liberty Mutual (customer C02283) rules marked Start on the Liberty Mutual sheet of the owner's Intake Rules workbook: rows 8, 9, 17, 29, 33, 34, 35 and 37. The Standard Intake Process sheet has no Start rows. Scope included Final Code, standalone Unity, Subject Line Builder, Reopen-Check, shared AI and legacy `src/`. No live referral or portal behavior was validated.

## Source documents

- `Desktop/Projects/FCM Documentation/Intake Rules.xlsx` — owner-provided business rules; a plaintext login exists in a non-Start row and has been flagged to the owner. No credential is reproduced here.
- `Desktop/Projects/CEM.docx` — Genex CEM portal guide for searching, adding and modifying Customers and Employers. Data Control reviews requests; the customer must be in CMS before a new employer can be requested/linked.

## Owner decisions so far

- Search everything, including legacy code.
- R37 applies **only** to Liberty Mutual referrals whose employer is Goodyear (E11483) or Cooper Tire & Rubber (E12449).
- For R35, live RRS/Unity dropdown labels are authoritative, and AI must reason contextually when a facility does not appear verbatim.
- Wizard authority (flag, pause or correct) varies by rule and is deferred. CEM's role was parked pending an existence check; that check is answered below.

## The 8 rules

- **R8 — Claim number:** `WC###A#####` or `WC########`; use other formats as printed on RFS/FROI, and do not add `WC` if a previous RGC is noted.
- **R9 — SSN:** On iCase referrals, partial or missing SSN stays blank for a new claimant profile; leave an existing claimant's SSN as is. Never enter the prohibited all-nines placeholder.
- **R17 — Comcast:** Select Comcast Cablevision (E05408).
- **R29 — Direct GAA FCM request:** A direct request for the named GAA FCM is not allowed. Obtain an alternate from the local branch and Liberty Mutual's permission; if refused, decline because the nurse is unavailable and remove the referral from RRS. These steps require human decisions.
- **R33 — UPS:** Select E00654 United Parcel Service.
- **R34 — Goodyear:** Select “Goodyear Tire and Rubber Co,” not “Goodyear Tire and Rubber Company.”
- **R35 — Goodyear Facility:** Choose the employer-defined Facility from the Location Code in special instructions (`RE` → `RE Retail Store`, `CT` → `CT Commercial Tires Centers`, otherwise a matching option). If absent, leave blank and create a CPD Inquiry task “Need Location from CE” (due today, priority Med). Never select “All Other Locations.” The embedded list has 25 entries: PL0153 Lawton OK; RE Retail Stores; PL0133 Topeka KS; CT Commercial Tire Centers; CP0001 Texarkana AR; PL0126 Danville VA; PL0161 Fayetteville NC; PL0155 Asheboro NC; CP0016 Tupelo MS; PL0130 Social Circle GA; PL0131 Gadsden AL; PL0993 Akron OH; CP0018 Findlay OH; CH0148 Bayport TX; PL0129 Union City TN; MS9999 Mileage Sales; MS9999 Lake Buena Vista FL; MS9999 Sun Valley CA; MS9999 Chatsworth CA; MS9999 El Monte CA; PL0170 Kingman AZ; CH0141 Houston TX; CH0137 Niagara Falls NY; EP0112 Saint Marys OH; ML1286 Eglin Air Force Base FL. Embedded labels are not proof of live dropdown labels.
- **R37 — GAA routing:** For the scoped employers, tick GAA Vendor in Subject Line Builder if the GAA NCM email address, claim jurisdiction AR/TX, claimant state TX/AR, a GAA special-instruction phrase or a Texarkana-area claimant city applies. Cities: Texarkana, Nash, Wake Village, Hooks, Maud, Redwater, New Boston, DeKalb, Atlanta TX; Texarkana, Fouke, Genoa, Doddridge, Ashdown, Lewisville AR.

## Verdicts

| Rule | Status | One-line summary | Key evidence |
| --- | --- | --- | --- |
| R8 | PARTIAL | Claim number passes through apart from whitespace; no WC add/strip, RGC detection or Liberty Mutual format branch; completeness checks presence only. | `AI/referral_schema.py:293-299,496-505`; `Final Code/finalcode/field_adapter.py:91-94,113-114` |
| R9 | CONFLICTS | Blank iCase SSN fails completeness before CMS, and the prompt preserves masked values instead of blanking partials. No code inserts the prohibited placeholder. | `AI/referral_schema.py:126,496-505`; `Final Code/finalcode/orchestrator.py:84-107` |
| R17 | PARTIAL | Comcast maps to an E05408 search, but the first employer-type result name is accepted without code verification. | `src/fcm_intake/legacy/legacy_customerchecker.py:480-507,926-932`; `src/fcm_intake/legacy/legacy_fcm.py:1503-1506` |
| R29 | CONFLICTS | A direct requested nurse can become assigned NCM and be entered in Requested NCM with no named-GAA-FCM exclusion or refusal path. | `AI/referral_schema.py:166-172`; `AI/source_evidence.py:66-70,126-137`; `Final Code/finalcode/field_adapter.py:32-53,106-141`; `Processes/SubjectLineBuilder/Deploy-Ready/legacy_steps.py:1307-1321` |
| R33 | PARTIAL | UPS maps to E00654 search but accepts an unverified first employer row; legacy renames UPS without “Inc.” | `src/fcm_intake/legacy/legacy_customerchecker.py:480-507,926-932`; `src/fcm_intake/legacy/legacy_fcm.py:1503-1504` |
| R34 | CONFLICTS | COMPANY normalizes to CO; Unity searches only four characters and may click a sole wrong Goodyear suggestion. | `src/fcm_intake/legacy/legacy_customerchecker.py:331-335,926-932`; `src/fcm_intake/legacy/legacy_unity.py:295-318` |
| R35 | PARTIAL WITH CONFLICTING BEHAVIOUR | Unity uses verbatim Facility labels or provider city, does not create the missing-location task, and live labels are unknown. | `src/fcm_intake/legacy/legacy_unity.py:1373-1429`; `AI/referral_schema.py:121-125` |
| R37 | PARTIAL WITH CONFLICTING BEHAVIOUR | GAA only checks Texarkana city plus Goodyear name; `Toggle()` can untick an already-ticked box. | `Processes/SubjectLineBuilder/Deploy-Ready/legacy_steps.py:1322-1325`; `Final Code/finalcode/field_adapter.py:32-65,106-151` |

For R9, legacy Unity clears a prefilled SSN whose first three characters are the prohibited placeholder prefix (`src/fcm_intake/legacy/legacy_unity.py:544-547`). The detailed report calls this a conflict with preserving an existing claimant's value; the parent reviewer considers the clearing consistent with the prohibition on that placeholder because real SSNs never begin with 9. New-versus-existing claimant and iCase origin cannot reliably be determined from current code.

R35's remark about employer identity in special instructions is blocked by design: extraction explicitly forbids taking the employer from that section (`AI/referral_schema.py:121-125`). Repository candidates read `RE Retail Stores` and `CT Commercial Tire Centers`, matching the embedded list rather than the rule prose; the live options remain unknown.

R37 has no claimant-state, jurisdiction, GAA NCM email, special-instruction, Cooper Tire or verified Liberty Mutual check. The necessary nurse email, jurisdiction, claimant city/state and special instructions are extracted today.

## CEM verdict

**EXISTS AND IS LIVE, conditionally and attended.** The customer-checker wrapper (`src/fcm_intake/workflows/customer_checker.py:8,49-50`) calls legacy `customer_prompter_and_cem`, which asks whether CEM is needed and runs `legacy_cem.main()` on yes (`src/fcm_intake/legacy/legacy_customerchecker.py:667-758`). The route is reachable from Final Code's CMS stage, Reopen-Check and Subject Line Builder. But the target is UAT (`src/fcm_intake/legacy/legacy_cem.py:52,163`), whereas CEM.docx documents production. Only employer search runs; customer search is defined but not called; Edge launches on import; there is no Data Control approval tracking or enforced customer-exists-first precondition. Unity's CEM call is commented out (`src/fcm_intake/legacy/legacy_unity.py:347-352`). Separately, Unity's `UNITY_URL` points to UAT (`src/fcm_intake/legacy/legacy_unity.py:23`); whether standalone Unity overrides it is unverified.

## The deciding finding

The system never verifies that the customer is Liberty Mutual. On these referrals, “Customer Name” denotes the **employer** and is extracted as `Employer Name` (`AI/referral_schema.py:54,157-158`); CMS returns a plain employer name, not a code. Neither customer C02283 nor employer E-codes are verified. All eight rules are Liberty Mutual-scoped and cannot trigger safely without verified customer identity.

## What exists to build on

Today's shared Bedrock call performs extraction; classification and name inference are Python post-processing. The Wizard would be a new policy-judgement call rather than another extraction. Reusable attended pauses include the workbench ID-keyed `_ask_prompt` (stale answers rejected; no state lock held while waiting), `pending_review`/`answer_review`, completeness and appointment gates, the pinned urgent banner, and Unity's approval prompt. Final Code's sequence is CAPTURE → EXTRACT → REVIEW → GATE → CMS → SUBJECT LINE BUILDER (`Final Code/finalcode/orchestrator.py:15,34-54,73-139`); `on_stage` announces entry only, so first-class interstage checks need a small orchestrator change. Unity has guard points before Assign and RRS completion. Subject Line Builder has pre-Create review, but R29 must be checked before Requested NCM is filled. Wizard verdicts could be explicitly whitelisted into per-referral audit JSON (`Final Code/finalcode/audit.py`).

## Recommended shape (not decided)

Use a rule registry declaring timing (FIRST/MID/LAST), scope (customer and employer), and deterministic-versus-AI judgement, with typed verdicts, attended pauses and explicitly whitelisted audit fields. R8 format, R17/R33/R34 codes and Co-versus-Company distinction, R37 trigger lists and R9 blank/never-placeholder logic are largely deterministic. AI is useful for contextual R35 facility matching, employer evidence only in special instructions, and recognizing a direct request for the named GAA FCM in free text. Never infer customer permission, award or nurse availability from model output. Neither global pause/correction authority nor an automatic assignment decision has been approved.

## Open questions blocking design

1. Where can the bot read and verify customer identity C02283 and the employer E-code? CMS currently returns only a name.
2. What are the live Facility dropdown labels? Obtain a screenshot or export.
3. Should the completeness gate allow a blank SSN for applicable iCase referrals?
4. How are iCase origin and a noted previous RGC identified reliably?
5. Is the UAT CEM target intentional, or should the attended flow target production?

## Detailed reports

- [[process-wizard/W1-employer-and-cem]] — employer identity, R17/R33/R34 and CEM.
- [[process-wizard/W2-facility-and-gaa]] — R35 and R37.
- [[process-wizard/W3-claimnumber-and-ssn]] — R8 and R9.
- [[process-wizard/W4-r29-and-wizard-architecture]] — R29 and Wizard integration seams.
