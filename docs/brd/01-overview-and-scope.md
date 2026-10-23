# Overview and scope
> Source: V4 RRS-Unity-CMS BRD Consolidated (slides 1-4). Converted from the owner's BRD. Screenshot descriptions are marked [from screenshot]; everything else is the BRD's own text.
## Summary
The BRD defines the Liberty Mutual case-intake-registration scope and the prerequisites for BOT assignment in RRS. It describes the iCase referral handoff, the Reopen and Like Item eligibility gates, and cases excluded from this phase. Human BOT Runner review determines whether some referrals may continue; an RRS code change or attended trigger is unresolved. Eligible referrals proceed to RRS intake.
## Flow
1. [[#Slide 1 -- Cover|Cover]]
2. [[#Slide 2 -- BOT referral identification and scope|BOT referral identification and scope]]
3. [[#Slide 3 -- Out of Scope for this phase|Out of Scope for this phase]]
4. [[#Slide 4 -- BOT referral eligibility and assignment|BOT referral eligibility and assignment]]

## Slide 1 -- Cover
**System / screen:** Presentation cover
**Process:** Overview
**Actor:** mixed
**Instructions:**
August 2026

Case Intake Registration – Liberty Mutual

Business Transformation
**Screenshot [from screenshot]:** No application screenshot; presentation cover with title and brand artwork.
**Speaker notes:** none
**Tags:** none

## Slide 2 -- BOT referral identification and scope
**System / screen:** RRS > Inbox; iCase; CMS
**Process:** Overview
**Actor:** mixed
**Instructions:**
This slide has been inserted to include documentation how the BOT should identify a referral to work on
- Know that a RRS code change will be necessary to support the automation of this process as all work is currently assigned via the dispatch tool or manually by a supervisor or manager who is responsible for managing the RRS Inbox.
- Once the referral email is selected and it is determined that there is an iCase link in the message body the BOT code needs to click the link, pause to permit BOT Runner to enter credentials and multifactor authentication. The Referral PDF will need to be downloaded and attached to the main referral in RRS. The vendor instruction PDF received on that main referral email will need to be deleted.
- Then the BOT will need to: check for referral types requiring processing by the BOT Runner such as those noted below (and on instructions provided), perform the Reopen check and the Like Item search.  When the BOT confirms it is “BOT Eligible” it can continue to next pages in this PPT.
- Out of Scope for this phase:
  - Referral types that Genex is not permitted to service (this is captured in the rules documentation)
  - SCAH (Serious Case After Hours), LM Rush Staffing, Catastrophic, or any referral email that does not contain a link to iCase Management.
- The Reopen check must be performed to determine if the referral is a reopen or new referral as Reopens are out of scope at this time since they follow a different workflow. (this is in the rules documentation)
- The Like Item search must be performed at start of the referral processing because any Liberty referral containing the iCase link may have a manual referral that was received on a prior date and is pending in the RRS Inbox awaiting receipt of the iCase Referral to complete the next action steps.
**Screenshot [from screenshot]:** No application screenshot. Branded text slide with indented Out of Scope bullets.
**Speaker notes:** none
**Tags:** [RULE] [DECISION] [PAUSE] [OUT-OF-SCOPE] [RRS-CODE-CHANGE] [CUSTOMER-RULE-DOC]

## Slide 3 -- Out of Scope for this phase
**System / screen:** RRS > View Inbox; CMS > Reopen / Like Item
**Process:** Overview
**Actor:** mixed
**Instructions:**
- Out of Scope for this phase:
  - Referral types that Genex is not permitted to service (this is captured in the rules documentation – Liberty Mutual Workflow Cheat Sheet)
  - Referrals identified as: SCAH (Serious Case After Hours), LM Rush Staffing, Catastrophic, or any referral email that does not contain a link to iCase Management.
  - can be seen in the view inbox
  - Reopens or Duplicate referrals:
    - Referrals having a prior FCM case that has been closed within the last 365 days or is currently open, must be reviewed by the BOT Runner to determine if the referral is a reopen or duplicate before proceeding.
    - BOT Runner should be permitted to determine if BOT can move to next step.
  - Any referral having results in the Like Item search must be reviewed by the BOT Runner to determine if BOT can continue.
**Screenshot [from screenshot]:** No application screenshot. Text-only nested bullets; the “can be seen in the view inbox” line is highlighted green.
**Speaker notes:** none
**Tags:** [RULE] [DECISION] [PAUSE] [OUT-OF-SCOPE] [CUSTOMER-RULE-DOC]

## Slide 4 -- BOT referral eligibility and assignment
**System / screen:** RRS > Inbox / dispatch
**Process:** Overview
**Actor:** mixed
**Instructions:**
How the BOT should identify a referral eligible for BOT processing
- NOTE: A RRS code change will be necessary to support the automation of this process as all work is currently assigned via the dispatch tool or manually by a supervisor or manager who is responsible for managing the RRS Inbox. Else the BOT Runner would need to trigger a BOT to do the following.  This step is to be determined once end to end BOT design is completed.
**Screenshot [from screenshot]:** No application screenshot or callouts; text-only design note.
**Speaker notes:** none
**Tags:** [RULE] [DECISION] [RRS-CODE-CHANGE]

## Open questions
The BRD cites rules documentation and the Liberty Mutual Workflow Cheat Sheet, which are not included here. Slides 2 and 4 leave assignment automation versus BOT Runner trigger undecided. Slides 2–3 call reopens out of scope but also allow BOT Runner review of prior open/recently closed cases; the boundary between review and BOT continuation needs confirmation.
