Tailor fresh resumes and cover letters for one or more job IDs using Claude, replacing any existing docs and updating the live dashboard.

The job IDs to process are: **$ARGUMENTS**

Parse `$ARGUMENTS` as a space-separated list of job IDs (e.g. `abc123 def456 ghi789`). If only one ID is given, process just that one. Run Steps 0–5 for **each job ID in sequence**, then run Steps 6–8 once at the end to batch-commit and sync everything.

---

## Constants (set once, reuse for every job)

- `PUBLIC`    = `C:\Users\vinee\manju_jobs`
- `PRIVATE`   = `C:\Users\vinee\Manju_jobs_private`
- `JOBS_JSON` = `PUBLIC\jobs.json`

Read the structural template **once** before the loop:
Read `PRIVATE\Resumes\f6aaa66f\f6aaa66f_data.json`. Every output JSON must match this structure exactly (same keys, same nesting).

---

## Loop — repeat Steps 0–5 for each JOB_ID

---

### Step 0 — Find the job

Read `JOBS_JSON` and locate the entry where `"id"` equals `JOB_ID`.
If not found, skip this ID, print an error, and continue to the next.

Record:
- `JOB_TITLE`  — the `title` field
- `COMPANY`    — the `company` field
- `JOB_URL`    — the `url` field
- `DESC_FILE`  — the `description_file` field (may be null)

---

### Step 1 — Obtain the job description

Try in order, stopping at the first success:

1. If `DESC_FILE` is set, read `PUBLIC\DESC_FILE`. Accept it if it contains more than 200 meaningful words after the `JOB DESCRIPTION:` header (not cookie walls or login pages).
2. Use **WebFetch** on `JOB_URL`.
3. Try a web search for `"JOB_TITLE" "COMPANY" Finland job`.

If all three fail, skip this ID, report which sources were tried, and continue to the next.

---

### Step 1.5 — Scrape application form questions (best-effort)

Run the scraper. Non-blocking — if it finds nothing or errors, continue to Step 2 normally.

```powershell
python "PUBLIC\scrape_application.py" `
    --job-url "JOB_URL" `
    --job-id  "JOB_ID" `
    --out-dir "PRIVATE\Resumes\JOB_ID" `
    --private-dir "PRIVATE"
```

**First-time behaviour:** If credentials for the platform aren't saved yet, the script prompts interactively (password hidden). They are saved to `PRIVATE\.env` and session cookies to `PRIVATE\sessions\` — all future runs are silent.

**Outcome:**
- Success → `PRIVATE\Resumes\JOB_ID\JOB_ID_questions.json` written. Note `question_count`.
- Failure / 0 questions → skip Step 1.6 for this job, continue from Step 2.

---

### Step 1.6 — Generate tailored application answers

Only run if `JOB_ID_questions.json` exists and `question_count > 0`.

Read `PRIVATE\Resumes\JOB_ID\JOB_ID_questions.json`. Using the job description from Step 1 and Manju's profile (see Step 2 tailoring rules below), write a tailored answer for every question.

**Answer rules:**
- **Text / textarea:** 1–4 sentences for short fields; a full paragraph for open-ended ones. Name the company and role directly where it fits.
- **Select / dropdown:** Pick the most accurate option from the `options` list.
- **Factual fields** — use these exact values:
  - Phone: leave blank, set `is_placeholder: true`
  - Address: `Oulu, Finland`
  - Availability: `September 2026`
  - Salary expectation: leave blank, set `is_placeholder: true`
  - Right to work in Finland: `Yes — EU residence permit`
- **Language:** Answer in the same language as the question (Finnish if Finnish, English if English).
- Do **not** invent facts not in Manju's profile.

**Write two output files:**

1. `PRIVATE\Resumes\JOB_ID\JOB_ID_answers.json` — machine-readable, used by the auto-filler:
```json
{
  "job_id": "JOB_ID",
  "job_url": "JOB_URL",
  "apply_url": "<apply_url from questions JSON, or JOB_URL>",
  "platform": "<platform from questions JSON>",
  "answers": [
    {
      "label": "<exact label from questions JSON>",
      "type": "<type>",
      "answer": "<generated answer, or empty string if placeholder>",
      "step": <step number if present>,
      "is_placeholder": <true if phone/salary/manual field>
    }
  ]
}
```

