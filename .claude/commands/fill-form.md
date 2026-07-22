Open a single job's application form in a visible, already-logged-in browser and fill it using your own judgment — ensures a Claude-tailored resume/cover letter exist first, resolves the real form URL via find-apply-link, then pauses before submit so Manju can review and click submit herself. With no job ID given, instead runs the full discovery flow first (find near-deadline unapplied jobs → verify liveness → flag expired ones for deletion → build a reasoned checklist → let Manju pick) and then applies the single-job flow to whatever she picks.

The arguments are: **$ARGUMENTS**

Parse `$ARGUMENTS` by space-separated tokens:
- Any token matching `^[0-9a-fA-F]{8}$` (case-insensitive) is treated as an explicit `JOB_ID`.
- Any token matching `^post<(\d+)$` or `^posted<(\d+)$` (case-insensitive) extracts `POSTED_DAYS_LIMIT` (e.g. `post<3` means jobs posted in the last 3 days, i.e., `posted_date >= today - 3 days`).
- Any token matching `^dead<(\d+)$` or `^deadline<(\d+)$` (case-insensitive) extracts `DEADLINE_DAYS_LIMIT` (e.g. `dead<3` means jobs expiring in the next 3 days, i.e., `today <= deadline <= today + 3 days`).

**If no explicit `JOB_ID` token is given**: Run Step -1 (discovery mode) using the parsed `POSTED_DAYS_LIMIT` and/or `DEADLINE_DAYS_LIMIT` filters, then come back and run Steps 0–6 for each job selected there.

Examples:
- `/fill-form 1ee84312` — process single explicit job ID
- `/fill-form post<3 dead<3` — discover unapplied jobs posted in the last 3 days AND expiring within the next 3 days
- `/fill-form dead<5` — discover unapplied jobs expiring within the next 5 days
- `/fill-form` — discover unapplied jobs expiring today or tomorrow (default)

---

## Constants (resolved at runtime — device-agnostic)

**`PUBLIC`** — repo root. `$PUBLIC = (Get-Location).Path`

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
4. If still not found — stop and ask the user to set `MANJU_PRIVATE_DIR`, then re-run.

**`JOBS_JSON`** = `PUBLIC\jobs.json` — read-only lookup only.

**`AUTOMATION_PROFILE`** = `$env:LOCALAPPDATA\Google\Chrome\Automation Profile` — the persistent Chrome profile with Manju's saved logins (LinkedIn, Eezy Talents, etc.). Always launch against this profile, never a fresh/incognito context, so platforms she's already authenticated on don't hit a login wall. See `.agents\skills\open_visible_browser\SKILL.md` and the `talent.core.eezy.fi` entry in `site_patterns.json` for the working reference pattern.

---

## Step -1 — Discovery mode (no explicit JOB_ID given)

Only runs when no explicit `JOB_ID` token is provided. Reproduces the end-to-end flow validated manually on 2026-07-21: find unapplied jobs matching date filters (`post<X` and/or `dead<Y`), verify each is genuinely still open, flag truly expired ones for deletion, build a reasoned fit checklist for what's left, let Manju pick, then fall through to Steps 0–6 for each pick.

### -1.0 — Pull latest jobs.json

```powershell
git pull --rebase origin main
```
If `git status --short` shows unrelated pre-existing modified tracked files (e.g. from a concurrent session), stash just those paths first, pull, then pop — never discard someone else's in-progress work. See `CLAUDE.md`'s git hygiene section.

### -1.1 — Find unapplied jobs matching date filters

Calculate filter dates based on parsed `$ARGUMENTS`:
- **Deadline filter (`dead<Y`)**: If `dead<Y` is given, filter jobs with `deadline` between `$today` and `$today + Y days`. If neither `dead` nor `post` is specified, default to `Y = 1` (today or tomorrow).
- **Posted filter (`post<X`)**: If `post<X` is given, filter jobs with `posted_date` between `$today - X days` and `$today`.

```powershell
$today = (Get-Date).ToString("yyyy-MM-dd")
```
Read `JOBS_JSON`. Candidates are entries satisfying the active `posted_date` and `deadline` filters, **and** where `applied` is not `"yes"`.

