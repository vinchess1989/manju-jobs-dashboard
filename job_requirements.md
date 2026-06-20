# Job Search Requirements

## Candidate Profile
* **Name:** Manju
* **Current Role:** Unemployed
* **Years of Experience:** 2 years
* **Background:** Law degree completed in India (international degree in English). Currently located in Finland and completing supplementary courses in Finnish to obtain equivalence/qualification for a Finnish law degree.
* **Key Skills:** Corporate Law
* **Driving:** Has a valid driving license and can use her personal car for work if required.

## Hard Rejections
Immediately discard a job if ANY of the following are true:
* The job title contains "Senior". The candidate does not have enough experience for senior roles.
* The job requires domain-specific technical expertise in any of the following fields: carpentry, electrical work, construction, cooking/chef, security guard, special education, nursing, or teaching. Discard even if the role appears entry-level.
* The job is a trade or manual-labour role requiring specific vocational training, such as: welding (hitsaaja, TIG-hitsaaja), metalwork/fabrication (särmääjä, koneistaja), scaffold assembly (telineasentaja), asbestos/demolition work, crane/heavy equipment operation, refrigeration installation (kylmäasentaja), or any similar skilled-trade position. These are NOT covered by the "Generalist / No-Requirement Role" exception — they require trade-specific qualifications.
* The job is in the medical or healthcare field requiring clinical training, such as: physician (lääkäri, ylilääkäri), pharmacist (farmaseutti), nurse practitioner, lab technician (laboratoriohoitaja), masseur/physiotherapist (hieroja), or any other role requiring a medical or healthcare degree. Note: "nursing" already covers many of these, but apply this rule broadly to all clinical roles.
* The job title is clearly unrelated to both law and general office/service work — e.g. husky guide, dog handler, pest control specialist, retinal photographer, diver, etc.

## Target Job Criteria

A job is a match if it satisfies the criteria in ALL of the following categories:

**1. Location & Work Model:**
* **Yes Match:** Must satisfy at least ONE of the following:
  * Oulu AND On-site
  * Finland AND Hybrid
  * Fully Remote AND (the location is "Worldwide" OR no specific country is mentioned). Must NOT require US residency.
* **Maybe Match:** If the job is located in a different location in Finland (outside Oulu) and does not have a hybrid/remote option (i.e. on-site in Helsinki, Tampere, etc.), mark it as "maybe" (instead of "no"), provided it satisfies all other criteria.
* **Location Inference:** If the job description is written in Finnish and no location is specified, set/assume the location as Finland.
* **Remote jobs listed under a specific foreign country (UK, USA, Spain, India, etc.):** These do NOT automatically qualify as "Fully Remote / Worldwide". They only qualify if the posting explicitly states it is open to applicants from anywhere / outside that country. If the posting is country-specific (e.g. "Remote – United Kingdom"), treat the location as that country and apply the standard location rules (which will result in "no" for most non-Finland postings).


**2. Domain, Position Type, & Degree Requirements:**
Must satisfy at least ONE of the following valid combinations:
* **Trainee / Internship Role (Legal):** Trainee, internship, or junior legal role, even if it requires a Finnish law degree or Finnish qualification (since she is in Finland and currently doing the supplementary courses needed).
* **English Law Role:** Any legal, compliance, contract management, or corporate law role (permanent, trainee, or contract) that accepts a law degree in English or an international/Indian law degree (without strictly requiring a Finnish qualification).
* **Generalist / No-Requirement Role:** If it's an entry level job and it doesn't require any specific technical degree or experience, consider as a match even though it doesn't directly match the candidate's key skills (e.g. entry-level business, administration, customer support, marketing, sales, etc). Can be permanent, contract, or trainee.

**3. Application Deadline:**
* The last date of application MUST be in the future (use a function or your system context to find today's date).
* If the deadline has already passed, discard the job. If no deadline is explicitly mentioned, assume it is still active.

* **Salary Expectation:** None

## Agent Instructions
When evaluating a job posting, you MUST use your web fetch tool to visit the URL to check the application deadline and read the full job description. Logically check if it fits the combinations defined above.

**Critical evaluation order — apply these checks in sequence:**
1. **Read the actual job title and description first.** Do not infer the role type from the company name or location alone. A job in Oulu is not automatically a "legal" or "generalist" role.
2. **Apply Hard Rejections first.** If the role is a trade (welder, carpenter, electrician), medical (doctor, pharmacist, nurse), cooking, teaching, or special education job, discard it immediately — location does not matter.
3. **Then check Domain criteria.** The role must fit one of the three valid combinations (Legal Trainee, English Law Role, or Generalist No-Requirement). Entry-level sales, admin, customer service, marketing qualify as generalist. Skilled trades do NOT.
4. **Then check Location.** Only after passing the above checks.
5. **Then check Deadline.** Reject if the deadline has already passed relative to today's date.

**Tracking Evaluations:** After evaluating a "pending" job in `jobs.json`, you MUST update that specific job's entry directly within `jobs.json` in-place. Set `"visited": "yes"`, update `"matches_requirements"` to `"yes"` (if it matched), `"maybe"` (if it is a maybe match), or `"no"` (if it was discarded), and set `"reason"` to a brief 1-sentence explanation of your decision. Do NOT delete any records from the file!

### Automatically Added Negative Constraints (from UI Rejections):
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'Construction experts'. Do NOT match jobs that have this issue.
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'carpenter job'. Do NOT match jobs that have this issue.
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'requires msc or PhD in technical areas like electrical or telecommunications'. Do NOT match jobs that have this issue.


### Automatically Added Positive Constraints (from UI Approvals):
- POSITIVE CONSTRAINT: The user explicitly approved a previous job because: 'testing reason'. Make sure to MATCH jobs that have this characteristic.


### Automatically Added Positive Constraints (from UI Approvals):
- POSITIVE CONSTRAINT: The user explicitly approved a previous job because: 'testing again'. Make sure to MATCH jobs that have this characteristic.
- POSITIVE CONSTRAINT: The user explicitly approved a previous job because: 'testing again and agian'. Make sure to MATCH jobs that have this characteristic.
