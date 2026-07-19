Tailor fresh resumes and cover letters for one or more job IDs using Claude, scrape the application form and generate tailored answers, replacing any existing docs and updating the live dashboard.

The job IDs to process are: **$ARGUMENTS**

Parse `$ARGUMENTS` as a space-separated list of tokens. Build a job list and an explicit-URL map as follows:

- Any token that starts with `http://` or `https://` is treated as an **explicit apply URL** for the immediately preceding job ID token.
- All other tokens are job IDs.

Examples:
- `abc123` → one job, no explicit URL
- `abc123 def456` → two jobs, no explicit URLs
- `abc123 https://example.com/apply` → one job, explicit apply URL for `abc123`
- `abc123 https://example.com/apply def456` → two jobs; `abc123` has an explicit URL, `def456` does not

Store the result as a list of `(JOB_ID, EXPLICIT_APPLY_URL | null)` pairs. Run Steps 0–5 for **each pair in sequence**, then run Steps 6–8 once at the end to batch-commit and sync everything.

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
Read `PRIVATE\Resumes\f6aaa66f\f6aaa66f_data.json`. Every output JSON must match this structure exactly (same keys, same nesting).

---

## Git sync — runs once before the loop, before any other git operation

Tailoring can happen on a different machine than the one running the scraper, and the scraper commits+pushes to `PUBLIC` roughly every 12 minutes. Skipping this step is how local work ends up silently stranded (unpushed) for days and collides with the scraper's commits — see `CLAUDE.md` for the full story. Do this before touching any file:

1. **Pull PRIVATE:** `git -C "PRIVATE" pull --rebase`
2. **Pull PUBLIC:** `git -C "PUBLIC" pull --rebase`. This should almost always be a clean fast-forward/rebase now that `jobs.json` is scraper-only (see the Git sync rule in `CLAUDE.md`). If it still conflicts (e.g. leftover legacy edits), resolve per-entry by keeping the union of fields from both sides rather than blindly picking one — never discard a field just to make the conflict go away.
3. **Catch stranded work from a previous session:** `git -C "PUBLIC" rev-list --count origin/main..HEAD`. If this is non-zero, a prior session already committed locally but never pushed — push it now, before starting any new work, using the retry logic in Step 7. Do not let it accumulate further.

Print: `Git sync done — PUBLIC and PRIVATE up to date.`

---

## Checkpoint Check — runs once before the loop

Canonical step order: `0 → 1 → 1.5 → 1.6 → 2 → 3 → 4 → 4.5`

For each JOB_ID in the list, check whether `PRIVATE\Resumes\JOB_ID\JOB_ID_checkpoint.json` exists.

If **no** checkpoint exists for a job, set `START_STEP[JOB_ID] = "0"` (start fresh).

If a checkpoint **does** exist indicating that Step 4 was completed (or if you see that `PRIVATE\Resumes\JOB_ID\JOB_ID_data.json` and the corresponding PDFs already exist), you must first read `JOB_ID_data.json` and check the `"tailor_model"` field:
- If `"tailor_model"` contains `"claude"` (case-insensitive), **automatically skip Steps 0-4 for this job** and jump straight to **Step 4.5 (Validate the generated resume)**, then on to the **Application Fill Phase**! Print a note: `Docs already tailored by Claude for JOB_ID. Auto-skipping tailoring and jumping straight to form fill.` A `tailor_model` of Claude does **not** guarantee the data schema was actually complete — always run Step 4.5 even on this fast path, never skip straight past it.
- If `"tailor_model"` does **not** contain `"claude"` (e.g., it is a Local LLM or Gemini), you **MUST** redo the tailoring from Step 2 to override it with Claude's superior tailoring. Print a note: `Docs were tailored by a different model. Redoing tailoring with Claude.`

Do not pause to ask the user for confirmation on any of this unless they explicitly included the word "redo" in their prompt.

---

## Loop — repeat Steps 0–4 for each JOB_ID

**If `START_STEP[JOB_ID]` is `"skip"`, skip this job entirely.**

