# RRS Complete Triage and Unity Export
> Source: V4 RRS-Unity-CMS BRD Consolidated (slides 65-68). Converted from the owner's BRD. Screenshot descriptions are marked [from screenshot]; everything else is the BRD's own text.
## Summary
The BOT selects the referral in the RRS Referral Routing System, populates Email Body View, and starts Complete Triage. It enters the ZIP code appropriate to the service type and confirms completeness and customer identity. An incomplete referral is routed to an agent hold/pending box for BOT Runner takeover. A successful Unity Entry can export an email referral template to the desktop folder for later attachment in Unity.
## Flow
1. [[#Slide 65 -- RRS – Complete Triage|RRS – Complete Triage]]
2. [[#Slide 66 -- RRS – Zip Code|RRS – Zip Code]]
3. [[#Slide 67 -- RRS - Options|RRS - Options]]
4. [[#Slide 68 -- RRS - Unity Entry|RRS - Unity Entry]]

## Slide 65 -- RRS – Complete Triage
**System / screen:** RRS > Referral Routing System > Complete Triage
**Process:** RRS intake
**Actor:** BOT
**Instructions:**
In the Referral Routing System window, BOT will tick the check box in the table

After ticking the checkbox, the email content from the Email Display window will populate in the Email Body View

Then, the BOT will click the Complete Triage button to begin next step for referral processing.

**Screenshot [from screenshot]:** Referral Routing System table boxes the row-selection checkbox (appears unchecked); separate red boxes mark Email Body View and Complete Triage. Blue callout arrows connect the selection to the email body pane and the button.
**Speaker notes:** none
**Tags:** none

## Slide 66 -- RRS – Zip Code
**System / screen:** RRS > Zip Code?
**Process:** RRS intake
**Actor:** BOT
**Instructions:**
If the Service Type is Med/Medical Task, you need the get the provider’s zip code.For Vocational Task type referral, you need the get the claimant’s zip code.

After clicking the Complete Triage button, the BOT will enter the appropriate zip code.
Generally, the Provider zip code is entered however there are exceptions to this rule which are related to the specific referral type selected.

Enter the Provider’s Zip code for the claimant and then click OK.

In this case, the service type is Med/Full Med.

**Screenshot [from screenshot]:** Referral Routing System source excerpt boxes provider information; Zip Code? popup boxes a populated ZIP input and OK button (Cancel also visible). Blue arrow connects input and instruction. The example is Med/Full Med; ZIP value is not transcribed.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 67 -- RRS - Options
**System / screen:** RRS > Information Complete? / Customer Check / reachout status
**Process:** RRS intake
**Actor:** mixed
**Instructions:**
After entering the Zip code and clicking OK, a confirmation pop up will show if the information is enough/complete

If information is enough/complete, BOT will click Yes

Another pop-up confirmation will show for Customer Check. If the customer is set correctly and it is in the subject line, BOT will click Yes.

After clicking yes, a confirmation pop up will show informing that the referral is now entered in Unity.

If BOT clicks No, BOT will select the correct reachout status and click OK. This will move the referral into the agents hold/pending box.

BOT Runner must take over from here

**Screenshot [from screenshot]:** Information Complete? popup boxes Yes and No. Blue arrows trace Yes to Customer Check popup (Yes/No), then Unity-entry confirmation with OK; No goes to ReferralRoutingSystem reachout-status popup with Branch, Adjuster, Provider and Phone Reachout options, OK and Cancel, and a yellow BOT Runner takeover callout.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE] [AGENT-ONLY]

## Slide 68 -- RRS - Unity Entry
**System / screen:** RRS > Unity Entry > Export Referral
**Process:** RRS intake
**Actor:** BOT
**Instructions:**
In the Unity Entry window, click the Export Referral button.

This action will generate and export the email referral template. The exported file will be saved in your desktop folder RRS_Referral_Export, ready to be attached in Unity.

**Screenshot [from screenshot]:** Unity Entry window boxes Export Referral below received/recipient, subject, attachments and referral detail controls. Blue arrow points to export explanation, then confirmation dialog with OK and File Explorer view of RRS_Referral_Export containing the exported email template; no filename or personal values transcribed.
**Speaker notes:** none
**Tags:** none

## Open questions
- Slide 66 says the ZIP entry is generally the provider ZIP with referral-type exceptions but explicitly specifies only Med/Medical Task and Vocational Task; other referral types need their source rule.
- Slide 67 does not specify the correct reachout status for each incomplete-information condition or what to do if Customer Check is No.
- Slide 68 says Export Referral produces a desktop email template; its filename and subsequent attachment mechanism are not specified in this range.
