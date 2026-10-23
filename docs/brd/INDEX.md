# V4 RRS-Unity-CMS BRD — navigation index
> Source: V4 RRS-Unity-CMS BRD Consolidated, 124 slides, converted from the owner’s BRD.

## How to read
Each linked file follows the slide sequence: summary, flow, then `## Slide N -- heading` with system/screen, process, actor, instructions, screenshot description, speaker notes and tags. `[from screenshot]` marks visual descriptions; other slide text is the BRD’s own verbatim text. The field mappings and open questions below are consolidated for navigation.
- `[RULE]`: prescribed process or field rule; `[DECISION]`: conditional branch; `[PAUSE]`: BOT stops for human review; `[OUT-OF-SCOPE]`: excluded from this phase; `[EXCEPTION]`: stated failure path.
- `[RRS-CODE-CHANGE]`: RRS change needed; `[AGENT-ONLY]`: human-operated step; `[LIBERTY-SPECIFIC]`: Liberty Mutual-specific rule; `[CUSTOMER-RULE-DOC]`: defers to an external customer/rule document.

## End-to-end flow
| # | Phase | Slides | Systems | Process | Hands off to |
|---|---|---|---|---|---|
| 1 | [[brd/01-overview-and-scope]] — Overview and scope | 1–4 | RRS, iCase, CMS | Set BOT eligibility, exclusions and assignment prerequisites. | RRS intake and iCase |
| 2 | [[brd/02-rrs-intake-and-icase]] — RRS intake and iCase | 5–16 | RRS, iCase | Assign referral; sign in, download and attach PDF; review eligibility. | CMS Reopen Check and Customer Search |
| 3 | [[brd/03-cms-reopen-and-customer-search]] — CMS Reopen Check and Customer Search | 17–18 | CMS, CEM | Check existing claims and employer/customer match. | Provider information check |
| 4 | [[brd/04-provider-check]] — Provider information check | 19–21 | Referral PDF, RRS, Google | Complete and validate provider details. | RRS Subject Line Builder — Part 1 |
| 5 | [[brd/05-rrs-subject-line-builder-part1]] — RRS Subject Line Builder — Part 1 | 22–45 | RRS, Unity | Search related items; map customer, claimant, employer, claim, appointment and provider. | RRS Subject Line Builder — Part 2 |
| 6 | [[brd/06-rrs-subject-line-builder-part2]] — RRS Subject Line Builder — Part 2 | 46–64 | RRS, Unity | Map contacts, classification, diagnosis and instructions; build subject/template. | RRS Complete Triage and Unity Export |
| 7 | [[brd/07-rrs-complete-triage-and-unity-export]] — RRS Complete Triage and Unity Export | 65–68 | RRS, Unity Entry | Complete triage, handle holds and export referral template. | Unity intervention and task completion |
| 8 | [[brd/08-unity]] — Unity intervention and task completion | 69–93 | Unity, RRS | Assign and validate intervention; attach export; flag or complete task. | Advance notice and assignment |
| 9 | [[brd/09-advance-notice-and-assignment]] — Advance notice and assignment | 94–101 | RRS, Unity, iCase, CMS, Outlook | Resolve case-manager assignment, accept/reject, record UnityComplete and case ID. | CMS case setup |
| 10 | [[brd/10-cms-case-setup]] — CMS case setup | 102–119 | CMS, CEM | Validate case tabs, related records and instructions; prepare CPD ERFS. | Complete Registration |
| 11 | [[brd/11-complete-registration]] — Complete Registration | 120–123 | RRS, CMS, Outlook, CEM | Complete registration or route employer-add request to CMU. | Exceptions |
| 12 | [[brd/12-exceptions]] — Exceptions | 124 | RRS | Record apostrophe-triggered Unity-notification failure. | Unresolved exception |

### Journey at a glance
1. Set scope and BOT eligibility.
2. Assign and acquire the iCase referral in RRS.
3. Check reopen and customer eligibility in CMS.
4. Verify provider data.
5. Populate RRS Subject Line Builder, part 1.
6. Finish field mapping and build the email template.
7. Complete triage and export the Unity referral.
8. Validate and complete the Unity intervention.
9. Arrange case-manager assignment and iCase acceptance.
10. Complete CMS case setup and ERFS.
11. Complete registration or route the CEM/CMU branch.
12. Track the unresolved RRS notification exception.

## Scope and eligibility
From [[brd/01-overview-and-scope]] (slides 2–4; quoted BRD instructions):

