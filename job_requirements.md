# Job Search Requirements

## Candidate Profile
* **Name:** Manju
* **Current Role:** Unemployed
* **Years of Experience:** 2 years
* **Background:** Law degree completed in India (international degree in English). Currently located in Finland and completing supplementary courses in Finnish to obtain equivalence/qualification for a Finnish law degree.
* **Key Skills:** Office administration, document management, customer service, corporate law background.
* **Driving:** Has a valid driving license and can use her personal car for work if required.

## Hard Rejections
Immediately discard a job if ANY of the following are true:
* The job title contains "Senior", "Manager", "Head of", "Director", or "Lead". The candidate does not have enough experience for these levels.
* The job requires domain-specific technical expertise in: carpentry, electrical work, construction, cooking/chef, security guard, special education, nursing, or teaching.
* The job is a trade or manual-labour role requiring specific vocational training: welding, metalwork/fabrication, scaffold assembly, asbestos/demolition, crane/heavy equipment operation, refrigeration installation, or any similar skilled-trade position.
* The job is in the medical or healthcare field requiring clinical training: physician (lääkäri), pharmacist (farmaseutti), nurse practitioner, lab technician (laboratoriohoitaja), physiotherapist, or any role requiring a medical/healthcare degree.
* The job requires a specific technical degree (engineering, IT/software development, science, architecture) as a hard requirement — unless the posting explicitly says the degree requirement can be waived with experience.
* The job title is clearly unrelated to office or service work — e.g. husky guide, dog handler, pest control, diver, retinal photographer, etc.
* Construction experts or construction-related roles.

## Target Job Criteria

A job is a match if it satisfies ALL of the following:

**1. Location & Work Model:**
* **Yes Match:** Must satisfy at least ONE of the following:
  * Oulu AND On-site (or hybrid)
  * Anywhere in Finland AND Hybrid or Remote
  * Fully Remote AND (location is "Worldwide" OR no specific country mentioned). Must NOT require EU/Finnish residency or US residency.
* **Maybe Match:** On-site role outside Oulu (Helsinki, Tampere, Turku, etc.) that passes all other criteria.
* **Location Inference:** If the job description is in Finnish and no location is specified, assume Finland.
* **Country-specific remote jobs (UK, USA, India, etc.):** Only qualify as remote if the posting explicitly states it is open to applicants from anywhere. Otherwise treat as that country (→ "no").

**2. Role Type — Primary: Generalist Office Roles:**
This is the PRIMARY match category. Match if the role is any entry-level or mid-level office/service position that does NOT require a specific technical degree. Examples include (but are not limited to):
* **Administration & Coordination:** office assistant, office coordinator, administrative assistant, executive assistant, receptionist, project coordinator, operations assistant, back-office support.
* **Customer Service & Sales:** customer service representative, customer support agent, sales assistant, account coordinator, helpdesk agent, inside sales.
* **HR & People:** HR assistant, HR coordinator, recruitment coordinator, people ops assistant, talent acquisition support.
* **Finance & Accounting Support:** accounts assistant, invoicing clerk, billing coordinator, payroll assistant — entry-level only, no CPA/accountant qualification required.
* **Marketing & Communications:** marketing assistant, communications assistant, content coordinator, social media assistant.
* **Data & Document Management:** data entry clerk, document controller, records coordinator, quality assistant.
* **Logistics & Supply Chain Support:** logistics coordinator, supply chain assistant, procurement assistant — office-based, no warehouse/forklift work.
* **Legal & Compliance (Secondary):** Any legal, compliance, contract management, or corporate law role (trainee, junior, or permanent) that accepts an international/Indian law degree OR is a Finnish trainee role (laki-/lakiharjoittelu).

A role qualifies if it is entry-level or does not list a strict degree requirement beyond a general bachelor's or equivalent.

**3. Application Deadline:**
* The application deadline MUST be in the future relative to today's date.
* If the deadline has already passed, discard. If no deadline is mentioned, assume it is still active.

**Salary Expectation:** None

## Agent Instructions
When evaluating a job posting, use your web fetch tool to visit the URL and read the full description. Then apply checks in this order:

1. **Read the full job title and description.** Do not infer from the company name or location alone.
2. **Apply Hard Rejections.** Trade, clinical/medical, senior-level, or purely technical roles → discard immediately.
3. **Check Role Type.** Does it fit a generalist office/service role or a legal role? If yes → proceed. If the role requires a specific technical degree (IT, engineering, science) as a hard requirement → "no".
4. **Check Location.**
5. **Check Deadline.**

**Tracking Evaluations:** After evaluating a "pending" job in `jobs.json`, update that job's entry in-place: set `"visited": "yes"`, set `"matches_requirements"` to `"yes"`, `"maybe"`, or `"no"`, and set `"reason"` to a brief 1-sentence explanation. Do NOT delete records.

### Negative Constraints (from user feedback):
- Do NOT match jobs that require MSc or PhD in technical areas like electrical or telecommunications.
- Do NOT match carpenter jobs or construction expert roles.
