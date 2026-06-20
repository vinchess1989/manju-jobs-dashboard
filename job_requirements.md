# Job Search Requirements

## Candidate Profile
* **Name:** Manju
* **Current Role:** Unemployed
* **Years of Experience:** 2 years
* **Background:** Law degree completed in India (international degree in English). Currently located in Finland and completing supplementary courses in Finnish to obtain equivalence/qualification for a Finnish law degree.
* **Key Skills:** Corporate Law

## Hard Rejections
Immediately discard a job if ANY of the following are true:
* The job title contains "Senior". The candidate does not have enough experience for senior roles.
* The job requires domain-specific technical expertise in any of the following fields: carpentry, electrical work, construction, cooking/chef, security guard, special education, nursing, or teaching. Discard even if the role appears entry-level.

## Target Job Criteria

A job is a match if it satisfies the criteria in ALL of the following categories:

**1. Location & Work Model:**
* **Yes Match:** Must satisfy at least ONE of the following:
  * Oulu AND On-site
  * Finland AND Hybrid
  * Fully Remote AND (the location is "Worldwide" OR no specific country is mentioned). Must NOT require US residency.
* **Maybe Match:** If the job is located in a different location in Finland (outside Oulu) and does not have a hybrid/remote option (i.e. on-site in Helsinki, Tampere, etc.), mark it as "maybe" (instead of "no"), provided it satisfies all other criteria.
* **Location Inference:** If the job description is written in Finnish and no location is specified, set/assume the location as Finland.


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