2. `PRIVATE\Resumes\JOB_ID\JOB_ID_application_cheatsheet.html` — human-readable backup:
```html
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Application — JOB_TITLE at COMPANY</title>
<style>
  body{font-family:Calibri,Arial,sans-serif;max-width:800px;margin:40px auto;font-size:14px;color:#1e1e1e}
  h1{font-size:18px;color:#1a4f82;border-bottom:2px solid #1a4f82;padding-bottom:6px}
  .meta{color:#666;font-size:12px;margin-bottom:24px}
  .qa{margin-bottom:20px}
  .question{font-weight:bold;font-size:13px;color:#333;margin-bottom:4px}
  .qmeta{font-size:11px;color:#999;margin-bottom:4px}
  .answer{background:#f0f4fa;border-left:3px solid #1a4f82;padding:8px 12px;white-space:pre-wrap}
  .placeholder{background:#fff8e1;border-left:3px solid #f59e0b;padding:8px 12px}
</style></head><body>
<h1>JOB_TITLE — COMPANY</h1>
<div class="meta">Job ID: JOB_ID | Platform: PLATFORM | <a href="APPLY_URL">Application link</a></div>
<!-- one .qa per question; use class="placeholder" for manual-fill fields -->
</body></html>
```

Report: `Application prep done: N answers generated, M placeholders for manual fill.`

---

### Step 2 — Write the tailored data.json

Create folder `PRIVATE\Resumes\JOB_ID\` if it does not exist.
Write the tailored JSON to `PRIVATE\Resumes\JOB_ID\JOB_ID_data.json` — overwrite if it exists.

#### Tailoring rules

**Top-level fields:**
- `job_id`: set to `JOB_ID`
- `job_title`: set to `JOB_TITLE` (exact string from jobs.json)
- `company`: set to `COMPANY`
- `tailor_model`: set to `"claude-sonnet-4-6"`

**`resume.role`:** `"JOB_TITLE Candidate"`

**`resume.profile`:** 2–3 sentences, highly specific to this role and company. Directly connect Manju's most relevant background to the stated requirements. Do not just summarise her CV — name the company and what they need.

**`resume.experience`:** Keep all four entries exactly as in the template (same dates, companies, titles). Reorder the four entries so the most relevant experience appears first. Within each entry, reorder and reword the bullets to front-load skills mentioned in the job description.

**`resume.education`:** Keep all entries as in the template.

**`resume.languages_html`:** For Finnish-language postings, put Finnish first. For English-language postings, keep English first.

**`resume.competencies_html`:** Completely rewrite 4–5 skill categories that map directly onto the key requirements in this job description. Use `<span class="skill-cat">Category:</span> description...` format.

**`cover_letter.date`:** Use today's date formatted as `"30 June 2026"`.

**`cover_letter.recipient`:** Fill `company` with `COMPANY` and `city` with the job location. Use `"Hiring Manager"` for title if no name is known.

**`cover_letter.paragraphs`:** 4–5 paragraphs written in the **same language as the job posting** (Finnish for Finnish postings, English for English postings):
  1. Hook — what drew Manju to this company and role specifically.
  2. Most relevant experience — connect it directly to the job requirements.
  3. Finland integration — Finnish B2, Oulu roots, IHO internship, OPH bar path.
  4. Why this company — something specific from the posting or company.
  5. Close — availability (September 2026), contact invitation.

**`cover_letter.sign_off`:** `"Ystävällisin terveisin"` for Finnish, `"Yours sincerely"` for English.

#### Manju's profile (use exactly these facts)
- LL.M. Business & Corporate Law, First Rank — Symbiosis International University (2020–21)
- LL.B. First Class Honours, Top 3 — University of Calicut (2009–14)
- Finnish Supplementary Law Studies (OPH bar path) — University of Lapland (2025–present)
- Kohti Yliopistoa — University of Oulu (2025–26)
- Language placement: Asianajajatoimisto Regelin Oy, Oulu (Apr–Jun 2026)
- Intern: International House Oulu — 14 events, OuluBot (Jan–Apr 2025, Sep–Oct 2024)
- Legal Associate: Poise Legal India (Oct 2021–May 2022) — 5–7 contracts/month
- Junior Lawyer: Juris Nexus India (Sep 2015–Jan 2016) — family & civil law
- Finnish B2, English C1, Malayalam native. Based in Oulu. Available Sep 2026.

---

### Step 3 — Clear old generated files

```powershell
Remove-Item "PRIVATE\Resumes\JOB_ID\*.html" -ErrorAction SilentlyContinue
Remove-Item "PRIVATE\Resumes\JOB_ID\*.pdf"  -ErrorAction SilentlyContinue
```

---

### Step 4 — Generate HTML and convert to PDF

```powershell
python "PUBLIC\make_resume.py" "PRIVATE\Resumes\JOB_ID\JOB_ID_data.json" --photo "PRIVATE\manju_photo.JPG" --out-dir "PRIVATE\Resumes"
```

This produces two `.html` files inside `PRIVATE\Resumes\JOB_ID\`. Convert each to PDF:

```powershell
$htmlFiles = Get-ChildItem "PRIVATE\Resumes\JOB_ID\*.html"
foreach ($html in $htmlFiles) {
    python "PUBLIC\html_to_pdf.py" $html.FullName
}
```

Confirm both PDF files exist. If either is missing, report the error but continue processing remaining job IDs.

Print a one-line progress note after each job: `✓ JOB_ID (JOB_TITLE @ COMPANY) — PDFs generated`

---

## End of loop

---

## Application Fill Phase — sequential browser sessions

Only run this phase if at least one job produced a `JOB_ID_answers.json` file.

Collect the job IDs that have answers files into a space-separated list (`FILL_IDS`), then run:

```powershell
python "PUBLIC\fill_application.py" `
    --job-id FILL_IDS `
    --private-dir "PRIVATE"
