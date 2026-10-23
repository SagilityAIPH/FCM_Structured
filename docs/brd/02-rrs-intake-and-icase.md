# RRS intake and iCase
> Source: V4 RRS-Unity-CMS BRD Consolidated (slides 5-16). Converted from the owner's BRD. Screenshot descriptions are marked [from screenshot]; everything else is the BRD's own text.
## Summary
The referral is opened and assigned in RRS, then selected from Hold/Pending Referrals by the BOT Runner. The runner opens the iCase link, signs in with MFA, downloads the referral PDF and replaces the vendor-instruction attachment in RRS. The BOT opens the attached referral for completeness and eligibility review. BOT-eligible work proceeds to CMS Reopen Check and Customer Search; exceptions return to the runner for manual processing.
## Flow
1. [[#Slide 5 -- Referral Routing System — View Inbox|Referral Routing System — View Inbox]]
2. [[#Slide 6 -- Referral Routing System — open referral|Referral Routing System — open referral]]
3. [[#Slide 7 -- Referral Routing System — assign referral|Referral Routing System — assign referral]]
4. [[#Slide 8 -- Hold / Pending Referrals|Hold / Pending Referrals]]
5. [[#Slide 9 -- Open Email Display|Open Email Display]]
6. [[#Slide 10 -- Open the iCase link|Open the iCase link]]
7. [[#Slide 11 -- iCase sign-in and referral prompt|iCase sign-in and referral prompt]]
8. [[#Slide 12 -- Download referral PDF|Download referral PDF]]
9. [[#Slide 13 -- Remove vendor-instruction attachment|Remove vendor-instruction attachment]]
10. [[#Slide 14 -- Upload referral PDF|Upload referral PDF]]
11. [[#Slide 15 -- Open attached referral document|Open attached referral document]]
12. [[#Slide 16 -- BOT review of referral PDF|BOT review of referral PDF]]

## Slide 5 -- Referral Routing System — View Inbox
**System / screen:** RRS > main menu > View Inbox / Inbox
**Process:** RRS intake
**Actor:** Agent
**Instructions:**
Click the View Inbox button to open your referral inbox.

After selecting View Inbox, the system will display the Inbox window (shown in the second image).
This inbox contains all incoming referrals.
**Screenshot [from screenshot]:** Two RRS screenshots: View Inbox button boxed red in main menu; orange arrow connects it to the Inbox grid of incoming referrals on the right. Inbox search/filter and assignment controls visible; no referral values transcribed.
**Speaker notes:** none
**Tags:** none

## Slide 6 -- Referral Routing System — open referral
**System / screen:** RRS > Case Reg Inbox SPV > Referral Information
**Process:** RRS intake
**Actor:** Agent
**Instructions:**
From the Inbox, locate the referral you want to process. Double-click the referral row to open the Referral Information Window.

Once the referral window opens, scroll to the email body section. There you will find a hyperlink that directs you to the iCase website.
Click this link to open the referral in iCase and download the referral document that must be attached to this case.
**Screenshot [from screenshot]:** Inbox row boxed red on left; orange arrow points to Referral Information on right. Link in email body boxed red; upper referral fields and lower attachment/email sections visible.
**Speaker notes:** none
**Tags:** none

## Slide 7 -- Referral Routing System — assign referral
**System / screen:** RRS > Inbox > Assignment
**Process:** RRS intake
**Actor:** Agent
**Instructions:**
Next, assign the referral.
Tick the checkbox on the referral row you want to assign. Then select the correct Agent’s name from the Agent dropdown and click the Assignment button.
**Screenshot [from screenshot]:** Selected referral row, row checkbox, Agent dropdown and Assignment button highlighted by colored boxes and orange guide lines. Triage, Assign and Reg options visible.
**Speaker notes:** none
**Tags:** none

## Slide 8 -- Hold / Pending Referrals
**System / screen:** RRS > Hold / Pending Referrals > Items on Hold
**Process:** RRS intake
**Actor:** BOT Runner
**Instructions:**
BOT Runner will click on Hold/Pending Referrals box.
Double Click on the referral line item located in the Items on Hold window with a HOLD status under the Triage column.
Note: There could be multiple items in this view so this process will repeat as new referrals are selected to be worked.
**Screenshot [from screenshot]:** Small panel has Hold / Pending Referrals button with Hold = 1; Items on Hold grid has a red-boxed referral row with Triage cell HOLD. Pending Items and SPV Item sections indicate no referrals.
**Speaker notes:** none
**Tags:** none

## Slide 9 -- Open Email Display
**System / screen:** RRS > referral grid > Email Display
**Process:** RRS intake
**Actor:** BOT Runner
**Instructions:**
BOT Runner will double click the row to open the email form.
This will open the Email Display window to view the email and the attachments.
**Screenshot [from screenshot]:** RRS referral row boxed red with orange arrow toward it; Email Body View pane below. Email Display is the result of double-clicking but is not pictured on this slide.
**Speaker notes:** none
**Tags:** none

## Slide 10 -- Open the iCase link
**System / screen:** RRS > Email Display > email body
**Process:** RRS intake
**Actor:** BOT Runner
**Instructions:**
BOT Runner will click on 1st link in the body of the email. This will take you out to the iCase website to proceed with the log in credential process to gain access to the referral.
**Screenshot [from screenshot]:** Email Display shows header fields, attachment list and two hyperlinks in the email body; first link is the iCase route, second is an attachment-view link. Expand control shows a left-pointing arrow. Link targets and message values omitted.
**Speaker notes:** none
**Tags:** none

## Slide 11 -- iCase sign-in and referral prompt
**System / screen:** iCase > Sign On / referral alert
**Process:** RRS intake
**Actor:** BOT Runner
**Instructions:**
BOT Runner will use their iCase credentials to sign in.
After entering username and password, complete the MFA (Multi-Factor Authentication) when prompted, as this is required for all agents.

Once logged in, a pop-up message will appear stating “Please accept or reject this referral.”
Simply click OK to proceed.
**Screenshot [from screenshot]:** Left browser screenshot has red-boxed sign-in form with username and password fields, Remember my username checkbox, Sign On button and help link; [credential shown -- not transcribed]. Right screenshot has alert to accept or reject a referral, with OK boxed red. No URLs or entered values transcribed.
**Speaker notes:** none
**Tags:** [PAUSE]

## Slide 12 -- Download referral PDF
**System / screen:** iCase > View Referral > browser PDF viewer
**Process:** RRS intake
**Actor:** BOT Runner
**Instructions:**
Once the PDF opens in a new tab, download and save it to your desktop (or any preferred location). This saved PDF will be attached later in RRS as part of the referral processing steps.

BOT Runner will click View Referral to open the referral document in PDF format.
**Screenshot [from screenshot]:** Left iCase view has View Referral link and PDF icon boxed red; orange arrow points to the PDF opened in a new browser tab on the right. PDF viewer toolbar shows download/save, print, page and zoom controls; PDF contents omitted.
**Speaker notes:** none
**Tags:** none

## Slide 13 -- Remove vendor-instruction attachment
**System / screen:** RRS > Email Display > Attachments
**Process:** RRS intake
**Actor:** BOT Runner
**Instructions:**
In the Email Display window and before attaching the referral, BOT Runner will locate the vendor instruction attachment listed under the Attachments section, select it, and remove it by clicking Delete Item button.
**Screenshot [from screenshot]:** Attachment row selected with checkbox checked; Deleted Items button boxed red. Remove and Upload Docs buttons also visible. Filename and identifying values omitted.
**Speaker notes:** none
**Tags:** none

## Slide 14 -- Upload referral PDF
**System / screen:** RRS > Email Display > Upload Docs
**Process:** RRS intake
**Actor:** BOT Runner
**Instructions:**
In the Email Display window, BOT Runner will click the Upload Docs button to attach the referral PDF.

Select the saved referral document from your computer and click Open.

A pop-up message will appear confirming the upload (e.g., “1 file(s) uploaded”). Click OK to continue.
**Screenshot [from screenshot]:** Three screenshots: Email Display with Upload Docs boxed red; operating-system file picker with Open button; upload-confirmation dialog with OK button. Selected file path and filename omitted.
**Speaker notes:** none
**Tags:** none

## Slide 15 -- Open attached referral document
**System / screen:** RRS > Email Display > Attachments
**Process:** RRS intake
**Actor:** BOT
**Instructions:**
BOT will open the document attached to this email form.
In this scenario, this is the referral form and needs to be reviewed for completeness like provider information, appointment demographic, the customer, the adjuster etc.
**Screenshot [from screenshot]:** Referral PDF row boxed red in Email Display attachment list, with orange arrow from instructions pointing to it. Header, message body and attachment-management controls visible; filename and personal values omitted.
**Speaker notes:** none
**Tags:** [RULE]

## Slide 16 -- BOT review of referral PDF
**System / screen:** Referral PDF; RRS > Like Item; CMS > Reopen Check
**Process:** RRS intake
**Actor:** mixed
**Instructions:**
- The BOT will review the referral pdf to:
  - Check for referral types requiring processing by an Agent
    - Referral/Service types noted as out of scope on previous slide
    - Any referral/service type that is identified on the Liberty Mutual Workflow Cheat Sheet as not accepted
  - If referral/service type is not permitted/accepted BOT will not continue and will advise BOT Runner that referral is not BOT eligible and they must manually complete the necessary steps.
  - Perform the Reopen check.
    - If BOT identifies a prior FCM case closed within the last 365 days or another open FCM case the BOT will stop and advise the BOT Runner that the referral is not BOT eligible and they must complete the necessary steps.
  - Perform the Like Item search:
    - If items are found in the results, the BOT should advise BOT runner to review additional items to determine if BOT can continue.
      - It is possible to find a manual referral that was received previously and is pending in the RRS Inbox awaiting receipt of the iCase Referral to complete the next action steps. Or there could be a Case manager assignment email OR additional details to attach to the main referral.
    - If BOT Runner determines BOT can continue proceed to next steps.
    - If BOT Runner determines there are additional actions required BOT should stop and permit BOT Runner to complete referral intake process.
- If the referral type is not one that requires processing by an agent AND is not a reopen AND does not have any like item results, the referral is “BOT Eligible” it can continue to next steps.
  - If referral is not ‘BOT Eligible’ the BOT should stop and advise the BOT runner that the referral requires manual processing. The BOT will set the Triage Agent to the BOT Runner’s name and the BOT runner will process the referral without the BOT.
**Screenshot [from screenshot]:** No application screenshot. Text-only nested bullets describing referral eligibility, Reopen and Like Item branches.
**Speaker notes:** none
**Tags:** [RULE] [DECISION] [PAUSE] [OUT-OF-SCOPE] [AGENT-ONLY] [CUSTOMER-RULE-DOC]

## Open questions
Slide 13 calls the action “Delete Item” while the screenshot button is “Deleted Items”; confirm the actual destructive control. Slide 16 references the Liberty Mutual Workflow Cheat Sheet and prior-slide out-of-scope types; source rules document was not included. Slide 16 says a prior open/recently closed case makes the referral not BOT eligible, whereas slides 3 and 17 describe runner validation and possible continuation; clarify precedence. Slide 6 links to iCase before slides 7–10 describe assignment and opening the link again; clarify actual operational order.
