Tailor fresh resumes and cover letters for one or more job IDs using Claude, replacing any existing docs and updating the live dashboard. Does not touch application forms, scrape questions, or generate answers — use tailor-resume-n-fill-form for that.

The job IDs to process are: **$ARGUMENTS**

Parse `$ARGUMENTS` as a space-separated list of job ID tokens (no URL parsing — this skill never visits an application form, so explicit apply URLs are not needed).

Examples:
- `abc123` → one job
- `abc123 def456` → two jobs

Run Steps 0–4 for **each job ID in sequence**, then run Steps 5–7 once at the end to batch-commit and sync everything.

---

## Constants (resolved at runtime — device-agnostic)

Resolve these once before starting the loop.

**`PUBLIC`** — the root of this repository. Derive from the skill file's own location (two levels up from `.claude/commands/`), or confirm with:
```powershell
$PUBLIC = (Get-Location).Path   # Claude is always invoked from the repo root
```

**`PRIVATE`** — the private companion repo. Resolve in this order and stop at the first hit:
1. The environment variable `MANJU_PRIVATE_DIR` if set.
2. A sibling of PUBLIC whose name contains "private" (case-insensitive):
   ```powershell
   $parent  = Split-Path $PUBLIC -Parent
   $PRIVATE = Get-ChildItem $parent -Directory |
              Where-Object { $_.Name -match 'private' } |
              Select-Object -First 1 -ExpandProperty FullName
   ```
3. A sibling of PUBLIC that contains a `Resumes\` subfolder:
   ```powershell
   $PRIVATE = Get-ChildItem $parent -Directory |
              Where-Object { Test-Path "$($_.FullName)\Resumes" } |
              Select-Object -First 1 -ExpandProperty FullName
   ```
4. If still not found — stop and ask the user to set the `MANJU_PRIVATE_DIR` environment variable to the correct path, then re-run.

**`JOBS_JSON`** = `PUBLIC\jobs.json`

Print the resolved paths before starting the loop:
```
PUBLIC  : <resolved path>
PRIVATE : <resolved path>
```

Read the structural template **once** before the loop:
Read `PRIVATE\Resumes\Master\master_data.json`. Every output JSON must match this structure exactly (same keys, same nesting).

---

## Checkpoint Check — runs once before the loop

Canonical step order: `0 → 1 → 2 → 3 → 4 → 4.5`

For each JOB_ID in the list, check whether `PRIVATE\Resumes\JOB_ID\JOB_ID_checkpoint.json` exists.

If **no** checkpoint exists for a job, set `START_STEP[JOB_ID] = "0"` (start fresh, no prompt).

If a checkpoint **does** exist, read it and display a block like this for each such job:

```
Checkpoint found — abc123 (Legal Trainee @ Hiab)
  Completed : 0, 1, 2, 3
  Last run  : 2026-07-01 10:30
  Next step : 4 (Generate PDFs)

  [Enter] Continue from Step 4        ← default
  [2]     Redo from Step 2 (Write tailored JSON)
  [1]     Redo from Step 1 (Fetch description)
  [0]     Start completely fresh
  [skip]  Skip this job this run