```

The script opens a visible browser for each job in turn:
1. Navigates to the application form and fills all matched fields automatically
2. Stops at the review/submit screen — **does not submit**
3. Manju reviews the answers in the browser and clicks Submit
4. Manju presses Enter in the terminal → browser closes → next job opens immediately
5. Typing `s` + Enter skips that job without submitting

A summary table is printed when all jobs are done. After this phase, continue to Step 5.

---

## Step 5 — Commit all jobs to private repo (one commit)

```powershell
git -C "PRIVATE" add Resumes\
git -C "PRIVATE" commit -m "Retailor resumes for N jobs: JOB_ID_1, JOB_ID_2, ... (claude-sonnet-4-6)"
git -C "PRIVATE" push
```

Use the actual count and list of successfully processed job IDs in the commit message.

---

## Step 6 — Sync links to Firestore (force overwrite)

```powershell
Set-Location "PUBLIC"
python sync_resume_links.py --upload --force
```

This rescans all Resumes/ folders, writes `input.csv`, and pushes the new PDF GitHub URLs to Firestore — overwriting any previously stored links for these jobs.

---

## Step 7 — Commit public repo

```powershell
git -C "PUBLIC" add input.csv
git -C "PUBLIC" commit -m "Update resume links for JOB_ID_1 JOB_ID_2 ... (retailored with claude-sonnet-4-6)"
git -C "PUBLIC" push origin main
```

If `input.csv` has no changes, skip the commit and note that it was already up to date.

---

## Step 8 — Report

Print a summary table for all processed jobs:

| Job ID | Title | Company | Resume PDF | Cover Letter PDF | Firestore |
|--------|-------|---------|------------|------------------|-----------|
| abc123 | ... | ... | filename.pdf | filename.pdf | ✓ |

Then note: "Dashboard links will appear live in the Docs column within ~30 seconds (Firebase realtime sync)."

If any job was skipped, list them with the reason.