**Skip rule:** At the start of each step, if the step ID comes *before* `START_STEP[JOB_ID]` in the canonical order `[0, 1, 1.5, 1.6, 2, 3, 4, 4.5]`, print `↷ Skipping Step N (checkpoint)` and move to the next step. Step 4.5 is the one exception: it **always** runs whenever Step 4 runs (fresh or resumed) and is never skipped by checkpoint state, since it is what catches a broken Step 4 output.

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

### Step 1.5 — Scrape application form questions (best-effort)

**Resolve the apply URL first.** Listing pages (Jobly, Duunitori, etc.) don't host the form — they link out to it, sometimes through more than one hop, and some sites (e.g. tyomarkkinatori.fi) render the real apply link client-side via JavaScript so it never appears as text anywhere in the description. Before running the scraper, find the real apply URL in this priority order, stopping at the first hit:

1. **Explicit URL from arguments** — if `EXPLICIT_APPLY_URL` is set for this job (passed on the command line), use it directly. Print: `Using explicit apply URL (from arguments): EXPLICIT_APPLY_URL`
2. Check Firestore for a cached result on this job's URL — this is often already populated by a previous run of Step 3 below or by `/find-apply-link` run standalone. **Never read (or write) `apply_url`/`apply_email` from `jobs.json` itself** — that file is scraper-owned; this metadata lives in Firestore instead (see `CLAUDE.md`).
   ```powershell
   python job_status_store.py get --url "JOB_URL" --field apply_email
   python job_status_store.py get --url "JOB_URL" --field apply_url
   ```
   - If `apply_email` is present (not `NONE`) → set `EMAIL_ONLY[JOB_ID] = <that email>`. Print: `JOB_ID applies via email only (cached) — skipping form scrape/fill; resume and cover letter will still be generated.` Skip the scraper invocation and Step 1.6 for this job (do **not** abort — proceed to Step 2 normally so the PDFs still get generated). Skip priorities 3–5 below.
   - Else if `apply_url` is present (not `NONE`) → use it directly, continue below. Skip priorities 3–5 below.
   - Else → fall through to priority 3.
3. **Apply the find-apply-link skill technique** (see `.claude/commands/find-apply-link.md`) using `JOB_URL` as `BASE_URL` and `JOB_ID` as `JOB_ID`. It resolves multi-hop "Apply" chains and JS-rendered apply links using a cached per-domain strategy, and self-persists the result to Firestore (`apply_url` or `apply_email`, via `job_status_store.py`) for future runs.
   - `RESULT_TYPE: form` → use `RESULT` as the apply URL, continue below.
   - `RESULT_TYPE: email` → set `EMAIL_ONLY[JOB_ID] = RESULT` (the email address). Print: `JOB_ID applies via email only (RESULT) — skipping form scrape/fill; resume and cover letter will still be generated.` Skip the scraper invocation and Step 1.6 for this job (do **not** abort — proceed to Step 2 normally so the PDFs still get generated).
   - `RESULT_TYPE: not_found` → fall through to priority 4 below.
4. Scan the job description text obtained in Step 1 for a URL following apply-related keywords (cheap, no network cost — try this before giving up). Match any of these patterns (case-insensitive):
   - Finnish: `Jätä hakemus:`, `Hae paikkaa:`, `hakemuslinkki:`, `Hakemukset:`, `Hae tästä:`
   - English: `Apply here:`, `Apply at:`, `Application link:`, `Submit.*application:`
   - Generic: any bare URL that appears on its own line immediately after the word "hakemus" or "apply"
5. If nothing found anywhere, fall back to `JOB_URL`.

If `EMAIL_ONLY[JOB_ID]` was just set in step 3 above, skip the rest of this step (scraper + Step 1.6) entirely for this job and continue to Step 2.

Otherwise, set `SCRAPE_URL` to whichever URL was found. Print: `Scraping apply URL: SCRAPE_URL`

Run the scraper. Non-blocking — if it finds nothing or errors, continue to Step 2 normally.

```powershell
python "PUBLIC\scrape_application.py" `
    --job-url "SCRAPE_URL" `
    --job-id  "JOB_ID" `
    --out-dir "PRIVATE\Resumes\JOB_ID" `
    --private-dir "PRIVATE"
```

