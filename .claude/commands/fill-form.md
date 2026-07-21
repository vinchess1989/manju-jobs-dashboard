Open a single job's application form in a visible, already-logged-in browser and fill it using your own judgment — ensures a Claude-tailored resume/cover letter exist first, resolves the real form URL via find-apply-link, then pauses before submit so Manju can review and click submit herself.

The job ID is: **$ARGUMENTS**

Parse `$ARGUMENTS` as a single `JOB_ID` (the first whitespace-separated token). If empty, ask the user for a job ID before proceeding.

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
   - `question_count > 0` → generate tailored answers exactly per **Step 1.6** of `tailor-resume-n-fill-form.md` (factual-field values, language matching the question, no invented facts) and write `JOB_ID_answers.json` + the cheatsheet HTML.
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