> - “Once the referral email is selected and it is determined that there is an iCase link in the message body the BOT code needs to click the link, pause to permit BOT Runner to enter credentials and multifactor authentication.”
> - “Then the BOT will need to: check for referral types requiring processing by the BOT Runner such as those noted below (and on instructions provided), perform the Reopen check and the Like Item search.  When the BOT confirms it is “BOT Eligible” it can continue to next pages in this PPT.”
> - “Referral types that Genex is not permitted to service (this is captured in the rules documentation)”
> - “SCAH (Serious Case After Hours), LM Rush Staffing, Catastrophic, or any referral email that does not contain a link to iCase Management.”
> - “The Reopen check must be performed to determine if the referral is a reopen or new referral as Reopens are out of scope at this time since they follow a different workflow. (this is in the rules documentation)”
> - “Referrals having a prior FCM case that has been closed within the last 365 days or is currently open, must be reviewed by the BOT Runner to determine if the referral is a reopen or duplicate before proceeding.”
> - “Any referral having results in the Like Item search must be reviewed by the BOT Runner to determine if BOT can continue.”
> - “NOTE: A RRS code change will be necessary to support the automation of this process as all work is currently assigned via the dispatch tool or manually by a supervisor or manager who is responsible for managing the RRS Inbox. Else the BOT Runner would need to trigger a BOT to do the following.  This step is to be determined once end to end BOT design is completed.”

The stricter slide 16 BOT-eligibility stop for open/recently closed cases versus slide 3 runner review remains an open question.

