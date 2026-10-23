# CMS case setup
> Source: V4 RRS-Unity-CMS BRD Consolidated (slides 102-119). Converted from the owner's BRD. Screenshot descriptions are marked [from screenshot]; everything else is the BRD's own text.
## Summary
CMS case setup begins with locating the correct Unity-created case, especially when a claim has multiple cases. The BOT checks claim, claimant, case, customer, provider, attorney, attachment and notes tabs against RRS/Unity and the referral. It also creates the additional CPD ERFS and prepares the case for RRS Complete Registration. Several entry rules defer to separate rule documents.
## Flow
1. [[#Slide 102 -- CMS - Case Search|Slide 102 -- CMS - Case Search]]
2. [[#Slide 103 -- CMS - Case Search|Slide 103 -- CMS - Case Search]]
3. [[#Slide 104 -- CMS - Claim Tab|Slide 104 -- CMS - Claim Tab]]
4. [[#Slide 105 -- CMS - Claim Tab|Slide 105 -- CMS - Claim Tab]]
5. [[#Slide 106 -- CMS - Claimant Tab|Slide 106 -- CMS - Claimant Tab]]
6. [[#Slide 107 -- CMS - Claimant Tab|Slide 107 -- CMS - Claimant Tab]]
7. [[#Slide 108 -- CMS - Case Tab|Slide 108 -- CMS - Case Tab]]
8. [[#Slide 109 -- CMS - Case Tab|Slide 109 -- CMS - Case Tab]]
9. [[#Slide 110 -- CMS - Case Tab|Slide 110 -- CMS - Case Tab]]
10. [[#Slide 111 -- CMS - Customer Tab|Slide 111 -- CMS - Customer Tab]]
11. [[#Slide 112 -- CMS - Customer Tab|Slide 112 -- CMS - Customer Tab]]
12. [[#Slide 113 -- CMS - Provider Tab|Slide 113 -- CMS - Provider Tab]]
13. [[#Slide 114 -- CMS - Provider Tab|Slide 114 -- CMS - Provider Tab]]
14. [[#Slide 115 -- CMS - Attorneys Tab|Slide 115 -- CMS - Attorneys Tab]]
15. [[#Slide 116 -- CMS - Attorneys Tab|Slide 116 -- CMS - Attorneys Tab]]
16. [[#Slide 117 -- CMS - Attachments Tab|Slide 117 -- CMS - Attachments Tab]]
17. [[#Slide 118 -- CMS - Other Notes Tab|Slide 118 -- CMS - Other Notes Tab]]
18. [[#Slide 119 -- CMS - Letters Tab|Slide 119 -- CMS - Letters Tab]]

## Slide 102 -- CMS - Case Search
**System / screen:** CMS > Case Search
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
For multiple claims, the bot will review and open each case associated with the claim. It will identify the case with the latest assigned date and matching referral type (Medical or Vocational).
**Screenshot [from screenshot]:** CMS Claimant Search results box the Claim Number column; a Case (Edit) inset boxes Assigned Date and Referral Type, linked by a red connector to show multiple-case comparison.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 103 -- CMS - Case Search
**System / screen:** CMS > Case Search
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
BOT will select the case under the claim identified from the previous steps, if there are multiple cases under the claim, choose the latest Assigned FCM case and always consider case created in Unity.
**Screenshot [from screenshot]:** CMS Claimant Profile lists claims and cases; a red rectangle and arrow mark the Unity-created case row and Select Case action under the chosen claim.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 104 -- CMS - Claim Tab
**System / screen:** CMS > Claim Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
Z
Claim Office Number
The following fields — Claim Office #, Loss #, Line of Insurance (LOI), Jurisdiction, and Adjuster information — should automatically populate from RRS to Unity and then flow into CMS.
BOT will verify that the Claim Office Number in Unity matches the office number on the referral.
Use the Liberty Mutual Claims Office Matrix if needed to confirm the correct office and to obtain the adjuster’s mailing and physical address for entry.
In most cases, the Line of Insurance (LOI) will be Workers’ Compensation.
Exceptions may apply if the referral specifies another coverage type (e.g., FECA, FELA, Longshore/USL&H).
**Screenshot [from screenshot]:** CMS Claim tab: red boxes/arrows mark Claim # and its office-number inset, Loss #, LOI, Claim Jurisdiction, Alt. Claim # and DOI. Adjuster search, contact and address labels appear below; values omitted.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 105 -- CMS - Claim Tab
**System / screen:** CMS > Claim Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
BOT will add a Diagnosis code if one is found on the referral, If unable to determine which ICD code was provided leave blank (why is there no prompt for BOT runner to enter ICD code if available or multiple?)
Information should feed over from Unity if blank BOT will Enter the Date of Disability as identified on referral, If no Date of Disability is specified on the referral use the Date of Injury.
The Body Part and Claim Type fields should automatically populate from RRS to Unity, and then to CMS.Manual entry in CMS is only required when multiple body parts are listed in the referral.
**Screenshot [from screenshot]:** CMS Claim tab captures: red boxes mark Diagnoses and Claim Body Parts tables with Save Claim and Add, injury/claim classification dropdowns, and Disabilities table; no diagnoses or disabilities shown in example.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 106 -- CMS - Claimant Tab
**System / screen:** CMS > Claimant Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
OUT OF SCOPE
* Alive and Well checks are a service where a case manager visits the spouse of a deceased claimant.
* The referral will often provide both the claimant name and demographics and spouse's name and demographics.
* The Spouse of the deceased is to be identified as the claimant in the case on the claimant tab. Enter all data based on spouse's information.  The descendant's name and information should be added to a new note in Other Notes as follows:
    Navigate to Other Notes and click Add
    Subject:  Deceased Information
    Description:  Name, demographics and information provided about descendant.
* If the referral identifies on the deceased claimant name and demographics, you would enter the deceased claimant's demographic data on the claimant tab then add a note to Other Notes to document the Spouse's name as follows:
    Navigate to Other Notes and click Add
    Subject:  Spouse
    Description:  Enter Name and information provided about the spouse.
The claimant rule defined in this process must be followed during RRS entry. No modifications should be made to claimant data once transferred to CMS.
The Other Note field, however, requires manual entry by the bot when the referral meets the specified criteria.
**Screenshot [from screenshot]:** Text-only CMS Claimant Tab slide. Yellow OUT OF SCOPE banner identifies Alive and Well Check paths; no application screenshot or controls beyond textual Other Notes > Add instructions.
**Speaker notes:** none
**Tags:** [DECISION] [OUT-OF-SCOPE]

## Slide 107 -- CMS - Claimant Tab
**System / screen:** CMS > Claimant Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
The Claimant information will prepopulate based on information from EDI feed. No modifications should be made to this tab unless there is additional data or the referral type is “Alive and Well Check.”
[OUT OF SCOPE: The Relationship field should be updated by the bot to “Spouse” only when the referral type is “Alive and Well Check.”]
In all other cases, no change should be made since this field is prepopulated from RRS.
The SSN field should also remain unchanged, as it automatically prepopulates from the EDI feed to CMS.
**Screenshot [from screenshot]:** CMS Claimant form: red box and arrow identify Relationship dropdown and SSN field; their values and surrounding claimant identifiers are omitted.
**Speaker notes:** none
**Tags:** [DECISION] [OUT-OF-SCOPE]

## Slide 108 -- CMS - Case Tab
**System / screen:** CMS > Case Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
BOT will enter the correct Case supervisor based on the Dedicated Supervisor Mapping (Medical/Vocational), search for the case prefix, if case prefix is not on the document, use branch name,
[Out of scope for phase 1: If case is “Catastrophic/Serious Case After Hours” Set the case supervisor field to the designated case supervisor.]
Case Prefix
Referral type, case objective should auto populate from RRS to Unity to CMS. There are specific product and services rules which should have been followed when completing RRS Subject Line builder.
[Out of scope for phase 1: *For Rush Hospital Visit referrals, all required data should be entered in RRS. No changes are necessary in CMS after the case has been created.]
**Screenshot [from screenshot]:** CMS Case (Edit): boxes/arrows identify Case Number prefix inset, Case Supervisor search, Case Objective and Referral Type. Yellow callouts mark two phase-1 exclusions.
**Speaker notes:** none
**Tags:** [DECISION] [OUT-OF-SCOPE]

## Slide 109 -- CMS - Case Tab
**System / screen:** CMS > Case Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
Inventory type: this field is on the Case tab but not shown in the screen shot above.  The field must be addressed, see standard case registration entry rules.
Medical-Field = Medical-FEE
Vocational = Vocation-FEE
Referral Date, Received Date, and Assigned Date will prepopulate from Unity
Referral Source: BOT will Enter referral number found on Icase PDF into the Referral Source Field.
Attorney, and Claimant Contact Permitted:These fields should remain unchanged, as they should populate based on Unity task completion to case creation.
Bilingual Services Needed: If filled out correctly in RRS/Unity should feed over to CMS case. BOT should verify this field fed over correctly.
**Screenshot [from screenshot]:** CMS Case (Edit): red boxes identify assigned/referral/received dates, Referral Source and Attorney, Claimant Contact Permitted and Bilingual Services Needed checkboxes. Arrow leads to enlarged Inventory Type dropdown; main screenshot does not show that field.
**Speaker notes:** none
**Tags:** [DECISION] [CUSTOMER-RULE-DOC]

## Slide 110 -- CMS - Case Tab
**System / screen:** CMS > Case Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
If the referral documentation lists the claimant's next office visit (NOV) or Doctor's appointment BOT will enter that date in this field else leave blank.
* Locate the Claim Information section of the referral, if there is a Claim ID found BOT will enter that value in this field.
* If no Claim ID has been provided leave this field blank.
The Date of First Appointment and Claim Identifier fields should automatically prepopulate from RRS to Unity, and then to CMS, if corresponding values are provided in RRS.
**Screenshot [from screenshot]:** CMS Case tab: red boxes and arrows isolate Date of First Appointment calendar field and Claim Identifier input; a partially visible LMS Replacement Percentage field is not called out.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 111 -- CMS - Customer Tab
**System / screen:** CMS > Customer Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
Employer Name should be found on the referral, FROI, supporting documentation or setup email.
If Employer is Not Given/Not Applicable BOT should verify correct employer name from RRS entry, then click assign employer and find a match
If the employer name is not found in the search this will require assistance to submit a request via CEM (this process should have been completed during intake, BOT should be able to select employer that was created via CEM or not available during Unity Entry)
Bill to = "Liberty Mutual Commercial Market" oracle code C02283.
The fields should automatically prepopulate from RRS to Unity, and then to CMS,
**Screenshot [from screenshot]:** CMS Customer Relationships: red boxes/arrows mark Employer with Assign Employer and Bill To dropdown; Parent, Carrier and other relationship dropdowns are also visible.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 112 -- CMS - Customer Tab
**System / screen:** CMS > Customer Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
Bill To
* if there are no employer specific rules for the Bill To use:  "Liberty Mutual Commercial Market" oracle code/Accounting # C02283.
* Bill to Location: BOT will match the "claim office number" specified on the referral to the Liberty Mutual Claims Office Matrix to identify the adjuster mailing address to use for entry..
Employer
*This section will populate once the Employer has been selected in the Customer Relationships section above.
* Employer may be found on the referral, FROI, supporting documentation or setup email.
* If field is not populated with provided employer location BOT will click assign Primary location and select a match. If employer contact is provided select a match the includes the employer contact.
*If Employer Contact is provided on the ICase PDF and not available for selection via Assign Primary Location search, follow the Employer Contact Add Process PDF.
Note: If employer location is not found via the Assign Primary Location search an Adress Add submission will be needed to be made via CEM.
**Screenshot [from screenshot]:** CMS Customer tab shows separate Employer and Bill To panels, each with Assign Primary Location; Employer also shows Save and View Comments. Claims Office Matrix reference shown alongside Bill To instructions; personal record values omitted.
**Speaker notes:** none
**Tags:** [DECISION] [CUSTOMER-RULE-DOC]

## Slide 113 -- CMS - Provider Tab
**System / screen:** CMS > Provider Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
Provider information will automatically populate through the RRS and Unity case creation process.
However, if there is more than one provider identified on the referral the BOT should click Add then follow CMS provider search or add rules found on Provider Entry Rules document.
To Add provider, click the Add button
**Screenshot [from screenshot]:** CMS Providers table: red box marks Add (green plus). Provider name/type/address/contact columns, Primary/Preferred checkboxes and Set Primary/Edit/Remove actions are visible; record values omitted.
**Speaker notes:** none
**Tags:** [DECISION] [CUSTOMER-RULE-DOC]

## Slide 114 -- CMS - Provider Tab
**System / screen:** CMS > Provider Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
To search for provider.
If provider is Facility: BOT will
1. Enter First word of facility and Phone Number. If result is greater than 10 or no result is found, do step 2.
2. Add City, State and Zip to the criteria. If no result is found, – Add New Provider.
If provider is professional: BOT will
1. Enter the First name, Last name and Phone Number. If result is greater than 10 or no result is found, do step 2.
2. Add City, State and Zip to the criteria. If no result is found, – Add New Provider.
Click Search
* if the provider is not found BOT will need to create a new provider record as long as you have Faclity or Individual Name, address, city, state, zip, and phone number.  Follow instructions on the Provider Entry Rules document.
When the correct provider/facility shows up, click the Add To Case button.
**Screenshot [from screenshot]:** CMS Provider Search shows facility/name, city/state/ZIP/phone filters and Search; bottom results table boxes Add To Case. Arrows connect search criteria and the selected result action; record values omitted.
**Speaker notes:** none
**Tags:** [DECISION] [CUSTOMER-RULE-DOC]

## Slide 115 -- CMS - Attorneys Tab
**System / screen:** CMS > Attorneys Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
Attorney information will automatically populate through the RRS and Unity case creation process. Therefore, no changes are required to this tab.
If attorney does not populate, click the Add button (see Attorney Entry Rules)
**Screenshot [from screenshot]:** CMS Attorneys table: red box highlights Add (green plus). Attorney type, firm, contact, status and Edit/Remove controls visible; example record omitted.
**Speaker notes:** none
**Tags:** [DECISION] [CUSTOMER-RULE-DOC]

## Slide 116 -- CMS - Attorneys Tab
**System / screen:** CMS > Attorneys Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
To search for attorney, enter first 3 letters of First and Last name and phone number.
When the correct attorney shows up, click the Add To Case button. If no record is found, Add New record following Attorney Entry rules document.
Click Search.
**Screenshot [from screenshot]:** CMS Attorney Search: red boxes and arrows highlight First Name/Last Name search fields, Search and Add To Case in the results table. Firm, city/state/ZIP, phone and attorney-type filters visible; record values omitted.
**Speaker notes:** none
**Tags:** [DECISION] [CUSTOMER-RULE-DOC]

## Slide 117 -- CMS - Attachments Tab
**System / screen:** CMS > Attachments Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
BOT will Select the record where the Sent by = 'UnityApiUser, Unity’ and Date Sent = current date, then on the Subject line keep the current entry and add a dash and the Liberty Mutual referral number.
**Screenshot [from screenshot]:** CMS Attachments tab: Add Attachment and Update Category above Date Sent, Sent By, Category, Subject and Type columns; the example table says No attachments found for claim. No matching row is visible despite the instruction.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 118 -- CMS - Other Notes Tab
**System / screen:** CMS > Other Notes Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
Referral notes and instructions should be automatically generated by the system at the time of case creation if the BOT entered them in the Special Instructions section of RRS or Unity.
**Screenshot [from screenshot]:** CMS Other Notes list: red box marks referral note subject and Edit; arrow leads to detail form with Subject and Note, Save and Return to Other Notes. Note and metadata values omitted.
**Speaker notes:** none
**Tags:** none

## Slide 119 -- CMS - Letters Tab
**System / screen:** CMS > Letters Tab
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
BOT will paste the referral instructions that were originally entered in the Other Notes tab into the Specific Tasks/Services Requested/Instructions field.
A CPD ERFS is automatically created when the case is generated using Unity data. BOT should always create an additional ERFS during case setup completion.
If Unity does not create an ERFS automatically, the BOT must create one after completing the case setup and saving all changes.
**Screenshot [from screenshot]:** CMS Letters tab: red box identifies CPD ERFS in CPD folder; arrow leads to ERFS form, particularly the Specific Tasks/Services Requested/Instructions text area. Other date, employer, physician and attorney field labels visible; values omitted.
**Speaker notes:** none
**Tags:** [DECISION]

## Open questions
- Slide 105 asks why there is no BOT Runner prompt for ambiguous or multiple ICD codes.
- Slide 106 is marked OUT OF SCOPE but its final sentence says the bot must manually enter an Other Note; clarify phase boundary.
- Slide 108 names a specific individual for an out-of-scope after-hours case-supervisor assignment; name withheld. Dedicated Supervisor Mapping is not included.
- Slide 109 references standard case registration entry rules, not included.
- Slides 112–116 refer to Employer Contact Add Process PDF, Provider Entry Rules and Attorney Entry Rules, not included.
- Slide 117 instructs selection of a Unity-sent attachment but its screenshot shows “No attachments found for claim.”
