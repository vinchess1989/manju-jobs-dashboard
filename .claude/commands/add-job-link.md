Manually add one or more specific job posting URLs to the dashboard, classify them through the existing local-LLM review pipeline, and publish the result.

The job URL(s) to add are: **$ARGUMENTS**

Parse `$ARGUMENTS` as a whitespace-separated list of `http://`/`https://` tokens. If no URLs are given, ask the user for at least one before proceeding.

---

## Step 0 — Precondition check

This skill classifies new jobs through the same local LLM the automated scraper uses. Confirm LM Studio is running with a model loaded at `http://127.0.0.1:1234` before continuing — if unsure, run `/lmstudio-switch` first to check. If it's not running, warn the user that the job(s) will still be added, but will stay in `pending` status until a review run succeeds with the server up.

---

## Step 1 — For each URL, gather details and check for duplicates

For each URL in the list:

1. Compute `JOB_ID` — the first 8 hex characters of the MD5 hash of the URL string (UTF-8 encoded), matching how `scraper.py` IDs every job:
   ```powershell
   $bytes = [System.Text.Encoding]::UTF8.GetBytes($url)
   $hash  = ([BitConverter]::ToString([System.Security.Cryptography.MD5]::Create().ComputeHash($bytes)) -replace '-', '').ToLower()
   $jobId = $hash.Substring(0, 8)
   ```
2. Check `jobs.json` and `deleted.json` for an existing entry with this URL or ID. If found, report its current status and **skip** this URL — don't re-add it.
3. Use **WebFetch** on the URL to extract the job title, company name, and location. Best-effort only — some sites (LinkedIn especially) block simple fetches or require JS rendering. If extraction is unclear or empty, leave the field blank rather than guessing; the review step below re-fetches the full page itself via Playwright and will still classify the job correctly from its own scrape.

---

## Step 2 — Append to jobs.json

For each URL that passed Step 1 (not a duplicate), run:

```powershell
python add_job.py --url "URL" --title "TITLE" --company "COMPANY" --location "LOCATION"
```

Omit `--title`/`--company`/`--location` (or pass empty strings) if Step 1 couldn't determine them.

This appends a new `pending` entry with `"source": "manual"` and prints the assigned `JOB_ID`, or prints `SKIP:` if it turns out to already be tracked (duplicate check happens again here as a safety net) — or `WARN:` if the URL was previously deleted (expired/blocked) and is now being re-added fresh.

---

## Step 3 — Run the review + publish

Once all new jobs are appended, classify and publish them in one pass:

```powershell
python scraper.py --review-urls URL1 URL2 ...
```

Pass every URL added in Step 2 (space-separated), even ones that were skipped as duplicates — omit those. This reuses the exact same pipeline as the automated scraper: fetches each page via Playwright, classifies it with the local LLM (`matches_requirements`, `reason`, `deadline`, etc.), runs `clean_blocked_jobs()`, appends a history snapshot, commits, pushes to GitHub, and deploys to Firebase Hosting — all in this one command. No separate publish step is needed.

---

## Step 4 — Report

Read `jobs.json` back and print a summary table for every URL processed this run:

| Job ID | Title | Company | Match | Reason |
|--------|-------|---------|-------|--------|

If any job came back `yes` or `maybe`, suggest: "Run `/tailor-resume JOB_ID` to generate a resume and cover letter for it."

If a job's `matches_requirements` is still `pending` or `error` after Step 3, say so plainly (the local LLM was likely unreachable) and suggest re-running `python scraper.py --review-urls URL` once LM Studio is available.
