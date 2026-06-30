# Job Search Requirements

## Candidate Profile
* **Name:** Manju Krishna Haridas
* **Current Role:** Actively seeking employment; completing supplementary law studies for Finnish bar qualification.
* **Education:**
  * LL.M. Business and Corporate Law — Symbiosis International University, India (2020–2021) | **First Rank Holder (Top of Class)**
  * LL.B. — University of Calicut, India (2009–2014) | **First Class Honours**
  * Supplementary Law Studies (Finnish Bar Qualification) — University of Lapland (2025–Present) | OPH recognition decision received
  * Towards University (KOHY) Studies — University of Oulu (2025–2026) | Academic integration + advanced Finnish
  * Integration Training — OSAO, Oulu (2023–2024)
* **Work Experience:**
  * Intern — International House Oulu, Finland (09/2024–10/2024 & 01/2025–04/2025): event management (14 community events), digital service deployment (OuluBot), communications & social media, advisory to international residents.
  * Legal Associate — Poise Legal, India (10/2021–05/2022): drafted/reviewed 5–7 commercial agreements per month (NDAs, Service Agreements), legal analysis on Company & Contract Law, full contract lifecycle management for 4 corporate clients.
  * Junior Lawyer — Juris Nexus, India (09/2015–01/2016): litigation support, trial preparation, client representation in civil and family matters.
* **Key Skills:** Contract Law & Drafting, Regulatory Compliance, Legal Research & Analysis, Project Coordination, Event Management, Client Advisory, Document Management, MS Office, Social Media Management, Digital Service Deployment.
* **Languages:** English (C1 / Native-level), Finnish (B2 — Intermediate, actively improving), Malayalam (Native).
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
* **Events & Communications:** event coordinator, event assistant, community coordinator, communications assistant, content coordinator, social media assistant — strong match given Manju's IHO experience organising 14+ community events and producing social media content.
* **Marketing & Digital:** marketing assistant, digital content assistant — supported by her social media management and OuluBot digital deployment experience.
* **Data & Document Management:** data entry clerk, document controller, records coordinator, quality assistant.
* **Logistics & Supply Chain Support:** logistics coordinator, supply chain assistant, procurement assistant — office-based, no warehouse/forklift work.
* **Legal & Compliance (Priority Secondary):** Any legal, compliance, contract management, or corporate law role (trainee, junior, or permanent) that accepts an international/Indian law degree OR is a Finnish trainee role (laki-/lakiharjoittelu). Her LL.M. First Rank + active Finnish bar path (OPH recognised) make these strong fits.

A role qualifies if it is entry-level or does not list a strict degree requirement beyond a general bachelor's or equivalent.

**Language note:** Manju's Finnish is B2 (Intermediate). Roles requiring fluent Finnish (C1+) as a hard requirement should be marked "no". Roles where Finnish is preferred but not mandatory, or where English is the working language, are fine to match.

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


### Automatically Added Negative Constraints (from UI Rejections):
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'Not my field - its for lahihoitaja'. Do NOT match jobs that have this issue.
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'Requires a nursing degree and a valid medical license'. Do NOT match jobs that have this issue.


### Automatically Added Negative Constraints (from UI Rejections):
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'Needs restaurant field studies'. Do NOT match jobs that have this issue.


### Automatically Added Negative Constraints (from UI Rejections):
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'Needs Hygeine pass'. Do NOT match jobs that have this issue.
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'Needs University degree in Forestry'. Do NOT match jobs that have this issue.


### Automatically Added Negative Constraints (from UI Rejections):
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'its for Accountants'. Do NOT match jobs that have this issue.


### Automatically Added Negative Constraints (from UI Rejections):
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'Needs lahihoitaja degree'. Do NOT match jobs that have this issue.


### Automatically Added Negative Constraints (from UI Rejections):
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'Needs hands on payroll processing expereince'. Do NOT match jobs that have this issue.


### Automatically Added Negative Constraints (from UI Rejections):
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'Should meet these conditions:
- you are 15-24 years old
- you have reached the age of 50
- you have not completed a matriculation examination, a degree referred to in the Act on Vocational Education and Training, or a comparable foreign upper secondary education
- you are entitled to an integration plan referred to in the Act on the Promotion of Integration
- you have not been in gainful employment during the previous six months
- as an unemployed job seeker, your chances of finding a suitable job have been significantly reduced due to a disability or illness.'. Do NOT match jobs that have this issue.


### Automatically Added Negative Constraints (from UI Rejections):
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'Expertise beyond general administrative work'. Do NOT match jobs that have this issue.
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'Need education in the field or otherwise commendable knowledge of automotive technology'. Do NOT match jobs that have this issue.
- NEGATIVE CONSTRAINT: The user explicitly rejected a previous job because: 'Appliaction accepted only from unemployed people in Helsinki between the ages 15- 25 and above 50 years'. Do NOT match jobs that have this issue.