```

Ask the user for their choice for each job that has a checkpoint. Set `START_STEP[JOB_ID]` to the chosen step (or `"skip"` to exclude that job from the loop entirely).

If the user chooses `[0]` (fresh), delete the existing checkpoint file before entering the loop.

---

## Loop — repeat Steps 0–4 for each JOB_ID

**If `START_STEP[JOB_ID]` is `"skip"`, skip this job entirely.**

**Skip rule:** At the start of each step, if the step ID comes *before* `START_STEP[JOB_ID]` in the canonical order `[0, 1, 2, 3, 4, 4.5]`, print `↷ Skipping Step N (checkpoint)` and move to the next step. Step 4.5 is the one exception: it **always** runs whenever Step 4 runs (fresh or resumed) and is never skipped by checkpoint state, since it is what catches a broken Step 4 output.

**Checkpoint write rule:** After each step completes successfully, write or update `PRIVATE\Resumes\JOB_ID\JOB_ID_checkpoint.json`:
```json
{
  "job_id": "JOB_ID",
  "job_title": "JOB_TITLE",
  "company": "COMPANY",
  "updated_at": "<ISO timestamp>",
  "completed_steps": ["0", "1", ...]
}
```
Add the current step's ID to `completed_steps` if not already present. Preserve all previously completed steps.

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

### Step 2 — Write the tailored data.json

Create folder `PRIVATE\Resumes\JOB_ID\` if it does not exist.
Write the tailored JSON to `PRIVATE\Resumes\JOB_ID\JOB_ID_data.json` — overwrite if it exists.

#### Tailoring rules

**Top-level fields:**
- `job_id`: set to `JOB_ID`
- `job_title`: set to `JOB_TITLE` (exact string from jobs.json)
- `company`: set to `COMPANY`
- `tailored_at`: set to the current ISO timestamp (e.g., `"2026-07-16T12:00:00+03:00"`) representing the exact time you are running this skill.
- `tailor_model`: set to `"claude-sonnet-4-6"`

**`resume.name`:** Always `"Manju Krishna Haridas"` — copy verbatim from the template. Never omit this field; `make_resume.py` silently renders a blank header line if it's missing.

**`resume.contact`:** Always copy the entire object verbatim from the template (`address`, `phone`, `email`, `linkedin_url`, `linkedin_display`) — these are static and never job-specific. Never omit this object; a missing `contact` silently renders a blank line under the name with no error.

**`resume.role`:** `"JOB_TITLE Candidate"`

**`resume.profile`:** 2–3 sentences, highly specific to this role and company. Directly connect Manju's most relevant background to the stated requirements. Do not just summarise her CV — name the company and what they need.

**`resume.experience`:** Keep all four entries exactly as in the template (same dates, companies, titles). Reorder the four entries so the most relevant experience appears first. Within each entry, reorder and reword the bullets to front-load skills mentioned in the job description.

**`resume.education`:** Keep all entries as in the template, **using the exact same keys** (`qual`, `inst`, and `bold` where set). Do not rename these keys (e.g. to `degree`/`school`) — `make_resume.py` reads `qual`/`inst` specifically and silently renders blank rows for any other key names.

**`resume.languages_html`:** For Finnish-language postings, put Finnish first. For English-language postings, keep English first.

**`resume.wage_subsidy_note`:** Always copy verbatim from the template. `make_resume.py` renders this as a highlighted banner directly under the header, above Professional Profile — this is deliberate, since palkkatuki eligibility is critical information for the employer's hiring decision and should be visible immediately, not buried in a skills list.

**`resume.competencies_html`:** Completely rewrite 4–5 skill categories that map directly onto the key requirements in this job description. Use `<span class="skill-cat">Category:</span> description...` format.

**`resume.references`:** Always copy the entire array verbatim from the template (same names, titles, contacts). Never omit this array; a missing `references` silently renders an empty "REFERENCES" section heading with no content and no error.

**`cover_letter.date`:** Use today's date formatted as `"30 June 2026"`.

**`cover_letter.recipient`:** Fill `company` with `COMPANY` and `city` with the job location. Use `"Hiring Manager"` for title if no name is known.

**`cover_letter.paragraphs`:** 5–6 paragraphs written in the **same language as the job posting** (Finnish for Finnish postings, English for English postings):
  1. Hook — what drew Manju to this company and role specifically.
  2. Most relevant experience — connect it directly to the job requirements.
  3. Finland integration — Finnish B2, Oulu roots, IHO internship, OPH bar path.
  4. Why this company — something specific from the posting or company.
  5. Wage subsidy (palkkatuki) — mention her eligibility and offer to handle her part of the joint application. English: "I'm eligible for wage subsidy support (palkkatuki), and would be glad to handle my part of the joint application with BusinessOulu if this makes hiring more accessible for your organization." Translate naturally to Finnish for Finnish-language postings.
  6. Close — availability (next possible working day), contact invitation.

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
- Finnish B2, English C1, Malayalam native. Based in Oulu. Available: next possible working day.
- Eligible for palkkatuki (wage subsidy) via BusinessOulu employment services — approx. 50% wage cost support for employer.
- Open to relocation within Finland, including Helsinki.
- Enthusiastic about AI and digital tools in legal work; experienced applying digital solutions to streamline legal processes.
- Co-organised 'Namaste Oulu', a cross-cultural event during the IHO internship — coordination with city authorities, community groups, and sponsors.
- At Poise Legal: also developed and maintained contract templates and risk registers; coordinated with external counsel and client representatives as an in-house advisory interface.
- Third reference available: Jaana Liukkonen, Teacher at OSAO — jaana.liukkonen@osao.fi, +358 40 570 7593.

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

### Step 4.5 — Validate the generated resume

`make_resume.py` has no required fields — every value defaults to `""` if a key is missing or misnamed, so a broken `data.json` produces a resume that *looks* generated (files exist, PDF opens fine) but has silently blank sections. This step exists to catch that before it goes anywhere.

**Always run this step whenever Step 4 runs** — never skip it, including on a checkpoint-resume.

1. Read `PRIVATE\Resumes\JOB_ID\JOB_ID_data.json` and confirm ALL of the following are present and non-empty:
   - `resume.name`
   - `resume.contact.address`, `resume.contact.phone`, `resume.contact.email`
   - `resume.education` — non-empty array, and **every** entry has non-empty `qual` and `inst`
   - `resume.experience` — non-empty array, and every entry has non-empty `title`, `company`, `dates`, and at least one bullet
   - `resume.languages_html`, `resume.competencies_html`
   - `resume.references` — non-empty array, and every entry has non-empty `name`, `title`, `contact`
   - `cover_letter.paragraphs` — non-empty array with at least 3 paragraphs

2. If anything fails: fix `JOB_ID_data.json` (pull `name`/`contact`/`references` verbatim from the template read at the start of this skill; rename any wrong education keys to `qual`/`inst`), then redo Step 3 and Step 4 to regenerate, and re-check from the top of this step.

3. Once the JSON check passes, read the regenerated resume PDF itself (via the Read tool) and visually confirm PROFESSIONAL PROFILE, EDUCATION, and REFERENCES actually contain rendered text — not just present-but-empty section headings. This catches template/rendering bugs that a JSON-only check would miss.

Do not proceed to the next job or to Step 5 until validation passes. Print: `✓ JOB_ID — resume validated (all sections populated)`.

---

## End of loop

---

## Step 5 — Commit all jobs to private repo (one commit)

```powershell
git -C "PRIVATE" add Resumes\
git -C "PRIVATE" commit -m "Tailor resumes for N jobs: JOB_ID_1, JOB_ID_2, ... (claude-sonnet-4-6)"
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
