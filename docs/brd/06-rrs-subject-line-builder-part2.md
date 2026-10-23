# RRS Subject Line Builder — part 2
> Source: V4 RRS-Unity-CMS BRD Consolidated (slides 46-64). Converted from the owner's BRD. Screenshot descriptions are marked [from screenshot]; everything else is the BRD's own text.
## Summary
The BOT finishes the RRS Subject Line Builder using the referral PDF, selected EDI/API record, and referral messages. It resolves contacts and attorneys, classification fields, diagnosis, special instructions, and claim type. When classification cannot be determined, the BOT pauses for a BOT Runner to select a value. The completed form builds the subject and inserts the email template before RRS Complete Triage.
## Flow
1. [[#Slide 46 -- RRS - DOI|RRS - DOI]]
2. [[#Slide 47 -- RRS - DOD|RRS - DOD]]
3. [[#Slide 48 -- Language|Language]]
4. [[#Slide 49 -- RRS - Referral Source|RRS - Referral Source]]
5. [[#Slide 50 -- Referral Source Entry into RRS|Referral Source Entry into RRS]]
6. [[#Slide 51 -- RRS - Adjuster|RRS - Adjuster]]
7. [[#Slide 52 -- RRS - Adjuster|RRS - Adjuster]]
8. [[#Slide 53 -- RRS – Primary Contact|RRS – Primary Contact]]
9. [[#Slide 54 -- RRS - Claimant/Plaintiff Attorney|RRS - Claimant/Plaintiff Attorney]]
10. [[#Slide 55 -- Claimant/Plaintiff Attorney|Claimant/Plaintiff Attorney]]
11. [[#Slide 56 -- Defense Attorney|Defense Attorney]]
12. [[#Slide 57 -- Employer Requested|Employer Requested]]
13. [[#Slide 58 -- RRS - Unity Body Part|RRS - Unity Body Part]]
14. [[#Slide 59 -- RRS - Unity injury Type|RRS - Unity injury Type]]
15. [[#Slide 60 -- RRS - Unity Injury Cause|RRS - Unity Injury Cause]]
16. [[#Slide 61 -- RRS – Diagnosis Code|RRS – Diagnosis Code]]
17. [[#Slide 62 -- RRS - Special Instructions|RRS - Special Instructions]]
18. [[#Slide 63 -- RRS - Subject Line Builder|RRS - Subject Line Builder]]
19. [[#Slide 64 -- RRS - Subject Line Builder|RRS - Subject Line Builder]]

## Field mapping summary
| RRS field | Source on referral PDF | Rule / condition | Slide |
| --- | --- | --- | --- |
| DOI | Claim Information > Date of Injury/Accident/Illness | Enter PDF date; an EDI-selected claim should already prefill it; add if absent. | 46 |
| DOD | Date of Disability; if absent, Claim Information > Date of Injury/Accident/Illness (DOI) | Use DOD if noted; otherwise default to DOI. | 47 |
| Language | Claimant demographics > Language / Primary Language; Special Instructions | Select requested case-manager language; otherwise English. | 48 |
| Referral Source | Case Manager Information or Special Instructions > Nurse Case Manager name/email | Use customer nurse case manager; parse clearly name-formatted email if only identifier; otherwise blank, including claims-case-manager-only referrals. | 49 |
| Referral source different from adjuster? / Unity Referral Source contact | Case Manager Information or Special Instructions > nurse case manager first/last name, email, phone | Check only when nurse case manager entered as Referral Source; enter available contact data, select Customer TCM; otherwise leave unchecked. | 50 |
| Adjuster | Case Manager Information > Claims Case Manager; claims office / matrix information | Search First Name, Last Name, Company; match intake rules and address guidance, Set Adjuster; if no match Add New Adjuster. | 51 |
| New Adjuster details | Case Manager Information > Claims Case Manager / office contact details | Enter adjuster details and click Add Adjuster after unsuccessful search. | 52 |
| Referral Origin | No PDF source (RRS default) | Always defaults to Customer. | 53 |
| Primary Contact Same As | Case Manager Information / Special Instructions; referral email message body or linked emails | Adjuster if no other contact; Referral Source if nurse case manager entered; Other if another contact specified. | 53 |
| Claimant/Plaintiff Attorney | Attorney Information > Attorney Name, Firm Name, Phone, Address, City, State, Zip | Search phone first; fallback last name, first three of first name or firm, plus city/state/zip; verify and Set Attorney. | 54 |
| New Claimant/Plaintiff Attorney | Attorney Information > attorney and firm / contact fields | If no matching search result, Add New Attorney, enter details, click Add New. | 55 |
| Defense Attorney | Referral > defense attorney (if identified) | Same search/set/add process as claimant/plaintiff attorney; otherwise blank. | 56 |
| Employer Requested | Employer details / CEM request (not direct PDF copy) | Defaults No; Yes after BOT identifies a valid new employer and submits request through CEM. | 57 |
| Unity Body Part | Claim Information > Injury Description; Special Instructions | EDI/API selected record should prefill; do not replace existing selected-record Body Part; if absent/indeterminate, BOT pauses for runner. | 58 |
| Unity Injury Type | Claim Information > Injury Description; Special Instructions | EDI/API selected record should prefill; if missing select appropriate type; if absent/indeterminate BOT pauses for runner. | 59 |
| Unity Injury Cause | Claim Information > Injury Description; Special Instructions | EDI/API selected record should prefill; if missing select appropriate cause; if absent/indeterminate BOT pauses for runner. | 60 |
| Diagnosis Code | Claim Information > Diagnosis Code; possibly Special Instructions | Enter PDF Dx code. | 61 |
| Special Instructions | Special Instructions section | Copy entire section to RRS Special Instruction window, close; button turns green. | 62 |
| Claim Type | Claim Type from EDI/API selected record; referral PDF or email body (possibly Special Instructions) | If not auto-populated, select Lost Time unless referral/email states Medical only. | 63 |
| Build Subject/Insert Template | All completed RRS fields (no single PDF field) | Click when all fields are filled out. | 64 |

## Slide 46 -- RRS - DOI
**System / screen:** RRS > Subject Line Builder > DOI
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will enter the Date of Injury/Accident/Illness(PDF) in DOI field in RRS
Note: If an EDI claim was selected this information should have already pre-filled into this field. If it is not pre-filled it then it can be added.

**Screenshot [from screenshot]:** RRS Subject Line Builder Email Display on the left has DOI boxed; the MCM/Voc Rehab Referral Form on the right has Claim Information > Date of Injury/Accident/Illness boxed. An orange connector links the PDF label to DOI.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 47 -- RRS - DOD
**System / screen:** RRS > Subject Line Builder > DOD
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will enter the Date of Disability in the DOD field in RRS. If DOD is not noted on the referral the BOT will default to entering in the DOI into the DOD field in RRS. Date of Injury/Accident/Illness(PDF)

**Screenshot [from screenshot]:** RRS Subject Line Builder Email Display has DOD boxed; the MCM/Voc Rehab Referral Form has Claim Information > Date of Injury/Accident/Illness boxed and connected by a blue line. The screenshot does not show a separately labeled DOD source.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 48 -- Language
**System / screen:** RRS > Subject Line Builder > Language
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
Language
If Claimant demographics specify primary language or instructions are specifying need for another language speaking case manager, the corresponding language must be selected.
Example: Special Instruction indicates a ‘Spanish speaking case manager is required/requested’ or there is a field called Language or Primary Language on the referral form select the corresponding language.
Else BOT should select ‘English’ as default
Note: This is critical to ensure Unity case manager auto assignment selects correct case manager as language is used in the algorithm.

**Screenshot [from screenshot]:** Subject Line Builder Email Display has the Language dropdown boxed in red; orange callout points to it. No PDF screenshot. The guidance names English as the default and a language request as an override.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 49 -- RRS - Referral Source
**System / screen:** RRS > Subject Line Builder > Referral Source
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will search iCase PDF referral form and enter the Customer’s Nurse Case Manager if found into the referral source field in RRS.
The referral source is found either in the Case Manager Information section or Special Instructions section of the iCase PDF. The referral source if noted on the PDF will be the customer’s Nurse Case Manager. If there is only a Claims Case Manager and no other contact noted in the Case Manager Information section or special instructions then leave this field blank. In the Case Manager section or Special Instructions, check for a name or email address in the PDF.
Sometimes the only available identifier is an email such as: [name-formatted email address]

You may parse this to extract the First and Last name.
If the email is in a different format (for example: initials, department names, or non-name formats), or if no email/name is provided at all, leave the Referral Source field blank.

**Screenshot [from screenshot]:** RRS Referral Source entry field boxed; MCM/Voc Rehab Referral Form shows boxed Case Manager Information and Special Instructions areas, including Claims Case Manager Name, Nurse Case Manager Name, Nurse Case Manager E-mail Address and Referrer Name labels. Green-highlighted instruction text bridges the sources and RRS field; no arrow.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 50 -- Referral Source Entry into RRS
**System / screen:** RRS > Subject Line Builder > Unity Referral Source
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
Referral Source Entry into RRS.
BOT will check the box next to Referral source different from adjuster?
If there is a Nurse case manager listed on the referral form which was entered into the Referral Source field (RRS).  Enter in the customer nurse case manger’s first name, last name, email, and phone number (if found on referral document which can be found in either the Case Manager Information section of the PDF or the Special Instructions section of the PDF.  Then select ‘Customer TCM’ as  Contact Type
Else leave Referral Source different from adjuster? checkbox blank.
Note: If you have both a Claims Case Manager (Adjuster) and a Nurse Case Manager (Referral Source) noted on the PDF then make sure you mark the Referral Source as the Primary Contact. (This is a standard intake rule)

**Screenshot [from screenshot]:** Unity Referral Source entry popup shows First Name, Last Name, Email, Phone Number, Contact Type and Company Name, with OK and Cancel. The instruction text highlights the “Referral source different from adjuster?” checkbox and Customer TCM contact type. No PDF screenshot or connecting arrows.
**Speaker notes:** none
**Tags:** [DECISION] [CUSTOMER-RULE-DOC]

## Slide 51 -- RRS - Adjuster
**System / screen:** RRS > Subject Line Builder > Adjuster Search
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will click the Magnifying Glass to open Adjuster Search window.

Enter the First Name, Last Name and Company click search.
if there is a result, select record that matches intake rules and if yes, click Set Adjuster button.
Note: If the mailing address matches then you can select the matching record. You only need to match the physical address if that is the only address noted on the matrix.
If No result appears or no match is found in list, click Add New Adjuster button follow steps on the next slide.

A green check will appear signifying that Adjuster selection is complete.

**Screenshot [from screenshot]:** RRS form Adjuster magnifying-glass lookup icon boxed; Adjuster Search popup shows First Name, Last Name, Company, City, State, Search, results table, Set Adjuster and Add New Adjuster (buttons boxed). Final RRS inset boxes a green check beside Adjuster. Orange arrows link lookup, search action and check. PDF Case Manager Information is boxed, including Claims Case Manager Name, Claims Office Number, Claims Office Name, Office Phone Number and Claims Case Manager E-mail Address labels.
**Speaker notes:** none
**Tags:** [DECISION] [CUSTOMER-RULE-DOC]

## Slide 52 -- RRS - Adjuster
**System / screen:** RRS > Subject Line Builder > Unity Adjuster Add New
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
If there is no result found after doing previous step, the BOT will click the Add New Adjuster button.

After entering the Adjuster information, click the Add Adjuster button

**Screenshot [from screenshot]:** Empty Adjuster Search results popup boxes Add New Adjuster; arrow leads to Unity Adjuster Add New popup. Its First Name, Last Name, Email, Phone, Fax, Address 1/2, City, State and Zip fields are boxed, as is Add Adjuster. PDF Case Manager Information is boxed, with Claims Case Manager Name, Claims Office Number, Claims Office Name, Office Phone Number and Claims Case Manager E-mail Address labels; connecting orange lines identify the source.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 53 -- RRS – Primary Contact
**System / screen:** RRS > Subject Line Builder > Primary Contact
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
Referral Origin: This will always default to ‘Customer’.
Primary Contact:
Adjuster: This is noted as the primary contact when there are no other contacts noted on the referral.
Referral Source: If there is a Nurse Case Manager entered in as the Referral Source in RRS then this button should be selected as the primary contact.
Other:  Select if the Special instruction (PDF) or the referral email message body or linked emails specify a referral contact other than the claim adjuster or referral source/nurse case manager.

**Screenshot [from screenshot]:** RRS Subject Line Builder form boxes Primary Contact Same As radio controls: Adjuster, Referral Source and Other. Adjuster is selected in the example. Referral Origin, “Referral Source different from adjuster?”, Special Instructions, Clear and Build Subject/Insert Template are visible. No PDF or arrows.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 54 -- RRS - Claimant/Plaintiff Attorney
**System / screen:** RRS > Subject Line Builder > Unity Attorney Search
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will click the Magnifying Glass to open Unity Attorney Search window.

Enter the Phone Number and click search. If no result is found, do step 2.
Enter the Last Name, first 3 of the First Name or Firm Name, City, State and Zip.
If multiple results are found, select matching result and click Set Attorney button.
If single result is found confirm it is matching Attorney on referral form and click  Set Attorney button.
If no result or matching record is found, then proceed to next step on next slide.

A green check will appear signifying that Attorney selection is complete.

**Screenshot [from screenshot]:** RRS Claimant/Plaintiff Attorney lookup icon boxed, leading by orange arrow to Unity Attorney Search popup (First Name, Last Name, Phone, Firm Name, City, State, Zip, Country, Search, results and boxed Set Attorney). Final RRS inset boxes a green check. Provider Information PDF has Attorney Information boxed with Attorney Name, Address-line-1/2, City, State, Zip, Phone Number and Extension labels.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 55 -- Claimant/Plaintiff Attorney
**System / screen:** RRS > Subject Line Builder > Unity Attorney Add New
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
If there is no result found after doing previous steps, BOT will click the Add New Attorney button.

After entering the Claimant/Plaintiff Attorney information, click the Add New button

**Screenshot [from screenshot]:** Unity Attorney Search with empty results boxes Add New Attorney; orange connector leads to Unity Attorney Add New form, boxing First Name, Last Name, Firm Name, Address 1/2, City, State, Zip, Phone, Email and Add New. Provider Information PDF boxes Attorney Information (Attorney Name, Address-line-1/2, City, State, Zip, Phone Number, Extension).
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 56 -- Defense Attorney
**System / screen:** RRS > Subject Line Builder > Defense Attorney
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
If there is a defense attorney identified on the referral, for RRS follow same steps as Claimant/Plaintiff attorney search, set attorney and add new attorney to complete Defense Attorney record.  If no Defense Attorney listed on referral leave field blank

**Screenshot [from screenshot]:** RRS Subject Line Builder form boxes the Defense Attorney text entry and magnifying-glass lookup control. No PDF screenshot or arrow.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 57 -- Employer Requested
**System / screen:** RRS > Subject Line Builder > Employer Requested
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
The field defaults to ‘No’ when the Subject Line Builder is opened. If the BOT identifies that the employer is a valid new employer and submits a request through CEM the BOT would update this field to ‘Yes’.

**Screenshot [from screenshot]:** RRS Subject Line Builder form boxes Employer Requested dropdown, shown at No; no PDF or arrow.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 58 -- RRS - Unity Body Part
**System / screen:** RRS > Subject Line Builder > Unity Body Part
**Process:** Subject Line Builder
**Actor:** mixed
**Instructions:**
When an EDI/API claim/claimant record has been selected the Unity Body Part, Unity Injury Type, and Unity Injury Cause should auto populate. If any do not follow the below:
Review the Injury Description and special instructions in the PDF and select the correct body part in the Unity Body Part dropdown list in RRS.
In this scenario, the injury description shows multiple unknowns, but a Body Part was already in the record after selecting the claimant, therefore it will not be changed. If no Body Part is in the record after selecting the claim or if unable to determine the correct Body Part, BOT will pause, and BOT Runner will need to manually select correct values.

**Screenshot [from screenshot]:** RRS Subject Line Builder boxes Unity Body Part dropdown, shown as Low Back Area (Lumbar and Lumbo-Sacral); Unity Injury Type and Unity Injury Cause appear below. Orange connector joins it to PDF Claim Information > Injury Description and Diagnosis Code, boxed together. PDF excerpt describes injury locations; no personal values transcribed.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE]

## Slide 59 -- RRS - Unity injury Type
**System / screen:** RRS > Subject Line Builder > Unity injury Type
**Process:** Subject Line Builder
**Actor:** mixed
**Instructions:**
When an EDI/API claim/claimant record has been selected the Unity Body Part, Unity Injury Type, and Unity Injury Cause should auto populate. If any do not follow the below:
Review the Injury Description and special instructions in the PDF and select the correct body part in the Unity Injury Type dropdown list in RRS.
In this scenario, the Unity Injury Type did not populate, and injury description shows multiple unknowns.
If no Injury Type is in the record after selecting the claim or if BOT is unable to determine the correct Injury Type, BOT will pause, and BOT Runner will need to manually select correct values.

**Screenshot [from screenshot]:** RRS Subject Line Builder boxes Unity Injury Type dropdown, shown as All Other Specific Injuries, NOC. Orange arrow connects PDF Claim Information > boxed Injury Description and Diagnosis Code rows to that dropdown. Unity Body Part and Unity Injury Cause are adjacent.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE]

## Slide 60 -- RRS - Unity Injury Cause
**System / screen:** RRS > Subject Line Builder > Unity Injury Cause
**Process:** Subject Line Builder
**Actor:** mixed
**Instructions:**
When an EDI/API claim/claimant record has been selected the Unity Body Part, Unity Injury Type, and Unity Injury Cause should auto populate. If any do not follow the below:
Review the Injury Description and special instructions in the PDF and select the correct Injury cause in the Unity Injury Cause dropdown list in RRS
In this scenario, the Unity Injury Cause did not populate, and injury description shows multiple unknowns.
If no Unity Injury Cause is in the record after selecting the claim or if BOT is unable to determine the correct Unity Injury Cause, BOT will pause, and BOT Runner will need to manually select correct values.

**Screenshot [from screenshot]:** RRS Subject Line Builder boxes Unity Injury Cause dropdown, shown as Other - Miscellaneous, NOC. Orange arrow connects PDF Claim Information > boxed Injury Description and Diagnosis Code rows to that dropdown; other Unity classification dropdowns are adjacent.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE]

## Slide 61 -- RRS – Diagnosis Code
**System / screen:** RRS > Subject Line Builder > Diagnosis Code
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
Enter the Diagnosis code from the PDF referral to the Diagnosis code field on RRS. The Dx code can also be in the Special Instruction.

**Screenshot [from screenshot]:** RRS Subject Line Builder boxes blank Diagnosis Code input; orange connector runs from the MCM/Voc Rehab Referral Form Claim Information > Diagnosis Code boxed row to it.
**Speaker notes:** none
**Tags:** none

## Slide 62 -- RRS - Special Instructions
**System / screen:** RRS > Subject Line Builder > Special Instruction
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will click the Special Instructions button to open the Special Instruction window

Copy the entire Special Instruction section and paste it in the Special Instruction window in RRS

After pasting, click the Close button

The Special Instructions button will change into green signifying that the Special Instruction is complete.

**Screenshot [from screenshot]:** First RRS inset boxes Special Instructions button; arrow leads to separate Special Instruction text window with boxed entry area and boxed Close button. Second RRS inset boxes the button after it turns green. PDF Provider Information page boxes Special Instructions section, which is linked to the entry area; only the section label is recorded.
**Speaker notes:** none
**Tags:** none

## Slide 63 -- RRS - Subject Line Builder
**System / screen:** RRS > Subject Line Builder > Subject Line Builder
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
Claim Type:
If not auto populated by the EDI/API claim/claimant selected, then:
  Select ‘Lost Time’ unless the referral (pdf) or email message body states ‘Medical only’.
  On referral (PDF) this could be found in the special instructions.

**Screenshot [from screenshot]:** RRS Subject Line Builder Email Display boxes Claim Type dropdown; orange elbow arrow points from claim-type instruction to dropdown. No PDF screenshot.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 64 -- RRS - Subject Line Builder
**System / screen:** RRS > Subject Line Builder > Subject Line Builder
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
Once all field are filled out, click the Build Subject/Insert Template button.

**Screenshot [from screenshot]:** RRS Subject Line Builder Email Display boxes Build Subject/Insert Template button at bottom; orange arrow points to it. Clear / Reset is beside it; no PDF.
**Speaker notes:** none
**Tags:** none

## Open questions
- Slide 47 says use Date of Disability for DOD but the annotated PDF box highlights Date of Injury/Accident/Illness instead; confirm where an explicit DOD is recorded.
- Slide 49 contains a generic email-format example; its address pattern is redacted here under the repository no-email-value policy.
- Slides 50–51 refer to a standard intake rule / intake rules and an address matrix not supplied in this slide range; confirm their authoritative documents and match criteria.
- Slide 59 says “correct body part” in the Injury Type dropdown instruction; confirm this is a wording error rather than an intended different mapping.
- Slides 58–60 say selected EDI/API classification should auto-populate, yet also say the BOT pauses if absent after selection; clarify when BOT selection is permitted versus mandatory pause.
- Slide 56 does not identify the defense-attorney PDF section by label; verify the source on applicable referral variants.
