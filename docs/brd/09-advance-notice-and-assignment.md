# Advance notice and assignment
> Source: V4 RRS-Unity-CMS BRD Consolidated (slides 94-101). Converted from the owner's BRD. Screenshot descriptions are marked [from screenshot]; everything else is the BRD's own text.
## Summary
After Unity task completion, RRS receives a Unity notification and an advance notice coordinates case-manager assignment. The BOT Runner or branch performs assignment and the runner accepts or rejects the referral in iCase. RRS Complete Assignment records UnityComplete and the CMS case ID before the supervisor hands the case to registration.
## Flow
1. [[#Slide 94 -- RRS Advance Notice|Slide 94 -- RRS Advance Notice]]
2. [[#Slide 95 -- RRS UnityPending|Slide 95 -- RRS UnityPending]]
3. [[#Slide 96 -- RRS – How to Send A Unity Advanced Notice|Slide 96 -- RRS – How to Send A Unity Advanced Notice]]
4. [[#Slide 97 -- iCase Assignment|Slide 97 -- iCase Assignment]]
5. [[#Slide 98 -- iCase Expanded View|Slide 98 -- iCase Expanded View]]
6. [[#Slide 99 -- RRS – Complete Assignment|Slide 99 -- RRS – Complete Assignment]]
7. [[#Slide 100 -- CMS – Case Number|Slide 100 -- CMS – Case Number]]
8. [[#Slide 101 -- RRS – Complete Assignment|Slide 101 -- RRS – Complete Assignment]]

## Slide 94 -- RRS Advance Notice
**System / screen:** RRS > Advance Notice
**Process:** RRS intake
**Actor:** mixed
**Instructions:**
After completing the task in Unity, an Advance Notice email will be auto generated to assign a case manager.
This process may take up to 2 hours. Once a case manager has been assigned, the task will continue automatically.
Once the case manager is assigned in Unity, a Unity Notification will generate and be sent into RRS. The RRS box supervisor will associate the unity notification to the main referral and place in the BOT Runner’s hold/pending box. BOT Runner will accept the referral in iCase and place the referral in a UnityComplete status. BOT can proceed to CMS Registration.
**Screenshot [from screenshot]:** Upper RRS Email Body View boxes the advance-notice message header. Lower RRS assignment screen boxes Assign status UnityComplete; Complete Assignment and other workflow buttons visible. Email personal details omitted.
**Speaker notes:** none
**Tags:** [AGENT-ONLY]

## Slide 95 -- RRS UnityPending
**System / screen:** RRS > UnityPending
**Process:** RRS intake
**Actor:** mixed
**Instructions:**
If the status remains UnityPending (after 10 min) the BOT or BOT Runner needs to verify the Unity Task fallout reason. If the fallout is in NoCaseManagerTask and no automated unity advanced notice has been issued then, click Complete Assignment button. From the Assignment Menu, select option 23 – Send Unity No CM Advance Notice.
If the Untiy Task fallout reason is NOT NoCaseManagerTask, BOT will need to prompt BOT Runner to resolve or to engage CPD Management for assistance.
**Screenshot [from screenshot]:** RRS assignment screen boxes UnityPending and Complete Assignment; an arrow leads to Assignment Menu option 23 – Send Unity No CM Advance Notice boxed in red, with OK/Cancel.
**Speaker notes:** none
**Tags:** [DECISION] [PAUSE]

## Slide 96 -- RRS – How to Send A Unity Advanced Notice
**System / screen:** RRS > How to Send A Unity Advanced Notice
**Process:** RRS intake
**Actor:** mixed
**Instructions:**
After clicking Complete Assignment, the Assignment Menu will popup, select option 1 Genex in the Assign Input window then click OK. The Unity Advanced Notice email will generate (branch contacts should be pre-filled into email), BOT or BOT Runner will hit send on generated email from Outlook.
**Screenshot [from screenshot]:** RRS Assignment Menu boxes option 23 – Send Unity No CM Advanced Notice; the following Assign Input dialog boxes 1. Genex (versus 2. Affiliate), with OK/Cancel.
**Speaker notes:** none
**Tags:** none

## Slide 97 -- iCase Assignment
**System / screen:** iCase > Assignment
**Process:** RRS intake
**Actor:** mixed
**Instructions:**
Upon Assignment, the BOT Runner will claim and assign the task in Unity or the branch will assign via the automated Unity Link email. A Unity Notification will generate and send out to the customer and RRS. The RRS box supervisor will associate the Unity Notification to the main referral and place in the BOT Runner’s hold under assignment. The BOT Runner will then follow the below to accept the referral in iCase.
Next, BOT runner will go back to iCase page to do the Accept or Reject the referral
Login using username and password, complete the MFA (Multi-Factor Authentication) when prompted, as this is required for all agents.
Once logged in, a pop-up message will appear stating “Please accept or reject this referral.”
Simply click OK to proceed.
**Screenshot [from screenshot]:** iCase sign-in screenshot boxes username/password form, Remember my username and Sign On; no values transcribed. A second box marks OK on “Please accept or reject this referral” pop-up.
**Speaker notes:** none
**Tags:** [AGENT-ONLY]

## Slide 98 -- iCase Expanded View
**System / screen:** iCase > Expanded View
**Process:** RRS intake
**Actor:** mixed
**Instructions:**
In the Expanded View page in iCase, the Bot will pause for manual intervention so the agent can determine whether the referral should be accepted or rejected. Once the decision is made, select the appropriate option and click Submit to allow the bot to continue processing.
**Screenshot [from screenshot]:** iCase Expanded View: red boxes mark Accept/Reject radio buttons and Submit; View Referral and expandable Claims Documentation also visible. Selection not legible as made.
**Speaker notes:** none
**Tags:** [PAUSE] [DECISION] [AGENT-ONLY]

## Slide 99 -- RRS – Complete Assignment
**System / screen:** RRS > Complete Assignment
**Process:** RRS intake
**Actor:** mixed
**Instructions:**
Tick the checkbox for the referral you just worked on, then click Complete Assignment.
First, enter the Claimant’s full name and click OK
Next, enter the Claimant Number and click OK
From the Assignment Menu, choose 19 – Unity Complete and click OK.
**Screenshot [from screenshot]:** RRS: boxes mark referral checkbox, Complete Assignment, two sequential input pop-ups and option 19 – Unity Complete in Assignment Menu. The second pop-up visually appears to ask for claimant name, conflicting with slide text saying Claimant Number.
**Speaker notes:** none
**Tags:** none

## Slide 100 -- CMS – Case Number
**System / screen:** CMS > Case Number
**Process:** CMS case setup
**Actor:** BOT
**Instructions:**
Go to CMS and enter the Claim Number in the Claim Number field, then click Search.
After selecting the record, the Claimant Profile page will open.
From the search results, click Select beside the matching claimant record.
Copy the Case Number displayed, enter it in the pop-up in RRS and click OK
A confirmation pop-up will appear asking “Is this referral completed in Unity and is there a CMS Case Number?” Click Yes.
A second pop-up will appear prompting you to enter the CMS Case ID.
**Screenshot [from screenshot]:** RRS Unity Complete? modal boxes Yes and Case Id input/OK; CMS search capture boxes Claim Number and Search, result boxes Select, and Claimant Profile boxes the Case Number location. Values omitted.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 101 -- RRS – Complete Assignment
**System / screen:** RRS > Complete Assignment
**Process:** RRS intake
**Actor:** mixed
**Instructions:**
After clicking OK, the referral will disappear from your inbox.
At this point, the workflow shifts — the supervisor will assign the case to a registration agent who will continue the process from there.
A final pop-up will appear asking “Is there a Unity Notification generated and attached to the referral?" Click Yes.
Another message will then confirm that the referral has been placed in UnityComplete status. Click OK to close the prompt.
**Screenshot [from screenshot]:** RRS final Unity Complete? notification prompt boxes Yes; a second status-confirmation pop-up boxes OK; arrow points to the inbox after removal.
**Speaker notes:** none
**Tags:** [AGENT-ONLY]

## Open questions
- Slides 95–96 show Assignment Menu option 23 before Assign Input option 1; slide 96 text omits explicitly selecting option 23.
- Slide 99 says Claimant Number for the second RRS pop-up, but the screenshot appears to ask for claimant name.
- Slides 94 and 97 vary on who claims/assigns in Unity (BOT Runner or branch), and on who accepts in iCase.