For each candidate, also check Firestore's `applied` field (`python job_status_store.py get --url "JOB_URL" --field applied`) — jobs.json's cached `applied` can lag behind what's actually been submitted. Drop any job where **either** source says `"yes"` (jobs already handled don't need re-triage).

If the raw candidate count is large, it's fine to narrow further using `matches_requirements` (prioritize `"yes"`/`"maybe"` over `"no"`) to keep the liveness-check pass manageable — state the excluded count when reporting so nothing silently vanishes.

### -1.2 — Verify each candidate is still genuinely open

For each remaining candidate:
- **tyomarkkinatori.fi** listings: use the cached `api` strategy in `site_patterns.json` (`https://tyomarkkinatori.fi/api/jobposting-new/v1/public/jobpostings/{id}`) — check `metadata.status` (4 = active, 5 = closed) and `application.expires`. Don't rely solely on jobs.json's cached `deadline`: the live `expires` value can be later than the cached one (extended deadline — treat as not urgent, no deletion action needed) or the status can already be 5 before the cached deadline even passes.
- **Other domains**: WebFetch the `url`. Ask a narrow, UI-only question — do **not** ask the model to reason about the deadline date, since that reasoning has proven unreliable (confirmed this session: it misclassified a still-open listing as expired purely from flawed date arithmetic). Use a prompt along the lines of: *"Reply ACTIVE if there is a live 'Apply'/'Hae paikkaa' button or open application form on this page. Reply CLOSED if the page explicitly states the position is filled, applications are no longer accepted, or the listing was removed. Do not reason about the deadline date — only report what the page's UI currently shows."*

### -1.3 — Flag genuinely expired/closed jobs for deletion

