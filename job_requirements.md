# Job Search Requirements

## Candidate Profile
* **Name:** Manju
* **Current Role:** Unemployed
* **Years of Experience:** 2 years
* **Key Skills:** Corporate Law

## Hard Rejections
Immediately discard a job if ANY of the following are true:
* The job title contains "Senior". The candidate does not have enough experience for senior roles.

## Target Job Criteria

A job is a match if it satisfies ONE condition from EACH of the following categories:

**1. Domain / Field:**
* Corporate Law OR any Legal field.
* *Exception:* If the position requires NO experience, then Marketing, Sales, or Generalist roles are also acceptable.

**2. Location & Work Model:**
* Oulu AND On-site
* Finland AND Hybrid
* Fully Remote AND (the location is "Worldwide" OR no specific country is mentioned). Must NOT require US residency.

**3. Position Type & Degree Requirements:**
* Permanent AND accepts an international degree in English.
* Trainee AND requires a Finland degree.

**4. Application Deadline:**
* The last date of application MUST be in the future (use a function or your system context to find today's date).
* If the deadline has already passed, discard the job. If no deadline is explicitly mentioned, assume it is still active.

* **Salary Expectation:** None

## Agent Instructions
When evaluating a job posting, you MUST use your web fetch tool to visit the URL to check the application deadline and read the full job description. Logically check if it fits the combinations defined above.

**Tracking Evaluations:** After evaluating a "pending" job in `jobs.json`, you MUST update that specific job's entry directly within `jobs.json` in-place. Set `"visited": "yes"`, update `"matches_requirements"` to `"yes"` (if it matched) or `"no"` (if it was discarded), and set `"reason"` to a brief 1-sentence explanation of your decision. Do NOT delete any records from the file!