## Master field mapping
| RRS field | Source on referral PDF | Rule / condition | Slide | File |
|---|---|---|---|---|
| Like Item Search | PDF Claim Number, claimant first/last name; referral ID for later search | Claim number first, then names (first four letters each if spelling uncertain); slide 23 searches name/referral ID/claim number and associates matches; runner reviews results. | 22–23 | [[brd/05-rrs-subject-line-builder-part1]] |
| Customer | Fixed Liberty Mutual customer; not a PDF value | Enter Liberty Mutual Commercial Market; preserve prepopulated fields. | 24 | [[brd/05-rrs-subject-line-builder-part1]] |
| Claimant lookup: Claim Number / DOB | PDF Claim Number / Claimant Information > Date of Birth | First search; zero/multiple matches → claim number plus first three last-name letters → first three letters of each name plus DOB → runner intervention. | 25 | [[brd/05-rrs-subject-line-builder-part1]] |
| Claimant | PDF Claimant Information | Select matching claimant; if none, select Claimant Address and enter manually. | 25, 27 | [[brd/05-rrs-subject-line-builder-part1]] |
| Claimant Address/contact | PDF Claimant Information > corresponding address, phone and email labels | Existing selected EDI/API claimant address auto-populates and must not be changed; for no match, enter PDF details; Address Line 2 may be skipped. | 26–27 | [[brd/05-rrs-subject-line-builder-part1]] |
| Gender | PDF Claimant Information > Gender | Select matching radio button; blank → Unknown. | 28 | [[brd/05-rrs-subject-line-builder-part1]] |
| DOB | PDF Claimant Information > Date of Birth | Enter if EDI did not already prepopulate. | 28 | [[brd/05-rrs-subject-line-builder-part1]] |
| Claim # | PDF Claim Information > Claim Number | Selected claimant auto-populates RRS value; do not change; verify against PDF. | 29 | [[brd/05-rrs-subject-line-builder-part1]] |
| Employer | PDF Claim Information > Customer Name; plant location / Special Instructions email domain for Goodyear | Select linked employer. Goodyear Tire and Rubber Co (E11483): plant mapping spreadsheet and @goodyear.com are clues. | 30 | [[brd/05-rrs-subject-line-builder-part1]] |
| No Employer | PDF Customer Name absent | Check No Employer. | 30 | [[brd/05-rrs-subject-line-builder-part1]] |
| Employer / Employer Input (new or unlinked) | PDF Customer Name / employer name | Follow CEM add/link; use Not Given/Not Applicable placeholder, type employer in popup; Unity receives placeholder until CEM addition. | 31 | [[brd/05-rrs-subject-line-builder-part1]] |
| Ref Type / Unity referral choices | PDF Referral Type; Standard Intake Entry Rules mapping | Select RRS referral type; in Unity Referral Types choose Service Type, Referral Type, Case Objective, then OK. | 32–33 | [[brd/05-rrs-subject-line-builder-part1]] |
| LOI | PDF Claim Information > Claim Type | Contains WC → Workers Compensation; contains Auto → Auto No-Fault; blank/unexpected → pause. | 34 | [[brd/05-rrs-subject-line-builder-part1]] |
| Service Type | PDF Referral Type interpreted through products/services mapping | Full Medical example → Med radio; other values depend on mapping. | 35 | [[brd/05-rrs-subject-line-builder-part1]] |
| Req Bilingual NCM | Setup email or PDF referral wording | Check only for “Bilingual Services Needed.” | 36 | [[brd/05-rrs-subject-line-builder-part1]] |
| Referral Number / No Referral # | PDF Referral Number | Enter if present, otherwise check No Referral #; number does not feed Unity and must be entered again in CMS referral source. | 37 | [[brd/05-rrs-subject-line-builder-part1]] |
| Claim Juris | PDF Claim Information > State/Jurisdiction of Claim | Enter unless already populated from selected EDI claim; retain existing EDI value. | 38 | [[brd/05-rrs-subject-line-builder-part1]] |
| Claim Identifier | PDF Claim Information > Claim ID | Enter RRS; copy into Unity customer-defined field, then CMS case-tab customer-defined field. | 39 | [[brd/05-rrs-subject-line-builder-part1]] |
| Req FCM / requested FCM | PDF Special Instructions | If Genex FCM requested, check Req FCM, type requested name, select matching record; free-form language varies. | 40 | [[brd/05-rrs-subject-line-builder-part1]] |
| Reopen / Arch | No PDF source; phase boundary | Do not click at this phase; Reopen expressly out of scope. | 40 | [[brd/05-rrs-subject-line-builder-part1]] |
| GAA Vendor | Employer plant/site and PDF Special Instructions vendor/FCM request | Check for Goodyear Texarkana, requested vendor or selected FCM with - MHAA; special named-FCM exception defers to Liberty intake instructions. | 40 | [[brd/05-rrs-subject-line-builder-part1]] |
| Staffing Location | LM staffing request | Do not click; out of scope. | 40 | [[brd/05-rrs-subject-line-builder-part1]] |
| SSN | Selected EDI/API claim, or Liberty intake rules if entry needed | Preserve populated value; defer required new entry to external rules. | 40 | [[brd/05-rrs-subject-line-builder-part1]] |
| Appointment / Date Only / date and time | PDF Special Instructions appointment detail | Appointment when date/time available; Date Only for date without time; enter both when supplied. Past date, Saturday/Sunday or US holiday → runner outreach. | 41 | [[brd/05-rrs-subject-line-builder-part1]] |
| Treating Provider / Provider Info Extract | PDF treating-provider details from iCase referral | Select radio button; review extracted gray fields; open Unity Provider Search with magnifier. | 42 | [[brd/05-rrs-subject-line-builder-part1]] |
| Unity provider search / Set Provider | PDF facility or professional name, phone, city, state, ZIP, address | Facility: first word + phone; professional: last name + phone; >10 or zero results → add city/state/ZIP; still zero → Add New Provider. Select match and Set Provider. | 43 | [[brd/05-rrs-subject-line-builder-part1]] |
| Unity New Provider | PDF provider Name/Facility, Address, City, State, ZIP, Phone | Verify prefill or enter manually; accurate address matters for auto-assignment; Add. | 44 | [[brd/05-rrs-subject-line-builder-part1]] |
| Provider Info | Selected/new Unity provider record originating from PDF | Set Provider populates RRS field; green check confirms. | 45 | [[brd/05-rrs-subject-line-builder-part1]] |
| DOI | Claim Information > Date of Injury/Accident/Illness | Enter PDF date; an EDI-selected claim should already prefill it; add if absent. | 46 | [[brd/06-rrs-subject-line-builder-part2]] |
| DOD | Date of Disability; if absent, Claim Information > Date of Injury/Accident/Illness (DOI) | Use DOD if noted; otherwise default to DOI. | 47 | [[brd/06-rrs-subject-line-builder-part2]] |
| Language | Claimant demographics > Language / Primary Language; Special Instructions | Select requested case-manager language; otherwise English. | 48 | [[brd/06-rrs-subject-line-builder-part2]] |
| Referral Source | Case Manager Information or Special Instructions > Nurse Case Manager name/email | Use customer nurse case manager; parse clearly name-formatted email if only identifier; otherwise blank, including claims-case-manager-only referrals. | 49 | [[brd/06-rrs-subject-line-builder-part2]] |
| Referral source different from adjuster? / Unity Referral Source contact | Case Manager Information or Special Instructions > nurse case manager first/last name, email, phone | Check only when nurse case manager entered as Referral Source; enter available contact data, select Customer TCM; otherwise leave unchecked. | 50 | [[brd/06-rrs-subject-line-builder-part2]] |
| Adjuster | Case Manager Information > Claims Case Manager; claims office / matrix information | Search First Name, Last Name, Company; match intake rules and address guidance, Set Adjuster; if no match Add New Adjuster. | 51 | [[brd/06-rrs-subject-line-builder-part2]] |
| New Adjuster details | Case Manager Information > Claims Case Manager / office contact details | Enter adjuster details and click Add Adjuster after unsuccessful search. | 52 | [[brd/06-rrs-subject-line-builder-part2]] |
| Referral Origin | No PDF source (RRS default) | Always defaults to Customer. | 53 | [[brd/06-rrs-subject-line-builder-part2]] |
| Primary Contact Same As | Case Manager Information / Special Instructions; referral email message body or linked emails | Adjuster if no other contact; Referral Source if nurse case manager entered; Other if another contact specified. | 53 | [[brd/06-rrs-subject-line-builder-part2]] |
| Claimant/Plaintiff Attorney | Attorney Information > Attorney Name, Firm Name, Phone, Address, City, State, Zip | Search phone first; fallback last name, first three of first name or firm, plus city/state/zip; verify and Set Attorney. | 54 | [[brd/06-rrs-subject-line-builder-part2]] |
| New Claimant/Plaintiff Attorney | Attorney Information > attorney and firm / contact fields | If no matching search result, Add New Attorney, enter details, click Add New. | 55 | [[brd/06-rrs-subject-line-builder-part2]] |
| Defense Attorney | Referral > defense attorney (if identified) | Same search/set/add process as claimant/plaintiff attorney; otherwise blank. | 56 | [[brd/06-rrs-subject-line-builder-part2]] |
| Employer Requested | Employer details / CEM request (not direct PDF copy) | Defaults No; Yes after BOT identifies a valid new employer and submits request through CEM. | 57 | [[brd/06-rrs-subject-line-builder-part2]] |
| Unity Body Part | Claim Information > Injury Description; Special Instructions | EDI/API selected record should prefill; do not replace existing selected-record Body Part; if absent/indeterminate, BOT pauses for runner. | 58 | [[brd/06-rrs-subject-line-builder-part2]] |
| Unity Injury Type | Claim Information > Injury Description; Special Instructions | EDI/API selected record should prefill; if missing select appropriate type; if absent/indeterminate BOT pauses for runner. | 59 | [[brd/06-rrs-subject-line-builder-part2]] |
| Unity Injury Cause | Claim Information > Injury Description; Special Instructions | EDI/API selected record should prefill; if missing select appropriate cause; if absent/indeterminate BOT pauses for runner. | 60 | [[brd/06-rrs-subject-line-builder-part2]] |
| Diagnosis Code | Claim Information > Diagnosis Code; possibly Special Instructions | Enter PDF Dx code. | 61 | [[brd/06-rrs-subject-line-builder-part2]] |
| Special Instructions | Special Instructions section | Copy entire section to RRS Special Instruction window, close; button turns green. | 62 | [[brd/06-rrs-subject-line-builder-part2]] |
| Claim Type | Claim Type from EDI/API selected record; referral PDF or email body (possibly Special Instructions) | If not auto-populated, select Lost Time unless referral/email states Medical only. | 63 | [[brd/06-rrs-subject-line-builder-part2]] |
| Build Subject/Insert Template | All completed RRS fields (no single PDF field) | Click when all fields are filled out. | 64 | [[brd/06-rrs-subject-line-builder-part2]] |

