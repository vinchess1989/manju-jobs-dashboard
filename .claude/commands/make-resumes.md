Generate tailored PDF resumes and cover letters for Manju's matching jobs.

## Step 0 — Discover repo paths (run this first, every time)
```
python find_repos.py --json
```
This auto-detects the local clone paths on any machine. Store the result as:
- `PUBLIC`  = the path returned for `vinchess1989/manju-jobs-dashboard`
- `PRIVATE` = the path returned for `munchnambiar/Manju-jobs`

Use these variables for all subsequent paths in this skill.

## Step 1 — Pull both repos
```
git -C "<PUBLIC>" pull
git -C "<PRIVATE>" pull
```

## Step 2 — Get the candidate job list
Run from the PUBLIC repo directory:
```
cd "<PUBLIC>"
python find_matching_jobs.py --posted-days 3 --deadline-days 3 --or posted-days deadline-days
```
This produces a timestamped `jobs_<ts>.json`. Read that file.
The script returns all jobs where `matches_requirements` is **yes or maybe**.

## Step 3 — Identify unprocessed jobs
Cross-check the output against existing folders in `<PRIVATE>\Resumes\`.
Jobs with an existing folder are already done — skip them.

**Claude review:** From the remaining jobs, discard only those that are completely irrelevant
(e.g. manual labour, driving, warehouse, cooking, healthcare assistant, cleaning).
Keep ALL generalist office/admin/coordinator/assistant/HR/comms/event roles even if they
don't directly use Manju's legal skills — she is available for generalist roles too.
Keep all legal, compliance, paralegal, juristi, and trainee roles unconditionally.

Show the curated list to the user before generating any files, and confirm before proceeding.

## Step 4 — For each unprocessed job (batches of 5)

### 4a — Get the job description
1. Check the local description file at `<PUBLIC>\<description_file field from jobs.json>`.
2. Read the file. If it has **real content** (>200 meaningful words after the `JOB DESCRIPTION:` header — not just cookie consent / LinkedIn login wall / Cloudflare error), use it.
3. If the file has no real content, use **WebFetch** on the job's URL (`url` field in jobs.json).
4. If that is also blocked, try a web search for `"<job title>" "<company>" Finland job`.
5. If all methods fail, note it and skip the job.

### 4b — Write tailored data.json
Create `<PRIVATE>\Resumes\<job_id>\<job_id>_data.json`.

Use `<PRIVATE>\Resumes\f6aaa66f\f6aaa66f_data.json` as the structural template.

Tailoring rules:
- `role` field: match the exact job title
- `profile` paragraph: 2–3 sentences. Reference the company and role specifically. Highlight the most relevant subset of Manju's background.
- `experience[].bullets`: reorder or reword to front-load skills most relevant to this role. Keep all 4 experience entries.
- `competencies_html`: reorder skill categories to lead with what matters for this role.
- `languages_html`: put Finnish first for Finnish-language roles.
- `cover_letter`: write in **Finnish** for Finnish-language roles, **English** for English-language roles. Address the hiring manager by name if known from the description. 4–5 paragraphs: hook → relevant experience → Finland integration → why this company → close.
- For legal/juristi roles: emphasise contract law, legal research, court experience, Finnish bar path.
- For generalist/admin/coordinator roles: emphasise event coordination (IHO), organisational skills, multilingual communication, MS Office, Finnish B2.
- For compliance roles: emphasise contract lifecycle management, regulatory research, GDPR awareness.

### 4c — Generate HTML
Run from PUBLIC repo directory:
```
cd "<PUBLIC>"
python make_resume.py "<PRIVATE>\Resumes\<job_id>\<job_id>_data.json" --photo "<PRIVATE>\manju_photo.JPG" --out-dir "<PRIVATE>\Resumes"
```

### 4d — Convert to PDF
```
python html_to_pdf.py "<PRIVATE>\Resumes\<job_id>\Manju_Krishna_<Title>_<Company>_resume.html"
python html_to_pdf.py "<PRIVATE>\Resumes\<job_id>\Manju_Krishna_<Title>_<Company>_cover_letter.html"
```

### 4e — Push private repo after each batch
```
git -C "<PRIVATE>" add Resumes/
git -C "<PRIVATE>" commit -m "Add resume docs for batch <n>: <job titles>"
git -C "<PRIVATE>" push
```

## Step 5 — Update Firestore
Create/append to `<PUBLIC>\input.csv`:
```
job_id,resume_url,cover_letter_url
<job_id>,https://github.com/munchnambiar/Manju-jobs/blob/main/Resumes/<job_id>/Manju_Krishna_<Title>_<Company>_resume.pdf,https://github.com/munchnambiar/Manju-jobs/blob/main/Resumes/<job_id>/Manju_Krishna_<Title>_<Company>_cover_letter.pdf
```
Then run:
```
cd "<PUBLIC>"
python upload_resume_links.py --input input.csv
```

## Step 6 — Push public repo
```
cd "<PUBLIC>"
git add input.csv
git commit -m "Update input.csv with resume links for batch <n>"
git push origin main
```

## Manju's profile (for tailoring)
- LL.M. Business & Corporate Law, First Rank — Symbiosis International University (2020–21)
- LL.B. First Class Honours, Top 3 — University of Calicut (2009–14)
- Finnish Supplementary Law Studies (OPH bar path) — University of Lapland (2025–present)
- Kohti Yliopistoa — University of Oulu (2025–26)
- Language placement: Asianajajatoimisto Regelin Oy, Oulu (Apr–Jun 2026)
- Intern: International House Oulu — 14 events, OuluBot (Jan–Apr 2025, Sep–Oct 2024)
- Legal Associate: Poise Legal India (Oct 2021–May 2022) — 5–7 contracts/month
- Junior Lawyer: Juris Nexus India (Sep 2015–Jan 2016) — family & civil law
- Finnish B2, English C1, Malayalam native. Based in Oulu. Available Sep 2026.
- Photo: `<PRIVATE>\manju_photo.JPG`

## Output naming convention
```
Resumes/<job_id>/Manju_Krishna_<JobTitle>_<Company>_resume.pdf
Resumes/<job_id>/Manju_Krishna_<JobTitle>_<Company>_cover_letter.pdf
```
(make_resume.py derives filenames automatically from `job_title` and `company` in the JSON)

## Already completed
- `f6aaa66f` — Legal Trainee, Hiab
- `f062b3e0` — Juristi, OP Jokilaaksot (cover letter in Finnish)