**First-time behaviour:** If credentials for the platform aren't saved yet, the script prompts interactively (password hidden). They are saved to `PRIVATE\.env` and session cookies to `PRIVATE\sessions\` — all future runs are silent.

**Outcome:**
- Success → `PRIVATE\Resumes\JOB_ID\JOB_ID_questions.json` written. Note `question_count`.
- Failure / 0 questions → skip Step 1.6 for this job, continue from Step 2.
- **Expired listing** → if `JOB_ID_questions.json` exists and contains `"expired": true`:
  - Check whether the job's `applied` status is `"yes"` (read `jobs.json` and check `job.applied`, or read the scraper output message — the scraper already called `move_job_to_deleted` if not applied).
  - If applied == "yes": print `Expired but already applied — continuing tailoring.` and proceed to Step 2 normally.
  - If not applied: print `EXPIRED: Job listing is no longer active. Job moved to deleted.json. Skipping tailoring.` and **abort this job** (do not run Steps 2–4 for it). Continue to the next job ID in the loop if processing multiple.

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
- `tailored_at`: set to the current ISO timestamp (e.g., `"2026-07-16T12:00:00+03:00"`) representing the exact time you are running this skill.
- `tailor_model`: set to `"claude-sonnet-4-6"`

**`resume.name`:** Always `"Manju Krishna Haridas"` — copy verbatim from the template. Never omit this field; `make_resume.py` silently renders a blank header line if it's missing.

**`resume.contact`:** Always copy the entire object verbatim from the template (`address`, `phone`, `email`, `linkedin_url`, `linkedin_display`) — these are static and never job-specific. Never omit this object; a missing `contact` silently renders a blank line under the name with no error.

**`resume.role`:** `"JOB_TITLE Candidate"`

**`resume.profile`:** 2–3 sentences, highly specific to this role and company. Directly connect Manju's most relevant background to the stated requirements. Do not just summarise her CV — name the company and what they need.

**`resume.experience`:** Keep all four entries exactly as in the template (same dates, companies, titles). Reorder the four entries so the most relevant experience appears first. Within each entry, reorder and reword the bullets to front-load skills mentioned in the job description.

**`resume.education`:** Keep all entries as in the template, **using the exact same keys** (`qual`, `inst`, and `bold` where set). Do not rename these keys (e.g. to `degree`/`school`) — `make_resume.py` reads `qual`/`inst` specifically and silently renders blank rows for any other key names.

**`resume.languages_html`:** For Finnish-language postings, put Finnish first. For English-language postings, keep English first.

**`resume.competencies_html`:** Completely rewrite 4–5 skill categories that map directly onto the key requirements in this job description. Use `<span class="skill-cat">Category:</span> description...` format.

**`resume.references`:** Always copy the entire array verbatim from the template (same names, titles, contacts). Never omit this array; a missing `references` silently renders an empty "REFERENCES" section heading with no content and no error.

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

### Step 4.5 — Validate the generated resume

`make_resume.py` has no required fields — every value defaults to `""` if a key is missing or misnamed, so a broken `data.json` produces a resume that *looks* generated (files exist, PDF opens fine) but has silently blank sections. This step exists to catch that before the resume ever reaches an application form.

**Always run this step whenever Step 4 runs** — fresh, resumed from checkpoint, or auto-skipped straight here via the `tailor_model` fast path above. Never skip it.

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

Do not proceed to the Application Fill Phase or the next job until validation passes. Print: `✓ JOB_ID — resume validated (all sections populated)`.

---

## End of loop

---

## Application Fill Phase — Interactive Hardcoded Script

Instead of using a generic API-based fill agent, you (the AI) must use your own intelligence in the chat to create a custom hardcoded Playwright Python script for each job that needs to be filled!

Only run this phase for jobs that produced a `JOB_ID_answers.json` file **and** are not in `EMAIL_ONLY`.