## Tag index

### [PAUSE] (26)
- [[brd/01-overview-and-scope#Slide 2 -- BOT referral identification and scope]]
- [[brd/01-overview-and-scope#Slide 3 -- Out of Scope for this phase]]
- [[brd/02-rrs-intake-and-icase#Slide 11 -- iCase sign-in and referral prompt]]
- [[brd/02-rrs-intake-and-icase#Slide 16 -- BOT review of referral PDF]]
- [[brd/03-cms-reopen-and-customer-search#Slide 17 -- CMS – Reopen Check]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 22 -- RRS - Like Item Search]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 25 -- RRS - Claimant]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 34 -- RRS - LOI]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 41 -- RRS - Appointment Date and Time]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 58 -- RRS - Unity Body Part]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 59 -- RRS - Unity injury Type]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 60 -- RRS - Unity Injury Cause]]
- [[brd/07-rrs-complete-triage-and-unity-export#Slide 67 -- RRS - Options]]
- [[brd/08-unity#Slide 70 -- Unity Intervention Queue]]
- [[brd/08-unity#Slide 72 -- Unity - Adjuster]]
- [[brd/08-unity#Slide 74 -- Unity - Employer]]
- [[brd/08-unity#Slide 80 -- Unity – Claimant Address]]
- [[brd/08-unity#Slide 81 -- Unity – Appt Date and Time]]
- [[brd/08-unity#Slide 82 -- Unity – Provider Address]]
- [[brd/08-unity#Slide 83 -- Unity – Provider Address]]
- [[brd/08-unity#Slide 84 -- Unity – Provider]]
- [[brd/08-unity#Slide 88 -- Unity – Customer Defined Fields]]
- [[brd/08-unity#Slide 89 -- Unity – Employer Defined Fields]]
- [[brd/08-unity#Slide 93 -- Unity – Flag and Complete Task]]
- [[brd/09-advance-notice-and-assignment#Slide 95 -- RRS UnityPending]]
- [[brd/09-advance-notice-and-assignment#Slide 98 -- iCase Expanded View]]

### [DECISION] (83)
- [[brd/01-overview-and-scope#Slide 2 -- BOT referral identification and scope]]
- [[brd/01-overview-and-scope#Slide 3 -- Out of Scope for this phase]]
- [[brd/01-overview-and-scope#Slide 4 -- BOT referral eligibility and assignment]]
- [[brd/02-rrs-intake-and-icase#Slide 16 -- BOT review of referral PDF]]
- [[brd/03-cms-reopen-and-customer-search#Slide 17 -- CMS – Reopen Check]]
- [[brd/03-cms-reopen-and-customer-search#Slide 18 -- CMS – Customer Search]]
- [[brd/04-provider-check#Slide 19 -- Checking provider information]]
- [[brd/04-provider-check#Slide 20 -- Checking provider information - RRS]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 22 -- RRS - Like Item Search]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 23 -- RRS - Like Items Search]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 25 -- RRS - Claimant]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 26 -- RRS - Claimant Address]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 27 -- RRS - Claimant]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 28 -- RRS - Gender and DOB]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 30 -- RRS - Employer]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 31 -- RRS - Employer]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 32 -- RRS - Referral Type]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 34 -- RRS - LOI]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 35 -- RRS - Service Type]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 36 -- RRS - Req Bilingual NCM]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 37 -- RRS - Referral Number]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 38 -- RRS - Claim Jurisdiction]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 40 -- RRS - Additional Controls]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 41 -- RRS - Appointment Date and Time]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 43 -- RRS - Unity Provider Search]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 44 -- RRS - Unity Provider Search]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 46 -- RRS - DOI]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 47 -- RRS - DOD]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 48 -- Language]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 49 -- RRS - Referral Source]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 50 -- Referral Source Entry into RRS]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 51 -- RRS - Adjuster]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 52 -- RRS - Adjuster]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 53 -- RRS – Primary Contact]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 54 -- RRS - Claimant/Plaintiff Attorney]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 55 -- Claimant/Plaintiff Attorney]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 56 -- Defense Attorney]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 57 -- Employer Requested]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 58 -- RRS - Unity Body Part]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 59 -- RRS - Unity injury Type]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 60 -- RRS - Unity Injury Cause]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 63 -- RRS - Subject Line Builder]]
- [[brd/07-rrs-complete-triage-and-unity-export#Slide 66 -- RRS – Zip Code]]
- [[brd/07-rrs-complete-triage-and-unity-export#Slide 67 -- RRS - Options]]
- [[brd/08-unity#Slide 70 -- Unity Intervention Queue]]
- [[brd/08-unity#Slide 72 -- Unity - Adjuster]]
- [[brd/08-unity#Slide 73 -- Primary Contact]]
- [[brd/08-unity#Slide 74 -- Unity - Employer]]
- [[brd/08-unity#Slide 76 -- Unity – Claim info – DOI/DOD]]
- [[brd/08-unity#Slide 77 -- Unity – Defense Attorney]]
- [[brd/08-unity#Slide 78 -- Unity – Claim Info – Claim Number]]
- [[brd/08-unity#Slide 79 -- Unity – Claim Info – Claim Number]]
- [[brd/08-unity#Slide 80 -- Unity – Claimant Address]]
- [[brd/08-unity#Slide 81 -- Unity – Appt Date and Time]]
- [[brd/08-unity#Slide 82 -- Unity – Provider Address]]
- [[brd/08-unity#Slide 83 -- Unity – Provider Address]]
- [[brd/08-unity#Slide 84 -- Unity – Provider]]
- [[brd/08-unity#Slide 85 -- Unity - Attorney]]
- [[brd/08-unity#Slide 86 -- Unity – Attachment]]
- [[brd/08-unity#Slide 92 -- Unity – Requested Case Manager]]
- [[brd/08-unity#Slide 93 -- Unity – Flag and Complete Task]]
- [[brd/09-advance-notice-and-assignment#Slide 95 -- RRS UnityPending]]
- [[brd/09-advance-notice-and-assignment#Slide 98 -- iCase Expanded View]]
- [[brd/09-advance-notice-and-assignment#Slide 100 -- CMS – Case Number]]
- [[brd/10-cms-case-setup#Slide 102 -- CMS - Case Search]]
- [[brd/10-cms-case-setup#Slide 103 -- CMS - Case Search]]
- [[brd/10-cms-case-setup#Slide 104 -- CMS - Claim Tab]]
- [[brd/10-cms-case-setup#Slide 105 -- CMS - Claim Tab]]
- [[brd/10-cms-case-setup#Slide 106 -- CMS - Claimant Tab]]
- [[brd/10-cms-case-setup#Slide 107 -- CMS - Claimant Tab]]
- [[brd/10-cms-case-setup#Slide 108 -- CMS - Case Tab]]
- [[brd/10-cms-case-setup#Slide 109 -- CMS - Case Tab]]
- [[brd/10-cms-case-setup#Slide 110 -- CMS - Case Tab]]
- [[brd/10-cms-case-setup#Slide 111 -- CMS - Customer Tab]]
- [[brd/10-cms-case-setup#Slide 112 -- CMS - Customer Tab]]
- [[brd/10-cms-case-setup#Slide 113 -- CMS - Provider Tab]]
- [[brd/10-cms-case-setup#Slide 114 -- CMS - Provider Tab]]
- [[brd/10-cms-case-setup#Slide 115 -- CMS - Attorneys Tab]]
- [[brd/10-cms-case-setup#Slide 116 -- CMS - Attorneys Tab]]
- [[brd/10-cms-case-setup#Slide 117 -- CMS - Attachments Tab]]
- [[brd/10-cms-case-setup#Slide 119 -- CMS - Letters Tab]]
- [[brd/11-complete-registration#Slide 120 -- RRS – Complete Registration]]
- [[brd/11-complete-registration#Slide 122 -- RRS Employer Request Add]]

### [OUT-OF-SCOPE] (7)
- [[brd/01-overview-and-scope#Slide 2 -- BOT referral identification and scope]]
- [[brd/01-overview-and-scope#Slide 3 -- Out of Scope for this phase]]
- [[brd/02-rrs-intake-and-icase#Slide 16 -- BOT review of referral PDF]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 40 -- RRS - Additional Controls]]
- [[brd/10-cms-case-setup#Slide 106 -- CMS - Claimant Tab]]
- [[brd/10-cms-case-setup#Slide 107 -- CMS - Claimant Tab]]
- [[brd/10-cms-case-setup#Slide 108 -- CMS - Case Tab]]

### [AGENT-ONLY] (7)
- [[brd/02-rrs-intake-and-icase#Slide 16 -- BOT review of referral PDF]]
- [[brd/07-rrs-complete-triage-and-unity-export#Slide 67 -- RRS - Options]]
- [[brd/08-unity#Slide 81 -- Unity – Appt Date and Time]]
- [[brd/09-advance-notice-and-assignment#Slide 94 -- RRS Advance Notice]]
- [[brd/09-advance-notice-and-assignment#Slide 97 -- iCase Assignment]]
- [[brd/09-advance-notice-and-assignment#Slide 98 -- iCase Expanded View]]
- [[brd/09-advance-notice-and-assignment#Slide 101 -- RRS – Complete Assignment]]

### [RRS-CODE-CHANGE] (2)
- [[brd/01-overview-and-scope#Slide 2 -- BOT referral identification and scope]]
- [[brd/01-overview-and-scope#Slide 4 -- BOT referral eligibility and assignment]]

### [CUSTOMER-RULE-DOC] (17)
- [[brd/01-overview-and-scope#Slide 2 -- BOT referral identification and scope]]
- [[brd/01-overview-and-scope#Slide 3 -- Out of Scope for this phase]]
- [[brd/02-rrs-intake-and-icase#Slide 16 -- BOT review of referral PDF]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 32 -- RRS - Referral Type]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 33 -- RRS - Referral Type]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 35 -- RRS - Service Type]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 40 -- RRS - Additional Controls]]
- [[brd/05-rrs-subject-line-builder-part1#Slide 41 -- RRS - Appointment Date and Time]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 50 -- Referral Source Entry into RRS]]
- [[brd/06-rrs-subject-line-builder-part2#Slide 51 -- RRS - Adjuster]]
- [[brd/08-unity#Slide 92 -- Unity – Requested Case Manager]]
- [[brd/10-cms-case-setup#Slide 109 -- CMS - Case Tab]]
- [[brd/10-cms-case-setup#Slide 112 -- CMS - Customer Tab]]
- [[brd/10-cms-case-setup#Slide 113 -- CMS - Provider Tab]]
- [[brd/10-cms-case-setup#Slide 114 -- CMS - Provider Tab]]
- [[brd/10-cms-case-setup#Slide 115 -- CMS - Attorneys Tab]]
- [[brd/10-cms-case-setup#Slide 116 -- CMS - Attorneys Tab]]

### [EXCEPTION] (1)
- [[brd/12-exceptions#Slide 124 -- Exception]]

## Referenced documents not included
These are referenced by the converted BRD but were not supplied with it. Names that vary across slides are grouped under one artifact where applicable.

| Document / process | Slides | Used for |
|---|---|---|
| Rules documentation / Liberty Mutual Workflow Cheat Sheet | 2–3, 16, 92 | Eligibility, exclusions and auto-assignment. |
| CEM new-employer / employer-add-link / address-add process | 18, 31, 57, 74, 111–112, 122 | New customer/employer and address requests. |
| Goodyear plant mapping spreadsheet | 30 | Plant/site-to-employer mapping. |
| Product and services mapping document | 32, 35, 108 | Service Type, Referral Type and Case Objective classification. |
| Standard Intake Entry Rules / standard intake rules | 33, 41, 50–51, 92 | Classification, appointment, contact, adjuster and assignment rules. |
| Liberty Mutual intake instructions / Liberty intake rules document | 40 | GAA vendor FCM exception and SSN entry. |
| Adjuster address matrix / Liberty Mutual Claims Office Matrix | 51, 104, 112 | Office-number, mailing and physical address lookup. |
| Dedicated Supervisor Mapping (Medical/Vocational) | 108 | Case-supervisor selection. |
| Standard case registration entry rules | 109 | Inventory Type and registration fields. |
| Employer Contact Add Process PDF | 112 | Employer contact creation. |
| Provider Entry Rules document | 113–114 | CMS provider search/add. |
| Attorney Entry Rules document | 115–116 | CMS attorney search/add. |

## Consolidated open questions
Questions retain source wording, grouped by phase. Repeated cross-phase reopen/eligibility and missing-rule-document questions are listed once under the earliest applicable phase.

### Overview and scope — [[brd/01-overview-and-scope]]
- The BRD cites rules documentation and the Liberty Mutual Workflow Cheat Sheet, which are not included here.
- Slides 2 and 4 leave assignment automation versus BOT Runner trigger undecided.
- Slides 2–3 call reopens out of scope but also allow BOT Runner review of prior open/recently closed cases; the boundary between review and BOT continuation needs confirmation.

### RRS intake and iCase — [[brd/02-rrs-intake-and-icase]]
- Slide 13 calls the action “Delete Item” while the screenshot button is “Deleted Items”; confirm the actual destructive control.
- Slide 16 says a prior open/recently closed case makes the referral not BOT eligible, whereas slides 3 and 17 describe runner validation and possible continuation; clarify precedence.
- Slide 6 links to iCase before slides 7–10 describe assignment and opening the link again; clarify actual operational order.

### CMS Reopen Check and Customer Search — [[brd/03-cms-reopen-and-customer-search]]
- Slide 18 does not define the partial-match threshold, how a validation answer is chosen, or the CEM new-employer process; source process document not included.

### Provider information check — [[brd/04-provider-check]]
- Slide 19 says “RSS 1st then google” but slide 20 identifies an RRS/Subject Line Builder provider search; confirm RSS versus RRS.
- Slide 20 uses “bash/validate” without defining “bash,” and supplies no Google-search screenshot or explicit resolution for conflicting search results.
- The rule for when missing provider information cannot be validated is unstated.

### RRS Subject Line Builder — Part 1 — [[brd/05-rrs-subject-line-builder-part1]]
- Slides 30 and 40 rely on a Goodyear plant-mapping spreadsheet and Liberty Mutual intake instructions not included here. Slide 40 names a specific GAA vendor FCM; their name has been replaced with the role. The exception itself is unresolved without those instructions.
- Slides 32–35 and 41 refer to product/services mapping and Standard Intake Entry Rules not included here; classification beyond illustrated values and appointment confirmation timing are not completely specified.
- Slide 40 proposes cross-checking active CMS FCMs as a suggestion, not a settled requirement; identifying a requested FCM from arbitrary free-form instructions remains unresolved.
- Slide 31 does not define when the CEM add/link is complete or how the BOT learns this; slide 41 offers two alternative appointment-confirmation gates (before Unity submission or before Unity Complete Task).
- Slide 43 says abbreviation handling is used to “bash” results; intended matching behavior is unclear. Slide 24 says fields prepopulate that later slides direct BOT to populate or verify; precedence when already populated is only explicitly defined for selected fields.

### RRS Subject Line Builder — Part 2 — [[brd/06-rrs-subject-line-builder-part2]]
- Slide 47 says use Date of Disability for DOD but the annotated PDF box highlights Date of Injury/Accident/Illness instead; confirm where an explicit DOD is recorded.
- Slide 49 contains a generic email-format example; its address pattern is redacted here under the repository no-email-value policy.
- Slides 50–51 refer to a standard intake rule / intake rules and an address matrix not supplied in this slide range; confirm their authoritative documents and match criteria.
- Slide 59 says “correct body part” in the Injury Type dropdown instruction; confirm this is a wording error rather than an intended different mapping.
- Slides 58–60 say selected EDI/API classification should auto-populate, yet also say the BOT pauses if absent after selection; clarify when BOT selection is permitted versus mandatory pause.
- Slide 56 does not identify the defense-attorney PDF section by label; verify the source on applicable referral variants.

### RRS Complete Triage and Unity Export — [[brd/07-rrs-complete-triage-and-unity-export]]
- Slide 66 says the ZIP entry is generally the provider ZIP with referral-type exceptions but explicitly specifies only Med/Medical Task and Vocational Task; other referral types need their source rule.
- Slide 67 does not specify the correct reachout status for each incomplete-information condition or what to do if Customer Check is No.
- Slide 68 says Export Referral produces a desktop email template; its filename and subsequent attachment mechanism are not specified in this range.

### Unity intervention and task completion — [[brd/08-unity]]
- Slide 71 uses supervisor-access screenshots and says agent-access screenshots remain to be supplied.
- Slide 74 asks whether employer review/selection is performed by BOT or BOT Runner; CEM process is not supplied.
- Slides 77 and 85 ask what to do when a newly added attorney fails address validation.
- Slides 82–83 conflict: pause for CPD management on a suggested provider address versus select and Use the recommended Google address.

### Advance notice and assignment — [[brd/09-advance-notice-and-assignment]]
- Slides 95–96 show Assignment Menu option 23 before Assign Input option 1; slide 96 text omits explicitly selecting option 23.
- Slide 99 says Claimant Number for the second RRS pop-up, but the screenshot appears to ask for claimant name.
- Slides 94 and 97 vary on who claims/assigns in Unity (BOT Runner or branch), and on who accepts in iCase.

### CMS case setup — [[brd/10-cms-case-setup]]
- Slide 105 asks why there is no BOT Runner prompt for ambiguous or multiple ICD codes.
- Slide 106 is marked OUT OF SCOPE but its final sentence says the bot must manually enter an Other Note; clarify phase boundary.
- Slide 108 names a specific individual for an out-of-scope after-hours case-supervisor assignment; name withheld. Dedicated Supervisor Mapping is not included.
- Slides 112–116 refer to Employer Contact Add Process PDF, Provider Entry Rules and Attorney Entry Rules, not included.
- Slide 117 instructs selection of a Unity-sent attachment but its screenshot shows “No attachments found for claim.”

### Complete Registration — [[brd/11-complete-registration]]
- Slide 120 directs Employer Request Add to slide 117 for the CMU process, but this deck puts that path on slides 122–123.
- Slides 121 and 123 show Outlook draft messages but do not expressly state whether BOT sends them or who approves recipients.

### Exceptions — [[brd/12-exceptions]]
- Slide 124 describes apostrophe-triggered RRS errors without a mitigation or recovery owner.

## Exceptions
[[brd/12-exceptions]] (slide 124) records an RRS failure when an apostrophe in a claimant name causes unhandled errors as a Unity notification reaches the RRS box. Mitigation and recovery owner are unspecified.

