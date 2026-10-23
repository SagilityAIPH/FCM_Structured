# Unity intervention and task completion
> Source: V4 RRS-Unity-CMS BRD Consolidated (slides 69-93). Converted from the owner's BRD. Screenshot descriptions are marked [from screenshot]; everything else is the BRD's own text.
## Summary
Unity receives the referral task after RRS intake and export. The BOT searches and assigns the intervention, verifies referral, claim, contacts and provider data, and uploads the exported referral email. Customer and employer fields and the final submission require BOT Runner validation where stated. A completed task hands off to case-manager assignment and advance notice.
## Flow
1. [[#Slide 69 -- Unity Intervention|Slide 69 -- Unity Intervention]]
2. [[#Slide 70 -- Unity Intervention Queue|Slide 70 -- Unity Intervention Queue]]
3. [[#Slide 71 -- Unity – Assigning Task|Slide 71 -- Unity – Assigning Task]]
4. [[#Slide 72 -- Unity - Adjuster|Slide 72 -- Unity - Adjuster]]
5. [[#Slide 73 -- Primary Contact|Slide 73 -- Primary Contact]]
6. [[#Slide 74 -- Unity - Employer|Slide 74 -- Unity - Employer]]
7. [[#Slide 75 -- Unity – Service Type|Slide 75 -- Unity – Service Type]]
8. [[#Slide 76 -- Unity – Claim info – DOI/DOD|Slide 76 -- Unity – Claim info – DOI/DOD]]
9. [[#Slide 77 -- Unity – Defense Attorney|Slide 77 -- Unity – Defense Attorney]]
10. [[#Slide 78 -- Unity – Claim Info – Claim Number|Slide 78 -- Unity – Claim Info – Claim Number]]
11. [[#Slide 79 -- Unity – Claim Info – Claim Number|Slide 79 -- Unity – Claim Info – Claim Number]]
12. [[#Slide 80 -- Unity – Claimant Address|Slide 80 -- Unity – Claimant Address]]
13. [[#Slide 81 -- Unity – Appt Date and Time|Slide 81 -- Unity – Appt Date and Time]]
14. [[#Slide 82 -- Unity – Provider Address|Slide 82 -- Unity – Provider Address]]
15. [[#Slide 83 -- Unity – Provider Address|Slide 83 -- Unity – Provider Address]]
16. [[#Slide 84 -- Unity – Provider|Slide 84 -- Unity – Provider]]
17. [[#Slide 85 -- Unity - Attorney|Slide 85 -- Unity - Attorney]]
18. [[#Slide 86 -- Unity – Attachment|Slide 86 -- Unity – Attachment]]
19. [[#Slide 87 -- Unity – Attachment|Slide 87 -- Unity – Attachment]]
20. [[#Slide 88 -- Unity – Customer Defined Fields|Slide 88 -- Unity – Customer Defined Fields]]
21. [[#Slide 89 -- Unity – Employer Defined Fields|Slide 89 -- Unity – Employer Defined Fields]]
22. [[#Slide 90 -- Unity – Complete Task|Slide 90 -- Unity – Complete Task]]
23. [[#Slide 91 -- Unity – Bilingual CM Requested|Slide 91 -- Unity – Bilingual CM Requested]]
24. [[#Slide 92 -- Unity – Requested Case Manager|Slide 92 -- Unity – Requested Case Manager]]
25. [[#Slide 93 -- Unity – Flag and Complete Task|Slide 93 -- Unity – Flag and Complete Task]]

## Slide 69 -- Unity Intervention
**System / screen:** Unity > Intervention
**Process:** Unity
**Actor:** BOT
**Instructions:**
BOT will log in to Unity. From the top navigation menu, BOT will click the Intervention tab to open the Intervention queue.
The Intervention Tasks list will display all available intervention items for review and action.
**Screenshot [from screenshot]:** Two Unity browser captures: the upper red box highlights the Intervention tab; a downward arrow leads to the lower Intervention Tasks table, boxed in red, with search filters for task, claimant, customer and assignment columns.
**Speaker notes:** none
**Tags:** none

## Slide 70 -- Unity Intervention Queue
**System / screen:** Unity > Intervention Tasks
**Process:** Unity
**Actor:** mixed
**Instructions:**
In the Intervention queue, the BOT will search for the Claimant Name in the search bar. If no results appear, the BOT will refresh the page every minute until the result is displayed. If no result is found the BOT will stop and the BOT Runner will take over.
Once the claimant record appears in the list, locate the correct entry and select it to open the Task page
**Screenshot [from screenshot]:** Unity Intervention Tasks queue: a red box marks the Claimant Name filter and another the matching task row; a blue callout connects search and selection.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE]

## Slide 71 -- Unity – Assigning Task
**System / screen:** Unity > Assigning Task
**Process:** Unity
**Actor:** BOT
**Instructions:**
On the Task Details page, BOT will verify that the correct name appears in the Assign to dropdown menu. BOT will click Assign Task to assign the task to the BOT Runner. (Once BOT opens referral task it will need to hit ‘Claim Task’ button.)
Once the task is successfully assigned, the page will refresh, and the action buttons will update — showing new options such as Referral Details/Export, Release task, and Complete task, as shown in the image below.
(This is a supervisor access. We will update this once we get screenshots for agent access)
**Screenshot [from screenshot]:** Unity Task Details: upper red boxes mark Assign to and Assign task; lower capture highlights the resulting Referral Details/Export, Release task, Delete task and Complete task actions. These captures use supervisor access, not yet agent access.
**Speaker notes:** none
**Tags:** none

## Slide 72 -- Unity - Adjuster
**System / screen:** Unity > Adjuster
**Process:** Unity
**Actor:** mixed
**Instructions:**
If the Adjuster information is already populated in Unity Adjuster Information section, BOT will review and validate the details.
If the adjuster was added in RRS but did not populate in Unity, BOT will click the Search Adjuster Magnifying Glass icon to search for the adjuster manually using same search & select criteria as completed in RRS.
If the adjuster cannot be found in the search results but is listed on the referral document, the BOT will click Add New Adjuster and manually enter the adjuster’s information.
If more than one adjuster record found pause for BOT Runner to select Adjuster or instruct BOT to Add New Adjuster.
**Screenshot [from screenshot]:** Unity Referral contacts > Adjuster Information: red boxes and arrows identify Search Adjuster (magnifying glass) and Add new Adjuster beneath the existing adjuster card.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE]

## Slide 73 -- Primary Contact
**System / screen:** Unity > Primary Contact
**Process:** Unity
**Actor:** BOT
**Instructions:**
Primary Contact: Since this was populated in RRS subject line builder this information should be populated with what was selected in RRS.
Is the referral source different from the adjuster – Y/N
  Contact Same as: Adjuster/Referral Source/Other
Primary Contact Same As:
  Adjuster, Referral Source, Other
**Screenshot [from screenshot]:** Unity Referral contacts: “Is the referral source different from the adjuster?” shows No selected; Primary contact > Same as shows Adjuster selected, with Referral source and Other available. Customer & employer begins below. No annotated arrows.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 74 -- Unity - Employer
**System / screen:** Unity > Employer
**Process:** Unity
**Actor:** mixed
**Instructions:**
In the Customer & Employer section, the BOT will verify the employer information. If the employer populated from RRS, no change is necessary.
If the field displays Not Given / Not Applicable, the employer did not pull in and requires review and selection by BOT Runner. (Is the BOT Runner still doing this part or is the BOT doing it?)
If employer did not populate, click Clear selection and enter the first 4 characters of the employer's name exactly as it appears on the referral document, select the matching Employer record from the dropdown.  (Note: employer/insured/customer/company names referenced on the referral form are not always an exact match to a value in RRS/Unity, when BOT cannot identify record to select it must pause for BOT Runner intervention
If no match appears, Revert the field back to Not Given / Not Applicable and follow the CEM process.
**Screenshot [from screenshot]:** Unity Customer & employer: the first red box and connector mark Clear selection on the employer field; the next red box marks the matching dropdown result; a third capture shows the selected employer. The employer record values are omitted.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE]

## Slide 75 -- Unity – Service Type
**System / screen:** Unity > Service Type
**Process:** Unity
**Actor:** BOT
**Instructions:**
BOT will verify and validate the information under the Service Type section, including the Received Date and Time, Referral Date and Time, Service Type, Referral Type, and Case Objective.
**Screenshot [from screenshot]:** Unity Service type: one red box encloses Received Date/Time, Referral Date/Time and the Service Type, Referral Type and Case Objective dropdowns.
**Speaker notes:** none
**Tags:** none

## Slide 76 -- Unity – Claim info – DOI/DOD
**System / screen:** Unity > Claim info – DOI/DOD
**Process:** Unity
**Actor:** BOT
**Instructions:**
The Date of Disability can sometimes be different from the Date of Injury depending on the referral. BOT will always check the referral document first for a specific Date of Disability.
If the referral does not list a Date of Disability, or you cannot locate one in any section of the document, default to using the Date of Injury as the Date of Disability.
This ensures both fields are accurate and consistent when the disability date is not provided.
**Screenshot [from screenshot]:** Two Unity Claim info captures: red boxes mark Date of Injury and Date of Disability; arrows connect the first date field to the latter for the fallback. The claim-type and injury dropdowns are also visible.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 77 -- Unity – Defense Attorney
**System / screen:** Unity > Defense Attorney
**Process:** Unity
**Actor:** BOT
**Instructions:**
If the Defense Attorney did  auto populate BOT will review and confirm details
If the Defense Attorney did not auto populate from RRS when task was created then, If the Customer has an attorney at the time of referral, BOT will select Yes. If not, select No.
If the attorney information is already populated in Unity, BOT will review and confirm the details.
If the attorney was entered in RRS but did not populate in Unity, BOT will click the Search Attorney magnifying glass icon to look up the attorney record manually.
If the attorney is not found in the search results but is listed on the referral document, BOT will click Add New Attorney and manually enter the attorney’s information. (Need to know BOT process on New Attorney adds if address validation fails?)
**Screenshot [from screenshot]:** Unity Defense Attorney: red boxes identify Search Attorney and Add new Attorney. A second capture shows the new-attorney form with name, firm, contact and address fields and Validate Address, including required-field errors; a yellow callout questions failed validation.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 78 -- Unity – Claim Info – Claim Number
**System / screen:** Unity > Claim Info – Claim Number
**Process:** Unity
**Actor:** BOT
**Instructions:**
In the Claim Info section, BOT will click the Search Claim/Claimant magnifying glass icon to look up the claim in Unity.
Important Note:
This manual search is not always required. If the user completed all required steps in RRS, then the claim/claimant data will automatically pass from RRS to Unity.
Manual search is only needed in special cases — for example, when the customer requires an EDI claim feed, but the claim has not yet been received at the time of referral processing. In these situations, specific Unity intervention steps must be followed.
**Screenshot [from screenshot]:** Unity Claim info: a red box isolates the Search Claim/Claimant magnifying glass beside the claim fields; Claim Number, alternate number, injury/disability dates and claim classification controls remain visible.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 79 -- Unity – Claim Info – Claim Number
**System / screen:** Unity > Claim Info – Claim Number
**Process:** Unity
**Actor:** BOT
**Instructions:**
Only required if Claim/Claimant information did not come over from RRS, or EDI did not link. BOT will enter the Claim Number from the referral documentation. After entering the information, click Search. Unity will return a list of matching claim records.
Search Claim/Claimant:
BOT will review the search results and locate the claim that matches the claimant information from the referral. Click on the correct claim record to select it. The selected row will highlight to confirm your choice. Once selected, Unity will automatically populate the claim fields in the Claim Info section.
**Screenshot [from screenshot]:** Unity Search Claim/Claimant modal: the Claim Number input is boxed; arrows lead to the highlighted selected result row. Search/Clear and claimant-name, SSN, DOB and case-number search labels are visible; result values omitted.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 80 -- Unity – Claimant Address
**System / screen:** Unity > Claimant Address
**Process:** Unity
**Actor:** mixed
**Instructions:**
BOT will click Validate Address if there is not a green check mark next to that button already.
After selecting Validate Address and a window appears with a suggested Address, the BOT should pause and instruct BOT Runner to engage CPD management for assistance.  Changing data here will cause Complete Task failures.
If Address validates a green check mark will appear.
If the Social Security Number begins with 999, it is considered invalid. In this scenario, the BOT will clear the Social Security Number field to allow Unity processing to continue.
**Screenshot [from screenshot]:** Unity claimant form: red box marks Validate Address and arrow leads to a Suggested Address versus Original Address modal with Show Map and boxed Use. A second crop highlights Social security number and its invalid-value message; values omitted.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE]

## Slide 81 -- Unity – Appt Date and Time
**System / screen:** Unity > Appt Date and Time
**Process:** Unity
**Actor:** mixed
**Instructions:**
In the Medical Provider Appointment section, BOT will review the following:
Does the claimant have an appointment with a medical provider? Yes if there is an appointment, No if there is no appointment
Appointment date and time should have populated from RRS, verify they match the referral instructions.
If the appointment information was entered in RRS but did not populate in Unity, add the Appointment Date and Time and Time Zone of provider location.
If no appointment date or time is provided in the referral and is a requirement for assignment of the referral, click Flag  and select Missing information and enter in the description Missing Provider appointment date/time.  BOT Runner will need to manually intervene to complete obtaining missing information and Complete Task.
**Screenshot [from screenshot]:** Two Unity Medical Provider Appointment captures: red boxes and arrows link empty to populated Appointment Date and Appointment Time fields; Yes/No appointment choice, Time Zone and Search Provider are visible.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE] [AGENT-ONLY]

## Slide 82 -- Unity – Provider Address
**System / screen:** Unity > Provider Address
**Process:** Unity
**Actor:** mixed
**Instructions:**
The BOT will click Validate Address if there is not a green check mark next to that button already.
After selecting Validate Address and a modal appears with a suggested Address, the BOT should pause and instruct the BOT runner to engage CPD management for assistance.  Changing data here will cause Complete Task failures.
If Address validates a green check mark will appear.
**Screenshot [from screenshot]:** Unity provider information: boxed Validate Address leads to a suggested/original address modal with boxed Use; green validation check appears by the button in the form.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE]

## Slide 83 -- Unity – Provider Address
**System / screen:** Unity > Provider Address
**Process:** Unity
**Actor:** mixed
**Instructions:**
If the Provider Address is invalid, bot will click the Add new Provider button and fill out the correct information.
If the Provider Address search is still invalid, BOT will stop and shows a prompter that the address is invalid with Google Maps search.
If the Provider Address search is valid, this window will appear and bot will click the Use button and select the recommended Google address.
**Screenshot [from screenshot]:** Three Unity provider captures: Add new Provider boxed at left; Validate Address and its Google Maps failure message boxed at upper right; lower address-comparison modal boxes Use for the recommended address.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE]

## Slide 84 -- Unity – Provider
**System / screen:** Unity > Provider
**Process:** Unity
**Actor:** mixed
**Instructions:**
Provider section should auto fill from RRS.
If not populated and Provider was included in RRS, BOT will perform same search, select and/or add criteria as in RRS.
If populated BOT will review and confirm details match referral.
If Unity shows error for Address validation, BOT must pause and alert BOT Runner to correct provider address validation error. Once BOT Runner completes correction BOT may resume.
**Screenshot [from screenshot]:** Unity Medical provider appointment: red outline encloses Search Provider and Add new Provider. Appointment Date, Time and Time Zone are empty and show required validation; Yes is selected for appointment.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE]

## Slide 85 -- Unity - Attorney
**System / screen:** Unity > Attorney
**Process:** Unity
**Actor:** BOT
**Instructions:**
If the Claimant Attorney did  auto populate BOT will review and confirm details
If the Claimant Attorney did not auto populate from RRS when task was created then, If the claimant has an attorney at the time of referral, BOT will select Yes. If not, select No.
If the attorney information is already populated in Unity, BOT will review and confirm the details.
If the attorney was entered in RRS but did not populate in Unity, BOT will click the Search Attorney magnifying glass icon to look up the attorney record manually.
If the attorney is not found in the search results but is listed on the referral document, BOT will click Add New Attorney and manually enter the attorney’s information. (Need to know BOT process on New Attorney adds if address validation fails?)
**Screenshot [from screenshot]:** Unity claimant-attorney form: Yes/No choice, boxed Search Attorney and Add new Attorney and existing-card Remove; the second capture shows name, firm, contact, address and Validate Address fields with required-field errors.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 86 -- Unity – Attachment
**System / screen:** Unity > Attachment
**Process:** Unity
**Actor:** BOT
**Instructions:**
In Unity, navigate to the Attachments section.
You can upload the exported referral file in either of the following ways:
Option 1: Click Select files…, browse to your desktop folder RRS_Referral_Export, select the referral email file, then click Open.
Option 2: Drag and drop the referral email file directly into the upload area.
Once uploaded, the file will appear in the Attached Files list.
**Screenshot [from screenshot]:** Unity Attachments panel: red boxes mark Select files…, drag-and-drop upload area, the selected referral email file in the Windows Open dialog and Open. Arrows connect both upload options to the Attached Files list.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 87 -- Unity – Attachment
**System / screen:** Unity > Attachment
**Process:** Unity
**Actor:** BOT
**Instructions:**
After the file is selected, it will appear under the Attached Files section. BOT will confirm that the referral email file is listed. This means the file has been successfully uploaded and is now ready to be submitted or processed in Unity.
**Screenshot [from screenshot]:** Unity Attachments: a red box encloses the uploaded file row in Attached Files, with Remove and Download controls; the upload target remains visible.
**Speaker notes:** none
**Tags:** none

## Slide 88 -- Unity – Customer Defined Fields
**System / screen:** Unity > Customer Defined Fields
**Process:** Unity
**Actor:** mixed
**Instructions:**
After selecting the customer, the Customer Defined Fields section will become available. Required fields such as Date of First Appointment and Claim Identifier (Referral Id in the PDF referral) must be entered based on the referral document.
The BOT will pause for validation to ensure all required customer-defined fields are completed accurately.
**Screenshot [from screenshot]:** Unity Customer defined fields: first capture shows the Liberty Mutual Commercial Market field group; second red box encloses Date of First Appointment date/time and Claim Identifier entry fields.
**Speaker notes:** none
**Tags:** [PAUSE]

## Slide 89 -- Unity – Employer Defined Fields
**System / screen:** Unity > Employer Defined Fields
**Process:** Unity
**Actor:** mixed
**Instructions:**
After the employer is entered in Unity, the Employer Defined Fields section will automatically appear in the left navigation when applicable. The BOT will pause for manual validation.
**Screenshot [from screenshot]:** Unity Employer defined fields selected in left navigation; the form shows yes/no fields and a Facility dropdown boxed in red, with Notes and special instructions below.
**Speaker notes:** none
**Tags:** [PAUSE]

## Slide 90 -- Unity – Complete Task
**System / screen:** Unity > Complete Task
**Process:** Unity
**Actor:** BOT
**Instructions:**
BOT will review the referral notes to ensure all Special Instructions from the referral email have been transferred correctly into Unity, update the note if anything has been missed.
**Screenshot [from screenshot]:** Unity Notes and special instructions text area sits below the Referral Details/Export, Release task, Delete task and Complete task buttons; Case Supervisor and Requested case manager fields appear below. Note contents omitted.
**Speaker notes:** none
**Tags:** none

## Slide 91 -- Unity – Bilingual CM Requested
**System / screen:** Unity > Bilingual CM Requested
**Process:** Unity
**Actor:** BOT
**Instructions:**
Bilingual CM Requested: BOT will Ensure toggle box is marked correctly based on what was entered into the RRS SLB.
**Screenshot [from screenshot]:** Unity Notes and special instructions: yellow outline emphasizes Bilingual CM Requested? Yes/No toggle, with No visibly selected.
**Speaker notes:** none
**Tags:** none

## Slide 92 -- Unity – Requested Case Manager
**System / screen:** Unity > Requested Case Manager
**Process:** Unity
**Actor:** mixed
**Instructions:**
If there is a Requested Case Manager AND the branch has approved assignment to the requested case manager, then type in first 3-4 letters of case manager’s first name and select the matching case manager name.  BOT Must make sure correct case manager having corresponding state corresponding to branch assigning referral or MHAA tag is selected. See Standard Intake rules for details.
  If case manager is not found in dropdown, but approved by the branch, BOT should check the Requested by Branch Manager box to allow the assigned case manager to show in the drop down and then can be searched/selected.
  If there is a Requested Case Manger but the branch has not approved assignment to the requested case manager and the case manager is not in the dropdown, BOT should Flag task for ‘Manual Assignment Needed’ BEFORE clicking complete task. BOT or BOT Runner will then need generate and send out a manual unity advanced notice from RRS to the branch to obtain manual assignment approval.
If no requested Case Manager, then confirm on Liberty Mutual Workflow cheat sheet if referral is eligible for auto assignment, If NOT then Flag referral for Manual case manager assignment BEFORE clicking complete task. If not eligible for auto assignment, BOT or BOT Runner will then need  to generate and send out a manual unity advanced notice from RRS to the branch to obtain manual assignment.
**Screenshot [from screenshot]:** Unity task form: highlighted Requested by Branch Manager checkbox, Requested case manager search and Assigned date; Case Supervisor and Requested case management company fields nearby. Yellow callouts emphasize manual advance notice.
**Speaker notes:** none
**Tags:** [DECISION] [CUSTOMER-RULE-DOC]

## Slide 93 -- Unity – Flag and Complete Task
**System / screen:** Unity > Flag and Complete Task
**Process:** Unity
**Actor:** mixed
**Instructions:**
If required information is missing in Unity, select Flag and choose the appropriate reason from the list.
Provide a brief description of the issue before flagging the referral.
Once BOT has finalized Unity review, it will prompt the BOT Runner to do a Final Check. Once the BOT Runner approves that the Unity referral is ready to be submitted then the BOT will click Complete Task.
**Screenshot [from screenshot]:** Unity Intervention Task Details: Flag link boxed and problem dialog shows Missing information, New customer, New employer, Max Case Load Override Required, Manual Assignment Needed and Other, plus description and Flag Referral. A second red box marks Complete task.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE]

## Open questions
- Slide 71 uses supervisor-access screenshots and says agent-access screenshots remain to be supplied.
- Slide 74 asks whether employer review/selection is performed by BOT or BOT Runner; CEM process is not supplied.
- Slides 77 and 85 ask what to do when a newly added attorney fails address validation.
- Slides 82–83 conflict: pause for CPD management on a suggested provider address versus select and Use the recommended Google address.
- Slide 92 refers to Standard Intake rules and Liberty Mutual Workflow cheat sheet, neither included.