For each job ID in `EMAIL_ONLY`, skip this phase entirely and print: `JOB_ID — apply by sending the resume and cover letter PDFs directly to EMAIL_ONLY[JOB_ID].` List the exact PDF paths from `PRIVATE\Resumes\JOB_ID\` alongside it.

For each remaining job ID in this phase:
1. **Analyze the form:** Read `JOB_ID_answers.json`. If you need more information about the form's HTML structure, use your tools (e.g. `run_command` with python) to fetch the form page and inspect its fields.
2. **Write a custom script:** Create a Python Playwright script at `scratch\hardcoded_fill_JOB_ID.py`.
   - The script must launch a **visible** Chrome browser (`headless=False`).
   - It must navigate to the job's apply URL.
   - It must hardcode the Playwright locators to fill in the specific values from `JOB_ID_answers.json`.
   - It must attach the specific PDF resume and cover letter generated in Step 4.
   - When finished filling, it must **pause indefinitely** (e.g., `page.wait_for_timeout(600000)`) and explicitly NOT submit the form, allowing Manju to review and click submit manually.
3. **Launch via Schtasks:** Because you are running in Session 0, you must apply the `open_visible_browser` skill technique to launch your custom script visibly on the user's desktop!
   - Kill background chrome: `powershell -Command "Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue; taskkill /F /IM chrome.exe /T"`
   - Create a batch wrapper: `scratch\run_hardcoded_fill_JOB_ID.bat` that runs `python -u "PUBLIC\scratch\hardcoded_fill_JOB_ID.py" > "PUBLIC\scratch\fill_JOB_ID.log" 2>&1`
   - Launch it using: `cmd /c "schtasks /delete /tn "AntigravityVisibleBrowser" /f & schtasks /create /tn "AntigravityVisibleBrowser" /tr "\"PUBLIC\scratch\run_hardcoded_fill_JOB_ID.bat\"" /sc once /st 00:00 /ru vinee /it /f & schtasks /run /tn "AntigravityVisibleBrowser""`
4. **Wait for completion:** Wait for the user to confirm they have submitted the form and closed the browser before proceeding to the next job or Step 5.

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

## Step 6.5 — Upload application answers to Firestore

Only run if at least one job produced a `JOB_ID_answers.json` file in this run.

```powershell
python upload_answers.py --job-id JOB_ID_1 JOB_ID_2 ...
```

This pushes each job's answers to the Firestore collection `application_answers` (one document per job_id), fetchable at:
```
https://firestore.googleapis.com/v1/projects/manju-jobs-dashboard/databases/(default)/documents/application_answers/<job_id>
```
No authentication is required to read this (same open-access pattern as the existing `shared_state/job_status` document) — treat these documents as world-readable if the document ID (job_id) is known.

---

## Step 7 — Commit public repo

```powershell
git -C "PUBLIC" add input.csv
git -C "PUBLIC" commit -m "Update resume links for JOB_ID_1 JOB_ID_2 ... (retailored with claude-sonnet-4-6)"
```

If `input.csv` has no changes, skip the commit and note that it was already up to date.

**Push with retry** — the scraper may have pushed again in the time this session has been running (it commits every ~12 min), so a plain push can be rejected as non-fast-forward. Don't treat that as a failure; resolve it the same way the scraper itself does:

```powershell
git -C "PUBLIC" push origin main
```

If rejected: `git -C "PUBLIC" pull --rebase origin main`, resolve any conflict per the `CLAUDE.md` rule (union of fields, never silently drop one side), then retry the push. Repeat up to 3 times total before surfacing it to the user as a real failure — a single rejection here is expected/routine, not exceptional.

---

## Step 8 — Report

Print a summary table for all processed jobs:

| Job ID | Title | Company | Resume PDF | Cover Letter PDF | Firestore | Answers | Apply Method |
|--------|-------|---------|------------|------------------|-----------|---------|---------------|
| abc123 | ... | ... | filename.pdf | filename.pdf | ✓ | ✓ (N questions) | Form |
| def456 | ... | ... | filename.pdf | filename.pdf | ✓ | — | Email: marika@example.com |

Use `Email: EMAIL_ONLY[JOB_ID]` for jobs resolved to `RESULT_TYPE: email` in Step 1.5; otherwise `Form`.

For jobs with an answers upload, print the fetch URL:
```
https://firestore.googleapis.com/v1/projects/manju-jobs-dashboard/databases/(default)/documents/application_answers/<job_id>
```

Then note: "Dashboard links will appear live in the Docs column within ~30 seconds (Firebase realtime sync)."

If any job was skipped, list them with the reason.
