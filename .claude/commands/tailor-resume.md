Tailor a fresh resume and cover letter for a single job ID using Claude, replacing any existing docs and updating the live dashboard.

The job ID to process is: **$ARGUMENTS**

---

## Step 0 — Resolve paths and find the job

Set these constants for all subsequent steps:
- `PUBLIC`  = `C:\Users\vinee\manju_jobs`
- `PRIVATE` = `C:\Users\vinee\Manju_jobs_private`
- `JOB_ID`  = `$ARGUMENTS`

Read `C:\Users\vinee\manju_jobs\jobs.json` and locate the entry where `"id"` equals `$ARGUMENTS`.
If not found, stop immediately and report the error.

Record from that entry:
- `JOB_TITLE`  — the `title` field
- `COMPANY`    — the `company` field
- `JOB_URL`    — the `url` field
- `DESC_FILE`  — the `description_file` field (may be null)

---

## Step 1 — Obtain the job description

Try in order, stopping at the first success:

1. If `DESC_FILE` is set, read `PUBLIC\DESC_FILE`. Accept it if it contains more than 200 meaningful words after the `JOB DESCRIPTION:` header (not cookie walls or login pages).
2. Use **WebFetch** on `JOB_URL`.
3. Try a web search for `"JOB_TITLE" "COMPANY" Finland job`.

If all three fail, stop and report which sources were tried.

---

## Step 2 — Read the template

Read `PRIVATE\Resumes\f6aaa66f\f6aaa66f_data.json` as the structural template. Every field in the output must match this structure exactly (same keys, same nesting).

---

## Step 3 — Write the tailored data.json

Create folder `PRIVATE\Resumes\JOB_ID\` if it does not exist.
Write the tailored JSON to `PRIVATE\Resumes\JOB_ID\JOB_ID_data.json` — overwrite if it exists.

### Tailoring rules

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

**`cover_letter.date`:** Use today's date formatted as `"24 June 2026"`.

**`cover_letter.recipient`:** Fill `company` with `COMPANY` and `city` with the job location. Use `"Hiring Manager"` for title if no name is known.

**`cover_letter.paragraphs`:** 4–5 paragraphs written in the **same language as the job posting** (Finnish for Finnish postings, English for English postings):
  1. Hook — what drew Manju to this company and role specifically.
  2. Most relevant experience — connect it directly to the job requirements.
  3. Finland integration — Finnish B2, Oulu roots, IHO internship, OPH bar path.
  4. Why this company — something specific from the posting or company.
  5. Close — availability (September 2026), contact invitation.

**`cover_letter.sign_off`:** `"Ystävällisin terveisin"` for Finnish, `"Yours sincerely"` for English.

### Manju's profile (use exactly these facts)
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

## Step 4 — Clear old generated files

Remove any stale HTML and PDF files from the job folder so old filenames don't persist:

```powershell
Remove-Item "PRIVATE\Resumes\JOB_ID\*.html" -ErrorAction SilentlyContinue
Remove-Item "PRIVATE\Resumes\JOB_ID\*.pdf"  -ErrorAction SilentlyContinue
```

---

## Step 5 — Generate HTML and convert to PDF

```powershell
cd PUBLIC
.\venv\Scripts\python make_resume.py "PRIVATE\Resumes\JOB_ID\JOB_ID_data.json" --photo "PRIVATE\manju_photo.JPG" --out-dir "PRIVATE\Resumes"
```

This produces two `.html` files inside `PRIVATE\Resumes\JOB_ID\`. Find their paths:

```powershell
$htmlFiles = Get-ChildItem "PRIVATE\Resumes\JOB_ID\*.html"
```

Convert each to PDF:

```powershell
foreach ($html in $htmlFiles) {
    .\venv\Scripts\python html_to_pdf.py $html.FullName
}
```

Confirm both PDF files exist before continuing. If either is missing, stop and report.

---

## Step 6 — Commit to private repo

```powershell
cd PRIVATE
git add "Resumes\JOB_ID\"
git commit -m "Retailor resume for JOB_ID: JOB_TITLE at COMPANY (claude-sonnet-4-6)"
git push
```

---

## Step 7 — Sync links to Firestore (force overwrite)

```powershell
cd PUBLIC
.\venv\Scripts\python sync_resume_links.py --upload --force
```

This rescans all Resumes/ folders, writes `input.csv`, and pushes the new PDF GitHub URLs to Firestore — overwriting any previously stored links for this job.

---

## Step 8 — Commit public repo

```powershell
cd PUBLIC
git add input.csv
git commit -m "Update resume links for JOB_ID (retailored with claude-sonnet-4-6)"
git push origin main
```

---

## Step 9 — Report

Print a summary:
- Job: `JOB_TITLE` at `COMPANY` (`JOB_ID`)
- Resume PDF: the filename generated
- Cover letter PDF: the filename generated
- Firestore: updated ✓ / failed ✗
- Dashboard: links will appear live in the Docs column within ~30 seconds (Firebase realtime sync)
