# CMS Reopen Check and Customer Search
> Source: V4 RRS-Unity-CMS BRD Consolidated (slides 17-18). Converted from the owner's BRD. Screenshot descriptions are marked [from screenshot]; everything else is the BRD's own text.
## Summary
The BOT searches CMS by claim number and checks the matched case status to identify potential reopens. Open or recently closed cases trigger BOT Runner validation before the standard workflow can continue. In CMS Customer Search, the BOT searches the employer name and either matches an existing customer or follows the CEM new-employer process. The resulting employer determination feeds provider checking and subsequent RRS work.
## Flow
1. [[#Slide 17 -- CMS – Reopen Check|CMS – Reopen Check]]
2. [[#Slide 18 -- CMS – Customer Search|CMS – Customer Search]]

## Slide 17 -- CMS – Reopen Check
**System / screen:** CMS > claimant search > claimant profile
**Process:** Reopen-Check
**Actor:** mixed
**Instructions:**
Once the case loads, review the Case Number that appears.
A backend query will check whether this case is marked as Open or Closed. If the system detects an existing open or recently closed case, the BOT Runner should be prompted to verify whether this referral represents a valid reopen request.
If no previous case exists—or no reopen situation applies—simply continue with the standard workflow.

BOT will go to CMS and search using the Claim Number from the referral. After searching, click Select to open the case.
**Screenshot [from screenshot]:** Two CMS screenshots: left search form has Claim Number field and result-row Select control boxed red; right claimant profile has Case Number boxed red. Return to Claimant Listing navigation arrow visible. Search/result identifiers omitted.
**Speaker notes:** none
**Tags:** [RULE] [DECISION] [PAUSE]

## Slide 18 -- CMS – Customer Search
**System / screen:** CMS > Customer Search > Customer Validation
**Process:** CMS Customer Search
**Actor:** BOT
**Instructions:**
The BOT will go to CMS, search for the employer in the customer search to check if it’s a Valid New Employer

If no results are found, the BOT proceeds according to the CEM process for new employer request.

Enter the first 4 characters of the employer's name exactly as it appears on the referral document or the First word of the employer’s name, If the employer appears in the search results, this confirms the employer already exists and is not a new employer.

Enter the valid customer/employer name and click OK.

BOT will automatically select a result if there is a partial match and move to the next step. If BOT is unable to identify a partial match, a validation message will show if there is a valid customer/employer.
**Screenshot [from screenshot]:** Upper-left Customer Search form has Name and Search boxed red; lower-left search results grid shows candidate employers and Select controls. Upper-right validation dialog has Yes and No boxed red; middle-right name-entry dialog has OK and Cancel, with orange connector to instruction. Long orange connector to no-results CEM branch. Query/result/contact values omitted.
**Speaker notes:** none
**Tags:** [RULE] [DECISION]

## Open questions
Slide 17 says runner may verify a valid reopen, but slide 16 says open/recently closed cases are not BOT eligible; clarify whether runner can resume the BOT. Slide 18 does not define the partial-match threshold, how a validation answer is chosen, or the CEM new-employer process; source process document not included.
