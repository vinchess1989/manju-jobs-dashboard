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

## Target Job Criteria

A job is a match if it satisfies the criteria in ALL of the following categories:

**1. Location & Work Model:**
Must satisfy at least ONE of the following:
* Oulu AND On-site
* Finland AND Hybrid
* Fully Remote AND (the location is "Worldwide" OR no specific country is mentioned). Must NOT require US residency.

**2. Domain, Position Type, & Degree Requirements:**
Must satisfy at least ONE of the following valid combinations:
* **Trainee / Internship Role (Legal):** Trainee, internship, or junior legal role, even if it requires a Finnish law degree or Finnish qualification (since she is in Finland and currently doing the supplementary courses needed).
* **English Law Role:** Any legal, compliance, contract management, or corporate law role (permanent, trainee, or contract) that accepts a law degree in English or an international/Indian law degree (without strictly requiring a Finnish qualification).
* **Generalist Role:** Any other job (non-legal, e.g. entry-level/generalist business, administration, customer support, marketing, sales) that does not require any specific technical knowledge. Can be permanent, contract, or trainee.

**3. Application Deadline:**
* The last date of application MUST be in the future (use a function or your system context to find today's date).
* If the deadline has already passed, discard the job. If no deadline is explicitly mentioned, assume it is still active.

* **Salary Expectation:** None

## Agent Instructions
When evaluating a job posting, you MUST use your web fetch tool to visit the URL to check the application deadline and read the full job description. Logically check if it fits the combinations defined above.

**Tracking Evaluations:** After evaluating a "pending" job in `jobs.json`, you MUST update that specific job's entry directly within `jobs.json` in-place. Set `"visited": "yes"`, update `"matches_requirements"` to `"yes"` (if it matched) or `"no"` (if it was discarded), and set `"reason"` to a brief 1-sentence explanation of your decision. Do NOT delete any records from the file!