For each candidate confirmed CLOSED in -1.2, apply the **mark-job-deleted** skill technique (`.claude/commands/mark-job-deleted.md`), including its **applied guard**: if either jobs.json or Firestore already says `applied == "yes"` for that job, do not auto-delete — report it and ask the user first (leaving it alone is a valid outcome — a completed application shouldn't disappear from the dashboard just because the listing expired). Otherwise set `deletion_reason` in Firestore directly with no confirmation needed.

### -1.4 — Build a reasoned checklist for what's left

For every candidate confirmed ACTIVE, read its `description_file` (accept it if it has more than 200 meaningful words after the `JOB DESCRIPTION:` header; otherwise WebFetch the job's `url`, or search `"JOB_TITLE" "COMPANY" Finland job` as a last resort) and write one row of honest fit reasoning per job: title, company, location, deadline, and an assessment against Manju's actual profile (Oulu-based, LL.M./LL.B. legal background, International House Oulu event-coordination + digital-tools experience, B2 Finnish / C1 English, driving license, palkkatuki-eligible). Call out location mismatches, hard-requirement gaps (e.g. SAP/procurement track record, industrial certifications, marketing-tech skills), and role-type issues (e.g. commission-only/entrepreneurial roles) as plainly as genuine strengths — don't inflate weak matches to pad the list. Present this as a table.

### -1.5 — Let Manju select

Ask which job ID(s) to proceed with — a plain-text question is fine (a checklist can easily run past `AskUserQuestion`'s 4-option cap). While waiting on her answer, for every checklisted job that is ultimately **not** selected, set `matches_requirements = "no"` and `user_reason = <the fit assessment written in -1.4>` in Firestore via `job_status_store.py`. This is what the live dashboard reads as an override on top of jobs.json's own `matches_requirements`/`reason` fields, so it corrects the scraper's classification for anyone reviewing the dashboard later — without ever touching `jobs.json` itself.

### -1.6 — Apply Steps 0–6 to each selected job

For each `JOB_ID` Manju selects, run Steps 0 through 6 below exactly as if that ID had been passed as `$ARGUMENTS`.

---

## Step 0 — Resolve the job

Read `JOBS_JSON`, find the entry with `id == JOB_ID`. If not found, abort with an error rather than guessing.

Record `JOB_TITLE`, `COMPANY`, `JOB_URL`.

---

## Step 1 — Ensure a Claude-tailored resume and cover letter exist

Check whether `PRIVATE\Resumes\JOB_ID\JOB_ID_data.json` exists, whether matching resume/cover-letter PDFs exist alongside it, and whether `data.json`'s `tailor_model` field contains `"claude"` (case-insensitive).

- **All true** → use as-is. Print `Using existing Claude-tailored docs for JOB_ID.`
- **Anything false or missing** → run the **tailor-resume** skill for this job (`.claude/commands/tailor-resume.md`, i.e. `/tailor-resume JOB_ID`) to generate or redo the resume/cover letter, then re-check.

Locate the exact filenames once docs are confirmed:
```powershell
$resumePdf = Get-ChildItem "PRIVATE\Resumes\JOB_ID\*_resume.pdf"        | Select-Object -First 1 -ExpandProperty FullName
$coverPdf  = Get-ChildItem "PRIVATE\Resumes\JOB_ID\*_cover_letter.pdf"  | Select-Object -First 1 -ExpandProperty FullName
```
Abort if either is still missing after tailoring.

---

## Step 2 — Resolve the application form URL

Priority order, stopping at the first hit:

1. **Firestore cache**:
   ```powershell
   python job_status_store.py get --url "JOB_URL" --field apply_email
   python job_status_store.py get --url "JOB_URL" --field apply_url
   ```
   - `apply_email` present (not `NONE`) → email-only, see below.
   - `apply_url` present (not `NONE`) → `APPLY_URL = <that value>`.
2. Otherwise, apply the **find-apply-link** skill technique (`.claude/commands/find-apply-link.md`) using `JOB_URL` as `BASE_URL` and `JOB_ID` as `JOB_ID`. It resolves multi-hop "Apply" chains and JS-rendered links, and self-persists whatever it finds to Firestore (`apply_url`/`apply_email`) so this lookup is instant next time.
   - `RESULT_TYPE: form` → `APPLY_URL = RESULT`.
   - `RESULT_TYPE: email` → email-only, see below.
   - `RESULT_TYPE: not_found` → fall back to `JOB_URL` itself, and warn the user this may just be the listing page rather than the real form.

**Email-only jobs:** if the resolved result is an email address, there is no form to fill. Print `JOB_ID applies via email only (ADDRESS) — no form to fill.`, list the exact `$resumePdf` / `$coverPdf` paths from Step 1 so Manju can attach them herself, and **stop here** — do not continue to Step 3.

---

## Step 3 — Get the form's fields and draft answers

1. If `PRIVATE\Resumes\JOB_ID\JOB_ID_answers.json` already exists and its `apply_url` matches `APPLY_URL`, reuse it as-is and skip to Step 4.
2. Otherwise, extract the form's questions:
   ```powershell
   python "PUBLIC\scrape_application.py" --job-url "APPLY_URL" --job-id "JOB_ID" --out-dir "PRIVATE\Resumes\JOB_ID" --private-dir "PRIVATE"
   ```
   - `question_count > 0` → generate tailored answers and write `JOB_ID_answers.json` + the cheatsheet HTML. **Answer rules:** text/textarea fields get 1–4 sentences (or a full paragraph for open-ended ones), naming the company/role where it fits; select/dropdown fields pick the closest matching option; answer in the same language as the question; never invent facts not in Manju's profile. **Known factual fields** — read these from `PRIVATE\Resumes\Master\master_data.json`'s `resume.contact` (or hardcode if faster):
     - Date of birth: `contact.date_of_birth` (`1990-07-25`, i.e. 25 July 1990) — use for any birth-date field (split into year/month/day sub-fields if the form asks for them separately).
     - Phone / salary expectation: leave blank, mark as a placeholder for manual fill.
     - Address: `Oulu, Finland`.
     - Availability: `Next possible working day`.
     - Willing to relocate: `Yes — open to relocation within Finland, including Helsinki`.
     - Right to work in Finland: `Yes — EU residence permit` (on forms with a structured work-permit dropdown instead of free text, pick the option meaning "I hold a valid work/residence permit", not "EU/Finnish citizen").
   - 0 questions / failure (e.g. a login-wall redirect) → no answers file will exist. You'll inspect the live form yourself once the browser is open in Step 5 — use WebFetch or a quick throwaway Playwright inspection script against `APPLY_URL` beforehand if you need the field structure before writing the fill script.

---

## Step 4 — Launch Chrome (CDP mode)

We use a detached browser architecture. The automation script connects to Chrome over CDP (port 9222) so it can open new tabs without locking up the browser, allowing multiple forms to be filled sequentially and left open for review.

```powershell
$port_open = Test-NetConnection -ComputerName 127.0.0.1 -Port 9222 -WarningAction SilentlyContinue
if (-not $port_open.TcpTestSucceeded) {
    Write-Host "Launching visible Chrome via CDP..."
    Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue
    taskkill /F /IM chrome.exe /T
    $batPath = "PUBLIC\scratch\launch_cdp_chrome.bat"
    Set-Content -Path $batPath -Value "@echo off`n`"C:\Program Files\Google\Chrome\Application\chrome.exe`" --remote-debugging-port=9222 --user-data-dir=`"$env:LOCALAPPDATA\Google\Chrome\Automation Profile`""
    cmd /c "schtasks /delete /tn `"AntigravityVisibleBrowser`" /f & schtasks /create /tn `"AntigravityVisibleBrowser`" /tr `"\`"$batPath\`"`" /sc once /st 00:00 /ru vinee /it /f & schtasks /run /tn `"AntigravityVisibleBrowser`""
    Start-Sleep -Seconds 4
}
```

---

## Step 5 — Write and Run the Fill Script

Create `PUBLIC\scratch\hardcoded_fill_JOB_ID.py`. It must:

```python
import os
import time
from playwright.sync_api import sync_playwright

url = "APPLY_URL"

with sync_playwright() as p:
    print("Connecting to Chrome over CDP...")
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    context = browser.contexts[0]
    
    # Reuse existing tab if URL matches, otherwise open a new one
    page = None
    for existing_page in context.pages:
        if url in existing_page.url:
            page = existing_page
            print("Reusing existing tab for this job!")
            page.bring_to_front()
            break
            
    if not page:
        print("Opening new page...")
        page = context.new_page()
        page.goto(url)
        page.set_default_timeout(3000)
        page.wait_for_load_state("load")
    else:
        page.set_default_timeout(3000)

    # ... hardcoded Playwright locators + fill/select calls for every field,
    #     using the values from JOB_ID_answers.json (or your own live reading
    #     of the form if no answers.json exists) ...
    # ... attach $resumePdf and $coverPdf to whatever file-upload input(s) exist ...

    print("Form filled. Disconnecting...")
    browser.close()
```

- Run the script: `python -u PUBLIC\scratch\hardcoded_fill_JOB_ID.py`
- **Form Filling Rules**:
  - Always use the LinkedIn profile link from Manju's resume for the LinkedIn profile field (do not leave it empty).
  - If asked about employment status, always answer "not currently employed" (or the equivalent "no").
  - If asked if the application can be used for other applications/future opportunities, always answer "yes" / agree to it.
  - If asked how she heard about the job, look up the `source` column for this job in `jobs.json` and use that value.
  - If asked for date of birth, use `1990-07-25` (25 July 1990) — from `master_data.json`'s `resume.contact.date_of_birth`.
- **Never click the final submit button.** Leave the form filled and waiting for review.

---

## Step 6 — Hand off for manual review

Print:
```
JOB_ID (JOB_TITLE @ COMPANY) — form opened and filled at APPLY_URL.
Resume       : $resumePdf
Cover letter : $coverPdf
Review the filled form in the browser window, then click submit yourself — this skill never submits automatically.
```

Wait for the user to confirm they've reviewed and submitted (or otherwise closed the browser) before considering the task done. Do not mark the job `applied` anywhere automatically — that's a separate, explicit action the user takes.

## Application Form Rules
- The field for linkedin profile is left empty. Use the linkedin profile link from the resume.
- I'm not currently employed.
- My application can be used for other applications.
- Whenever they ask how did we hear about the job, mention the source column corresponding to this job in dashboard.
