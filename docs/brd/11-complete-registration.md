# Complete Registration
> Source: V4 RRS-Unity-CMS BRD Consolidated (slides 120-123). Converted from the owner's BRD. Screenshot descriptions are marked [from screenshot]; everything else is the BRD's own text.
## Summary
After CMS tabs are finalized, the BOT returns to RRS Complete Reg. Standard completion uses Reg Menu option 3 and produces an Outlook email. An employer-add request through CEM instead uses option 10 and places the referral in CMU for BOT Runner manual update.
## Flow
1. [[#Slide 120 -- RRS – Complete Registration|Slide 120 -- RRS – Complete Registration]]
2. [[#Slide 121 -- RRS Outlook email|Slide 121 -- RRS Outlook email]]
3. [[#Slide 122 -- RRS Employer Request Add|Slide 122 -- RRS Employer Request Add]]
4. [[#Slide 123 -- RRS CMU email|Slide 123 -- RRS CMU email]]

## Slide 120 -- RRS – Complete Registration
**System / screen:** RRS > Complete Registration
**Process:** Complete Registration
**Actor:** BOT
**Instructions:**
After the CMS process, BOT will go back to RRS and click Complete Reg button.
Enter number 3 in the InputBox field box and click OK to finalize the process if all CMS tabs have been finalized.
If Employer Request Add (CEM) was required, then follow slide 117 (CMU process)
**Screenshot [from screenshot]:** RRS workflow screen boxes Complete Reg; subsequent Reg Menu InputBox boxes the value 3 and OK. Other referral/case values omitted.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 121 -- RRS Outlook email
**System / screen:** RRS > Outlook email
**Process:** Complete Registration
**Actor:** BOT
**Instructions:**
An outlook email will show right after selecting case registration CMS complete.
**Screenshot [from screenshot]:** Outlook compose window with Send, To, Cc, Subject and attachment controls; a Notice dialog says “Finished CMS Update for case” with OK. Body warns not to change the subject line when replying; recipient and attachment names omitted.
**Speaker notes:** none
**Tags:** none

## Slide 122 -- RRS Employer Request Add
**System / screen:** RRS > Employer Request Add
**Process:** Complete Registration
**Actor:** mixed
**Instructions:**
After the CMS process, go back to RRS and click Complete Reg button.
BOT will, enter 10 in the InputBox field box if Employer Requested via CEM and click OK. Referral will be placed in CMU status for manual update by the BOT runner
**Screenshot [from screenshot]:** RRS workflow screen shows Complete Reg; subsequent Reg Menu boxes option 10 – Employer Request Add, InputBox value 10 and OK, with Cancel alongside.
**Speaker notes:** none
**Tags:** [DECISION]

## Slide 123 -- RRS CMU email
**System / screen:** RRS > CMU email
**Process:** Complete Registration
**Actor:** BOT
**Instructions:**
An outlook email will show right after selecting Employer Request Add. Referral will be placed in CMU status
**Screenshot [from screenshot]:** Outlook compose window with Send, From/To/Cc/Subject and attachments; body warns not to change the subject line while replying. Inset shows Hold / Pending Referrals and CMU status; personal addresses/attachment names omitted.
**Speaker notes:** none
**Tags:** none

## Open questions
- Slide 120 directs Employer Request Add to slide 117 for the CMU process, but this deck puts that path on slides 122–123.
- Slides 121 and 123 show Outlook draft messages but do not expressly state whether BOT sends them or who approves recipients.
