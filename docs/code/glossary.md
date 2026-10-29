---
tags: [code, glossary]
sources: [docs/brd/01-overview-and-scope.md, docs/brd/05-rrs-subject-line-builder-part1.md, docs/brd/10-cms-case-setup.md, docs/brd/11-complete-registration.md, AI/referral_schema.py, src/fcm_intake/legacy/CMS.py]
verified_at: b47ced0 (2026-10-28)
---
# Glossary

**Summary.** These are the terms used in the code and the BRD. An expansion is marked *confirmed* only where the BRD or the code states it. Treat the others as unconfirmed, and ask the owner before using them in documents meant for other people.

## Systems

| Term | Meaning | Status |
| --- | --- | --- |
| **RRS** | Referral Routing System: the Windows desktop app that holds the referral work queue. Automated through pywinauto UIA | Confirmed (BRD) |
| **iCase / iCaseManager** | The referral-intake portal. Its PDF is the referral source; the operator approves the referral there before RRS Complete Assignment | Role from the BRD; no expansion given |
| **CMS** | The case management web portal, run in Internet Explorer mode in Edge with IEDriver | No expansion given in the BRD or code |
| **Unity** | The portal where the referral's task and CMS case are created and completed (Chrome) | Name only |
| **Bedrock** | AWS Bedrock, hosting the extraction model (default `openai.gpt-oss-120b`) | Confirmed (code) |
| **AI PDF Analyzer** | The owner's name for the referral-extraction **modular process**, which is the `AI/` folder itself. Its stand-alone app is the AI PDF Reader / FCM Workbench; Final Code embeds it. See [[code/ai-shared-modules]] | Confirmed (owner, 2026-10-30) |
| **ICD-10-CM** | The US standard diagnosis code set (CDC/NCHS and CMS). The Analyzer checks codes against the FY2027 list. *Invalid* = not in the list; *incomplete* = a real category that isn't billable, flag currently switched off | Confirmed (code) |

## Business terms

| Term | Meaning | Status |
| --- | --- | --- |
| **LOI** | Line of Insurance, e.g. Workers Compensation or Auto No-Fault, chosen from the PDF's Claim Type | Confirmed (BRD 05, 10) |
| **SCAH** | Serious Case After Hours. Out of scope for the BOT | Confirmed (BRD 01) |
| **NCM** | Nurse Case Manager (`NCM`, `Nurse Case Manager E-mail Address` fields); assigned in Unity after approval since v1.0.13 | Confirmed (code) |
| **FCM** | The repo and product name (FCM Intake). The BRD refers to a requested "field case manager" | Likely Field Case Management/Manager; unconfirmed |
| **CEM** | The **Employer Request Add** process, run when the employer isn't found in CMS (BRD 11: "Employer Request Add (CEM)"). Code: `legacy_cem.py` plus a daily CEM checker workbook | Process confirmed; acronym not expanded |
| **CMU** | The team or process that completes the employer add after a CEM request (BRD 11, slides 122–123); Complete Registration uses option `10` | Role from the BRD; no expansion given |
| **C02283** | The Oracle code for the Bill To customer "Liberty Mutual Commercial Market" | Confirmed (BRD 10) |
| **CPD ERFS** | A letter item on the CMS Letters tab that registration configures; the BRD also asks for an *additional* ERFS | No expansion given |
| **TCM** | A CMS case type. An open TCM for Goodyear/Cooper Tire stops the customer search for manual processing | No expansion given |
| **Inventory Type** | CMS case field: `Medical - FEE` or `Vocational - FEE` | Confirmed (code) |
| **Referral Type** | Medical or Vocational; drives CMS case matching and the inventory type | Confirmed |
| **Option 19 / 3 / 10** | RRS input-box codes: **19** = Complete Assignment (Unity), **3** = Complete Registration, **10** = Complete Registration on the CEM path. Their business meaning beyond that isn't documented | Codes confirmed; meaning unconfirmed |
| **BOT / BOT Runner** | The automation and the operator who runs it | BRD usage |

## Repo terms

| Term | Meaning |
| --- | --- |
| **Deploy-Ready** | A process's shared controller and implementation, ready to merge. Not proof of live validation |
| **Stand-Alone** | A process's own runner, desktop app, synthetic scenarios and tests |
| **Final Code** | The merged attended chain, `FinalCode.exe` |
| **`Not found`** | The model's value for an absent field. Adapters convert it to `""` |
| **`allData`** | The legacy Subject Line Builder field dictionary (camelCase keys) |
| **memory_only** | The Reader front end running inside Final Code: text from RRS, no file upload, no workbook |
| **FCM-1.1-NN** | A permanent backlog ID ([[INSTRUCTIONS]]) |
| **JARVIS** | The owner's word to recall the parked Process Wizard investigation ([[process-wizard/INVESTIGATION]]) |

## Related

[[code/CODE-MAP]] · [[brd/INDEX]]

## Open questions

- Confirm the expansions of CMS, CEM, CMU, ERFS, TCM and FCM with the owner or BA. A candidate for the BA question workbook.
