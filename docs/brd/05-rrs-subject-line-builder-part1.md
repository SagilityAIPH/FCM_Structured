# RRS Subject Line Builder — Part 1
> Source: V4 RRS-Unity-CMS BRD Consolidated (slides 22-45). Converted from the owner's BRD. Screenshot descriptions are marked [from screenshot]; everything else is the BRD's own text.
## Summary
This phase searches RRS for related items, finds or enters the claimant, and populates the first half of the Subject Line Builder from the Liberty Mutual iCase referral. It maps customer, employer, classification, claim attributes, appointment and provider details into RRS and Unity lookup windows. Existing EDI/API values are preserved where specified. Ambiguous matches and certain claim or appointment exceptions require runner review; provider selection hands the partially filled builder onward.
## Flow
1. [[#Slide 22 -- RRS - Like Item Search|Like Item Search]]
2. [[#Slide 23 -- RRS - Like Items Search|Like Items Search]]
3. [[#Slide 24 -- RRS - Customer|Customer]]
4. [[#Slide 25 -- RRS - Claimant|Claimant]]
5. [[#Slide 26 -- RRS - Claimant Address|Claimant Address]]
6. [[#Slide 27 -- RRS - Claimant|Claimant]]
7. [[#Slide 28 -- RRS - Gender and DOB|Gender and DOB]]
8. [[#Slide 29 -- RRS - Claim Number|Claim Number]]
9. [[#Slide 30 -- RRS - Employer|Employer]]
10. [[#Slide 31 -- RRS - Employer|Employer]]
11. [[#Slide 32 -- RRS - Referral Type|Referral Type]]
12. [[#Slide 33 -- RRS - Referral Type|Referral Type]]
13. [[#Slide 34 -- RRS - LOI|LOI]]
14. [[#Slide 35 -- RRS - Service Type|Service Type]]
15. [[#Slide 36 -- RRS - Req Bilingual NCM|Req Bilingual NCM]]
16. [[#Slide 37 -- RRS - Referral Number|Referral Number]]
17. [[#Slide 38 -- RRS - Claim Jurisdiction|Claim Jurisdiction]]
18. [[#Slide 39 -- Claim Identifier Field|Claim Identifier Field]]
19. [[#Slide 40 -- RRS - Additional Controls|Additional Controls]]
20. [[#Slide 41 -- RRS - Appointment Date and Time|Appointment Date and Time]]
21. [[#Slide 42 -- RRS - Treating Provider Info|Treating Provider Info]]
22. [[#Slide 43 -- RRS - Unity Provider Search|Unity Provider Search]]
23. [[#Slide 44 -- RRS - Unity Provider Search|Unity Provider Search]]
24. [[#Slide 45 -- RRS - Treating Provider Info|Treating Provider Info]]

## Field mapping summary
| RRS field | Source on referral PDF | Rule / condition | Slide |
|---|---|---|---|
| Like Item Search | PDF Claim Number, claimant first/last name; referral ID for later search | Claim number first, then names (first four letters each if spelling uncertain); slide 23 searches name/referral ID/claim number and associates matches; runner reviews results. | 22–23 |
| Customer | Fixed Liberty Mutual customer; not a PDF value | Enter Liberty Mutual Commercial Market; preserve prepopulated fields. | 24 |
| Claimant lookup: Claim Number / DOB | PDF Claim Number / Claimant Information > Date of Birth | First search; zero/multiple matches → claim number plus first three last-name letters → first three letters of each name plus DOB → runner intervention. | 25 |
| Claimant | PDF Claimant Information | Select matching claimant; if none, select Claimant Address and enter manually. | 25, 27 |
| Claimant Address/contact | PDF Claimant Information > corresponding address, phone and email labels | Existing selected EDI/API claimant address auto-populates and must not be changed; for no match, enter PDF details; Address Line 2 may be skipped. | 26–27 |
| Gender | PDF Claimant Information > Gender | Select matching radio button; blank → Unknown. | 28 |
| DOB | PDF Claimant Information > Date of Birth | Enter if EDI did not already prepopulate. | 28 |
| Claim # | PDF Claim Information > Claim Number | Selected claimant auto-populates RRS value; do not change; verify against PDF. | 29 |
| Employer | PDF Claim Information > Customer Name; plant location / Special Instructions email domain for Goodyear | Select linked employer. Goodyear Tire and Rubber Co (E11483): plant mapping spreadsheet and @goodyear.com are clues. | 30 |
| No Employer | PDF Customer Name absent | Check No Employer. | 30 |
| Employer / Employer Input (new or unlinked) | PDF Customer Name / employer name | Follow CEM add/link; use Not Given/Not Applicable placeholder, type employer in popup; Unity receives placeholder until CEM addition. | 31 |
| Ref Type / Unity referral choices | PDF Referral Type; Standard Intake Entry Rules mapping | Select RRS referral type; in Unity Referral Types choose Service Type, Referral Type, Case Objective, then OK. | 32–33 |
| LOI | PDF Claim Information > Claim Type | Contains WC → Workers Compensation; contains Auto → Auto No-Fault; blank/unexpected → pause. | 34 |
| Service Type | PDF Referral Type interpreted through products/services mapping | Full Medical example → Med radio; other values depend on mapping. | 35 |
| Req Bilingual NCM | Setup email or PDF referral wording | Check only for “Bilingual Services Needed.” | 36 |
| Referral Number / No Referral # | PDF Referral Number | Enter if present, otherwise check No Referral #; number does not feed Unity and must be entered again in CMS referral source. | 37 |
| Claim Juris | PDF Claim Information > State/Jurisdiction of Claim | Enter unless already populated from selected EDI claim; retain existing EDI value. | 38 |
| Claim Identifier | PDF Claim Information > Claim ID | Enter RRS; copy into Unity customer-defined field, then CMS case-tab customer-defined field. | 39 |
| Req FCM / requested FCM | PDF Special Instructions | If Genex FCM requested, check Req FCM, type requested name, select matching record; free-form language varies. | 40 |
| Reopen / Arch | No PDF source; phase boundary | Do not click at this phase; Reopen expressly out of scope. | 40 |
| GAA Vendor | Employer plant/site and PDF Special Instructions vendor/FCM request | Check for Goodyear Texarkana, requested vendor or selected FCM with - MHAA; special named-FCM exception defers to Liberty intake instructions. | 40 |
| Staffing Location | LM staffing request | Do not click; out of scope. | 40 |
| SSN | Selected EDI/API claim, or Liberty intake rules if entry needed | Preserve populated value; defer required new entry to external rules. | 40 |
| Appointment / Date Only / date and time | PDF Special Instructions appointment detail | Appointment when date/time available; Date Only for date without time; enter both when supplied. Past date, Saturday/Sunday or US holiday → runner outreach. | 41 |
| Treating Provider / Provider Info Extract | PDF treating-provider details from iCase referral | Select radio button; review extracted gray fields; open Unity Provider Search with magnifier. | 42 |
| Unity provider search / Set Provider | PDF facility or professional name, phone, city, state, ZIP, address | Facility: first word + phone; professional: last name + phone; >10 or zero results → add city/state/ZIP; still zero → Add New Provider. Select match and Set Provider. | 43 |
| Unity New Provider | PDF provider Name/Facility, Address, City, State, ZIP, Phone | Verify prefill or enter manually; accurate address matters for auto-assignment; Add. | 44 |
| Provider Info | Selected/new Unity provider record originating from PDF | Set Provider populates RRS field; green check confirms. | 45 |

## Slide 22 -- RRS - Like Item Search
**System / screen:** RRS > Subject Line Builder > Like Item Search
**Process:** Subject Line Builder
**Actor:** mixed
**Instructions:**
Like item search:
- Complete 1st search using claim number
- Complete 2nd search using claimant last and first name.
- For the name search, sometimes the name is spelled incorrectly. Use first 4 letters of the First Name and first 4 letters of the Last Name to narrow it down
- If items are found in the results:
  - the BOT should advise BOT runner to review additional items to determine if BOT can continue.
  - This is because it is possible to find a manual referral that was received previously and is pending in the RRS Inbox awaiting receipt of the iCase Referral to complete the next action steps Or there could be a Case manager assignment email OR additional details pertinent to the referral which must be attached to the main referral.
- If BOT Runner determines BOT can continue proceed to next steps.
- If BOT Runner determines there are additional actions required BOT should stop and permit BOT Runner to complete referral intake process.
**Screenshot [from screenshot]:** RRS Subject Line Builder: Like Item Search button red-boxed; claim and claimant search controls visible, no connector arrow.
**Speaker notes:** none
**Tags:** [RULE] [DECISION] [PAUSE]

## Slide 23 -- RRS - Like Items Search
**System / screen:** RRS > Subject Line Builder > Like Items Search
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
Search by Claimant Name, Referral Id, and Claim Number. If you find a match, check off the item and click on Add To Work List.
Click on item added to work list and click on the Associate button.
Note: In this form, you have the ability to associate/unassociate/set main/unset main and clear or set claimant name on all items in the view.
**Screenshot [from screenshot]:** Upper RRS crop: Customer, Employer, Claimant, Claim # and No Employer with arrow to Like Item Search. Lower Current Work Items view: blue arrows indicate Search, Add To Work List and Associate; controls for set/unset main, association and claimant name are visible.
**Speaker notes:** none
**Tags:** [RULE] [DECISION]

## Slide 24 -- RRS - Customer
**System / screen:** RRS > Subject Line Builder > Customer
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will enter “Liberty Mutual Commercial Market” in the Customer field.
After doing so, Magnifying Glass will be visible in the UI for later process.
Note: Once Liberty Mutual is entered the following fields will prepopulate Employer, Referral #, Claim Identifier, Claim Juris, Gender, Referral Type (Unity Referral Type Selections), Line of Insurance (Workers’ Compensation only), and Service Type.
Bot will not need to modify prepopulated fields.
**Screenshot [from screenshot]:** RRS Customer field red-boxed and connected to customer-entry instruction; separate red boxes encircle magnifier lookup icons that become visible after customer entry.
**Speaker notes:** none
**Tags:** [RULE] [LIBERTY-SPECIFIC]

## Slide 25 -- RRS - Claimant
**System / screen:** RRS > Subject Line Builder > Claimant
**Process:** Subject Line Builder
**Actor:** mixed
**Instructions:**
A green check will appear signifying that claimant is set.
If there are multiple results, a prompt stop will appear for manual intervention.
BOT will click the Magnifying Glass for Claimant to open RRS Unity Claim Claimant search window.
1. Enter Claim number and DOB and click search. If no match or multiple matches then
1. Claim number and first 3 letters of last name, if no match or multiple matches then
1. First 3 letters of first name, first 3 letters of last name and DOB, if no match or multiple matches then
1. BOT runner intervention to confirm if manual claim/claimant should be added.
**Screenshot [from screenshot]:** RRS claimant lookup magnifier boxed; Unity Claim Claimant search criteria include Claim Number, DOB, first/last names, case number and SSN, with Search, result grid, Set Claim/Claimant and Close. Numbered PDF callouts mark Claim Number and claimant name sources; lower RRS crop boxes green claimant-set check.
**Speaker notes:** none
**Tags:** [RULE] [DECISION] [PAUSE]

## Slide 26 -- RRS - Claimant Address
**System / screen:** RRS > Subject Line Builder > Claimant Address
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
The claimant address will auto populate once a claim in the RRS Unity Claim Claimant Search window is selected. No changes should be done if an EDI or API claim was selected.
**Screenshot [from screenshot]:** Red boxes pair RRS Address 1/2, City, State, ZIP, Country, Phone, Cell and Email with PDF Claimant Information; orange connector indicates source-to-target mapping. Other RRS controls include Gender and DOB.
**Speaker notes:** none
**Tags:** [RULE] [DECISION]

## Slide 27 -- RRS - Claimant
**System / screen:** RRS > Subject Line Builder > Claimant
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
If no matching record is found in the RRS Unity Claim Claimant search, the BOT will close the search window and proceed with entering the claimant’s information manually.
The BOT selects the Claimant Address radio button to display the claimant section, then populates the claimant details from the referral document into the RRS fields. Address Line 2 may be skipped.
**Screenshot [from screenshot]:** Unity Claim Claimant window shows search fields, empty results and Close. RRS Claimant Address radio button is boxed and selected; address/contact/Gender/DOB fields boxed; orange connector links PDF Claimant Information excerpt to RRS.
**Speaker notes:** none
**Tags:** [RULE] [DECISION]

## Slide 28 -- RRS - Gender and DOB
**System / screen:** RRS > Subject Line Builder > Gender and DOB
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
Gender: BOT will identify the  Gender found on the iCase PDF referral form and click the appropriate corresponding radio button. If Gender is blank the BOT will select Unknown.
DOB: BOT will identify the Date of Birth (DOB) found on the iCase PDF referral form and enter it into the DOB field in RRS.
  - NOTE: If an EDI claim is selected this data should already be pre-populated. If not, it can be added in by the BOT.
**Screenshot [from screenshot]:** Blue arrows pair PDF Claimant Information > Gender and Date of Birth with RRS M/F/Unknown radio buttons and DOB box; a radio button is selected.
**Speaker notes:** none
**Tags:** [RULE] [DECISION]

## Slide 29 -- RRS - Claim Number
**System / screen:** RRS > Subject Line Builder > Claim Number
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
After selecting the claimant, the claim number will populate in the Claim # field and this should not be changed.
Ensure that the claim number in the referral document should be the same in RRS.
Note:  claimant can have multiple claim number that is based on the date or injury and LOI.
**Screenshot [from screenshot]:** PDF Claim Number row and RRS Claim # field boxed in red with orange arrow from source to target.
**Speaker notes:** none
**Tags:** [RULE]

## Slide 30 -- RRS - Employer
**System / screen:** RRS > Subject Line Builder > Employer
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will type the Customer Name (PDF) in Employer field in RRS. (All employers linked to Liberty Mutual in the CMS system will load into the RRS SLB upon selection of the customer name (Liberty Mutual).
How to identify if employer is Goodyear Tire and Rubber Co (E11483):
  - If employer name is listed as the facility name/plant location: (e.g., US-Kansas- Topeka” instead of “Goodyear”, use Goodyear plant mapping spreadsheet to identify (e.g., “Topeka”).
  - Review email addresses in special instructions to identify if “@goodyear.com” is found.
If no Customer Name is available in the PDF, BOT will click the No Employer checkbox in RRS.
**Screenshot [from screenshot]:** PDF Customer Name row and RRS Employer field boxed and connected by orange arrow; No Employer checkbox separately boxed and connected to missing-name instruction.
**Speaker notes:** none
**Tags:** [RULE] [DECISION] [LIBERTY-SPECIFIC]

## Slide 31 -- RRS - Employer
**System / screen:** RRS > Subject Line Builder > Employer
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
If employer is new or not linked to Liberty Mutual and does not show in the employer field the BOT will need to follow the CEM process to have added/linked and then will type/select Not Given/Not Applicable in the Employer field in RRS. An Employer Input box will pop up and the BOT will then enter in the new employer's name into the Employer Input box and hit ok. This will allow the new employer's name to show up on the RRS subject line builder, but when this feeds into Unity it will feed in as Not Given/Not Applicable and the BOT will need to add the true new employer's name once it has been added through the CEM process.
**Screenshot [from screenshot]:** RRS Employer dropdown boxed; red arrow leads to Employer Input dialog, with blank text input, OK and Cancel.
**Speaker notes:** none
**Tags:** [RULE] [DECISION]

## Slide 32 -- RRS - Referral Type
**System / screen:** RRS > Subject Line Builder > Referral Type
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will select the appropriate Referral Type from the dropdown and then click the Magnifying Glass to set the Service Type, Referral Type and Case Objective in the Unity Referral Types window
Select the correct Service Type.
Select the correct Referral Type.
Select the correct Case Objective.
Once all 3 fields are complete, click OK.
A green check will appear signifying that Ref Type selection is complete.
Note: follow the product and services mapping document to select the correct value. There are Liberty Mutual specific rules. This is very important as incorrect selection will impact service delivery and billing rates.
**Screenshot [from screenshot]:** PDF Referral Type boxed; RRS Ref Type lookup magnifier boxed; Unity Referral Types window separately boxes Service Type, Referral Type, Case Objective and OK, with arrows from corresponding instructions. Green completion check boxed.
**Speaker notes:** none
**Tags:** [RULE] [DECISION] [CUSTOMER-RULE-DOC] [LIBERTY-SPECIFIC]

## Slide 33 -- RRS - Referral Type
**System / screen:** RRS > Subject Line Builder > Referral Type
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
Check the Standard Intake Entry Rules document and follow process for selecting the Service Type, Referral Type and Case objective.
**Screenshot [from screenshot]:** Two spreadsheet screenshots of Standard Intake Entry Rules show Service Type, Referral Type, Case Objective and referral-code/assignment columns; one cell selected, no callout arrows.
**Speaker notes:** none
**Tags:** [RULE] [CUSTOMER-RULE-DOC]

## Slide 34 -- RRS - LOI
**System / screen:** RRS > Subject Line Builder > LOI
**Process:** Subject Line Builder
**Actor:** mixed
**Instructions:**
When reviewing Liberty Mutual iCase referrals, the BOT must determine the correct LOI (Line of Insurance) by checking the Claim Type field in the referral document.
If the Claim Type contains “WC”
→ LOI = Workers Compensation
If the Claim Type contains “Auto”
→ LOI = Auto No-Fault (.) Sometimes displayed as “Auto – No Fault/Med Pay.” You only need to look for the word Auto
If the Claim Type field is blank or shows an unexpected value
→ BOT will pause and Manual review is required
**Screenshot [from screenshot]:** PDF Claim Type row boxed (business-type example WC); orange arrow connects to boxed RRS LOI dropdown showing Workers Compensation.
**Speaker notes:** none
**Tags:** [RULE] [DECISION] [PAUSE] [LIBERTY-SPECIFIC]

## Slide 35 -- RRS - Service Type
**System / screen:** RRS > Subject Line Builder > Service Type
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
Since the referral type is Full Medical, BOT will select Med (radio button) in Service Type
* This value to select should be defined on the products and services mapping with the referral type/case objective rule.
**Screenshot [from screenshot]:** RRS Service Type Med/Voc/Emp Services / Other radio buttons boxed with Med selected; orange arrow connects to Full Medical instruction.
**Speaker notes:** none
**Tags:** [RULE] [DECISION] [CUSTOMER-RULE-DOC]

## Slide 36 -- RRS - Req Bilingual NCM
**System / screen:** RRS > Subject Line Builder > Req Bilingual NCM
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
This box should only be checked if the verbiage “Bilingual Services Needed” are used in the set up email or referral.
**Screenshot [from screenshot]:** RRS Req Bilingual NCM checkbox boxed, appearing unselected; surrounding customer/referral fields visible; no connector arrow.
**Speaker notes:** none
**Tags:** [RULE] [DECISION]

## Slide 37 -- RRS - Referral Number
**System / screen:** RRS > Subject Line Builder > Referral Number
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will enter the Referral Number (PDF) in Referral Number field in RRS (Note: this will not feed into Unity, so the referral number will need to be entered in again in CMS in the referral source field.
If no Referral Number is available in the PDF, click the No Referral # (RRS) checkbox.
**Screenshot [from screenshot]:** PDF Referral Number row boxed and linked to boxed RRS Referral Number and No Referral # checkbox. Separate connector points from checkbox to absent-number instruction.
**Speaker notes:** none
**Tags:** [RULE] [DECISION]

## Slide 38 -- RRS - Claim Jurisdiction
**System / screen:** RRS > Subject Line Builder > Claim Jurisdiction
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will enter the State/Jurisdiction of Claim (PDF) in Claim Juris field in in RRS. If there is a selected claim EDI and the jurisdiction has already populated, leave it as is.
**Screenshot [from screenshot]:** PDF State/Jurisdiction of Claim row and RRS Claim Juris dropdown boxed and connected by orange arrow.
**Speaker notes:** none
**Tags:** [RULE] [DECISION]

## Slide 39 -- Claim Identifier Field
**System / screen:** RRS > Subject Line Builder > Claim Identifier Field
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will find the Claim Identifier on the Liberty Mutual PDF form next to the field labeled: Claim ID. BOT will enter the Claim ID into the Claim Identifier field in the RRS subject line builder.
Note: This field should then copy to Unity into the Claim Identifier customer defined field, which then will feed into CMS into the claim identifier customer defined field located on the case tab.
**Screenshot [from screenshot]:** Four screenshots: ovals mark PDF Claim ID, RRS Claim Identifier, Unity customer-defined Claim Identifier and CMS case-tab customer-defined Claim Identifier. No connecting arrows.
**Speaker notes:** none
**Tags:** [RULE]

## Slide 40 -- RRS - Additional Controls
**System / screen:** RRS > Subject Line Builder > Additional Controls
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
See below to address for BOT as was missed:
- Req FCM: this is used when a Case manager has been requested in the referral special instructions
  - The BOT will need to scan the Liberty PDF to see if it can identify if there is a requested Genex field case manger and if identified then in RRS, the Req FCM box will need to be checked, and the BOT will have to type in the requested FCM name and select the correct FCM name record. Bottom left screen shot is an example of a requested Genex case manager pulled from a Liberty special instructions, however the verbiage could vary in the PDF special instructions. (Maybe the BOT can do a cross check against active FCMs in CMS to names identified as possible requested Genex case managers on the PDF to help identify if the name in the special instructions is a Genex case manager? Not sure if this would cause a delay or not, just a suggestion, otherwise I am not sure how the bot will 100% of the time be able to identify this information since it is entered into a free form instruction section of the PDF.)
- Reopen: should not be clicked by BOT at this phase as it is out of scope.
- Arch: should not be clicked by BOT at this phase
- GAA vendor:
  - If Liberty Mutual Employer is Goodyear Tire… Check for plant/site/location name of Texarkana, if found then check GAA Vendor check box.
  - If Special instructions identify a requested Vendor name or a Case Manager name that resolves to a name having ‘- MHAA’ when selected after clicking Req FCM then check GAA Vendor check box.
  - If a referral requests the designated GAA vendor FCM, do not assign to her. See rule found on Liberty Mutual intake instructions for details.
- Staffing Location: should not be clicked by BOT as this relates to LM Staffing requests which are out of scope.
- SSN: do not change value if populated by EDI/API claim selection.
  - If entry is required follow entry rules found on Liberty intake rules document.
**Screenshot [from screenshot]:** RRS shows Req FCM, Reopen, Arch, GAA Vendor, Staffing Location and SSN; lower PDF excerpt is Special Instructions. Green highlights emphasize Req FCM, do-not-Reopen, SSN preservation and external rules; yellow highlight marks free-form requested-FCM guidance. No arrows.
**Speaker notes:** none
**Tags:** [RULE] [DECISION] [OUT-OF-SCOPE] [CUSTOMER-RULE-DOC] [LIBERTY-SPECIFIC]

## Slide 41 -- RRS - Appointment Date and Time
**System / screen:** RRS > Subject Line Builder > Appointment Date and Time
**Process:** Subject Line Builder
**Actor:** mixed
**Instructions:**
If appointment date and time is available in the Special Instruction section (PDF), BOT will click the Appointment checkbox.
If appointment provided is date only, BOT will click the Date Only checkbox. Else, leave it uncheck .
If both is provided, BOT will enter the Date and Time.
Note: If the Date and Time is in the past, is on a Saturday or Sunday or US Holiday the BOT runner will need to complete a reachout to confirm appointment date/time before referral is submitted to Unity (or before Unity Complete Task). This is defined on the Standard intake rules document.
**Screenshot [from screenshot]:** PDF Special Instructions appointment excerpt boxed; orange connectors point to boxed RRS Appointment checkbox (checked), Date Only checkbox (unchecked) and date/time controls.
**Speaker notes:** none
**Tags:** [RULE] [DECISION] [PAUSE] [CUSTOMER-RULE-DOC]

## Slide 42 -- RRS - Treating Provider Info
**System / screen:** RRS > Subject Line Builder > Treating Provider Info
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will click the Treating Provider radio button and the provider info fields will show.
Provider Info Extract will display with information parsed from the ICase referral by RRS in gray fields. (Review referral and data for accuracy)
BOT will click the Magnifying Glass to open the Unity Provider Search window
**Screenshot [from screenshot]:** RRS Treating Provider radio button and lookup magnifier boxed, orange arrows leading to Unity Provider LM search window. Parsed Provider Info Extract appears in gray fields; editable search criteria, Search, result panel and Add New Provider visible.
**Speaker notes:** none
**Tags:** [RULE]

## Slide 43 -- RRS - Unity Provider Search
**System / screen:** Unity > Provider Search / New Provider
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
Provider Extract will fill out search criteria based on rules below if Provider information is identified.
Else, BOT will search the provider by using the Facility Name/First and Last name, Phone Number, City, State, Zip and select the matching result. Follow the search criteria.
If a result is shown after searching, click the checkbox on the selected row.
Once selected, click the Set Provider button
If provider is Facility:
1. Enter First word of facility and Phone Number. If result is greater than 10 or no result is found, do step 2.
2. Add City, State and Zip to the criteria. If no result is found, – Add New Provider.
If provider is professional:
1. Enter the Last name and Phone Number. If result is greater than 10 or no result is found, do step 2.
2. Add City, State and Zip to the criteria. If no result is found, – Add New Provider.
Note: If result reflects ‘DR’ or ‘Dr’ as the first name and the other fields noted match it is ok to select the record having ‘Dr’ as the first name.
3.  If there is no result found after doing previous steps, click the Add New Provider button
Update: abbreviation like St, Rd, Ave, etc. are now in the BOT logic to bash the results from the referral.
**Screenshot [from screenshot]:** Unity Provider LM parsed-provider area boxed, with search criteria below. Separate results grid boxes selected-row checkbox guidance and Set Provider button, connected by arrow. Empty-results crop boxes Add New Provider and arrow.
**Speaker notes:** none
**Tags:** [RULE] [DECISION]

## Slide 44 -- RRS - Unity Provider Search
**System / screen:** Unity > Provider Search / New Provider
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
If there still no result shown after searching, BOT will click the Add New Provider button and data should appear from RRS Provider Info Extract else enter the Provider Name/Facility, Address, City, State, Zip and Phone Number.
Note: Address must be accurate as it is key for Unity case manager auto assignment.
After verifying the provider info, click the Add button
Data from Provider Extract will prefill in Unity New Provider Fields (verify data accuracy)
**Screenshot [from screenshot]:** Empty Unity Provider LM search behind Unity New Provider dialog; red box encloses name/facility, Address 1/2, City, State, ZIP, Email and Phone fields; arrows connect prefill/verify instruction and Add button.
**Speaker notes:** none
**Tags:** [RULE] [DECISION]

## Slide 45 -- RRS - Treating Provider Info
**System / screen:** RRS > Subject Line Builder > Treating Provider Info
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
After clicking the Set Provider button, the selected/entered provider info will populate in this section
A green check will appear signifying that Provider selection is complete.
**Screenshot [from screenshot]:** RRS Provider Info field boxed with orange arrow from Set Provider explanation; adjacent green check separately boxed and blue-arrowed.
**Speaker notes:** none
**Tags:** [RULE]

## Open questions
- Slides 30 and 40 rely on a Goodyear plant-mapping spreadsheet and Liberty Mutual intake instructions not included here. Slide 40 names a specific GAA vendor FCM; their name has been replaced with the role. The exception itself is unresolved without those instructions.
- Slides 32–35 and 41 refer to product/services mapping and Standard Intake Entry Rules not included here; classification beyond illustrated values and appointment confirmation timing are not completely specified.
- Slide 40 proposes cross-checking active CMS FCMs as a suggestion, not a settled requirement; identifying a requested FCM from arbitrary free-form instructions remains unresolved.
- Slide 31 does not define when the CEM add/link is complete or how the BOT learns this; slide 41 offers two alternative appointment-confirmation gates (before Unity submission or before Unity Complete Task).
- Slide 43 says abbreviation handling is used to “bash” results; intended matching behavior is unclear. Slide 24 says fields prepopulate that later slides direct BOT to populate or verify; precedence when already populated is only explicitly defined for selected fields.
