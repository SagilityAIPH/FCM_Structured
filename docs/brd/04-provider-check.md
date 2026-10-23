# Provider information check
> Source: V4 RRS-Unity-CMS BRD Consolidated (slides 19-21). Converted from the owner's BRD. Screenshot descriptions are marked [from screenshot]; everything else is the BRD's own text.
## Summary
The BOT checks the referral PDF for complete provider address details and searches for missing information. It opens the Subject Line / Template Builder from RRS, uses provider search criteria and validates potential matches with a second Google search. The checked provider information supports the following Subject Line Builder email-template workflow. The instructions give a fallback when the initial facility-and-phone search yields too many or no results.
## Flow
1. [[#Slide 19 -- Checking provider information|Checking provider information]]
2. [[#Slide 20 -- Checking provider information - RRS|Checking provider information - RRS]]
3. [[#Slide 21 -- RRS - Email Display|RRS - Email Display]]

## Slide 19 -- Checking provider information
**System / screen:** Referral PDF > Special Instructions; provider lookup
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
This sample has missing provider Zip code. If there is any missing information such as address, state, zip, the next step will be searching the correct and full information through RSS 1st then google.
**Screenshot [from screenshot]:** Two PDF excerpts: left Special Instructions has Address of Appt. location boxed orange-red with arrow, amid Provider Name, Phone, Email, Appt. Date | Time, Employer and clinical-objective labels; right excerpt boxes address beneath Provider Name and Phone, with arrow, amid ASSIGNMENT TYPE, Employer, Atty Permission and WORK STATUS labels. No field values transcribed.
**Speaker notes:** none
**Tags:** [RULE] [DECISION]

## Slide 20 -- Checking provider information - RRS
**System / screen:** RRS > Email Display > Subject Line / Template Builder; provider search
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
BOT will click the Subject Line / Template Builder button.
This will open the Subject Line Builder Email Display to use the provider search

1. Enter First 2 word of facility and Phone Number. If result is greater than 10 or no result is found, do step 2.
2. Add City, State and Zip to the criteria.

If results shown after searching, validate each result and check for partial match of the Name, address and phone number. If there is a match, get the information and do a second search in google to bash/validate the results. If there is a match in google search, use that as the provider information. (no screenshot available yet for google search)
**Screenshot [from screenshot]:** Two screenshots: Email Display has Subject Line / Template Builder boxed red and an orange arrow; provider-search form boxes First Name, Last Name, Facility Name, Group Name, Phone, City, State and Zip. Search results grid and Set Provider / Add New Provider buttons visible; no Google screenshot.
**Speaker notes:** none
**Tags:** [RULE] [DECISION]

## Slide 21 -- RRS - Email Display
**System / screen:** RRS > Email Display > Subject Line / Template Builder
**Process:** Subject Line Builder
**Actor:** BOT
**Instructions:**
After reviewing the document, BOT will click the Subject Line / Template Builder button.
This will open the Subject Line Builder Email Display window to create the template for the referral email.
**Screenshot [from screenshot]:** Email Display screenshot shows header fields, attachments and email body; Subject Line / Template Builder button boxed red with orange arrow from instruction. Other attachment and email buttons visible; message, link and attachment values omitted.
**Speaker notes:** none
**Tags:** none

## Open questions
Slide 19 says “RSS 1st then google” but slide 20 identifies an RRS/Subject Line Builder provider search; confirm RSS versus RRS. Slide 20 uses “bash/validate” without defining “bash,” and supplies no Google-search screenshot or explicit resolution for conflicting search results. The rule for when missing provider information cannot be validated is unstated.
