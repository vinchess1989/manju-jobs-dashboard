Draft (never send) a job-application email for one or more jobs that apply via email — tailored resume and cover letter attached — and leave it in Manju's own Gmail Drafts folder (`munchnambiar@gmail.com`) for her to review and send herself. Composed and attached via browser automation (same CDP/Chrome pattern as `fill-form`), verified afterward via the connected `claude.ai Gmail` MCP connector.

The arguments are: **$ARGUMENTS**

Parse `$ARGUMENTS` as space-separated tokens:
- Any token matching `^[0-9a-fA-F]{8}$` (case-insensitive) is a `JOB_ID`.
- The token `redo` (case-insensitive) sets `$Redo = $true` — re-draft even if a draft already exists for a job (a fresh draft is created; the old one is left alone in Gmail, not deleted).

**If no `JOB_ID` token is given** → run Step -1 (auto-discovery) to build the job list, then Steps 0–5 for each. **If one or more `JOB_ID`s are given** → run Steps 0–5 directly for each, skipping Step -1.

Examples:
- `/email-apply` — find every job with a pending `email_application` action item and no existing draft, and draft all of them
- `/email-apply abc12345` — draft one specific job
- `/email-apply abc12345 def67890` — draft two jobs
- `/email-apply abc12345 redo` — re-draft even though a draft already exists for this job

---

## Why this exists

`find-apply-link` and `fill-form` already detect jobs whose only application path is an email address (`RESULT_TYPE: email` / `apply_email` in Firestore) and log an `email_application` action item — but until now that just told Manju "go write this email yourself." This skill does the mechanical part (correct recipient, tailored PDFs attached, professional copy in the right language) and stops at a Gmail **draft**, exactly the same trust boundary `fill-form` uses for web forms ("never click submit" → here, "never click send").

---

## Constants (resolved at runtime — device-agnostic)

**`PUBLIC`** — repo root. `$PUBLIC = (Get-Location).Path`

**`PRIVATE`** — the private companion repo. Resolve in this order and stop at the first hit:
1. The environment variable `MANJU_PRIVATE_DIR` if set.
2. A sibling of PUBLIC whose name contains "private" (case-insensitive).
3. A sibling of PUBLIC that contains a `Resumes\` subfolder.
4. If still not found — stop and ask the user to set `MANJU_PRIVATE_DIR`, then re-run.

**`JOBS_JSON`** = `PUBLIC\jobs.json` — read-only lookup only.

**`SENDER_CONTACT`** — read once from `PRIVATE\Resumes\Master\master_data.json`'s `resume.contact`: `address`, `phone`, `email` (must be `munchnambiar@gmail.com` — see the safety check below), `linkedin_url`.

**`AUTOMATION_PROFILE`** = `$env:LOCALAPPDATA\Google\Chrome\Manju Automation Profile` — same dedicated, already-logged-in-as-Manju Chrome profile `fill-form.md` uses. **Do not use the old shared `Automation Profile` directory (no "Manju" prefix)** — that one's Chrome Sync account is Vineeth's, not Manju's.

**Gmail account safety check (do this once per session, before drafting anything):** confirm the connected `claude.ai Gmail` MCP connector really is Manju's own mailbox — e.g. `mcp__claude_ai_Gmail__search_threads` with `query: "in:sent"`, `pageSize: 1`, and check the returned message's `sender` is `munchnambiar@gmail.com`. If it resolves to any other address, **stop immediately and tell the user** — do not draft anything, and do not launch the browser automation either (it uses the same account by construction, but this MCP check is the cheap tripwire that catches a swapped connector before any browser work starts). (Confirmed `munchnambiar@gmail.com` / "Manju Krishna Haridas" on 2026-09-09; re-verify if this ever looks different, since MCP connector auth can be swapped by the user at any time.)

---

## Step -1 — Auto-discovery (only when no `JOB_ID` given)

List every job with a pending, undrafted email application:

```powershell
python -c "
import job_status_store as jss, json
data = jss.get_job_status()
out = []
for url, entry in data.items():
    ai = entry.get('action_item') or {}
    if ai.get('type') != 'email_application' or ai.get('status') != 'pending':
        continue
    if (entry.get('email_draft') or {}).get('status') == 'created':
        continue
    if entry.get('applied') == 'yes':
        continue
    out.append(url)
print(json.dumps(out))
"
```

Read `JOBS_JSON`, map each returned URL to its job `id` (skip URLs no longer present — the job may have been deleted/expired since the action item was logged, note this in the final report). The resulting `id` list becomes the `JOB_ID`s Steps 0–5 run for.

If the list is empty, print `No pending, undrafted email applications found.` and stop.

---

## Step 0 — Resolve the job

Read `JOBS_JSON`, find the entry with `id == JOB_ID`. If not found, print an error and skip to the next `JOB_ID`.

Record `JOB_TITLE`, `COMPANY`, `JOB_URL`, `JOB_LOCATION` (`location` field), `SOURCE` (`source` field, if present).

---

## Step 1 — Idempotency check

```powershell
python job_status_store.py get --url "JOB_URL" --field email_draft
```

If it returns a value with `status == "created"` and `$Redo` is not set, print `JOB_ID already has a draft (Gmail draft id: <draft_id>) — pass 'redo' to create another.` and skip to the next `JOB_ID`.

---

## Step 2 — Ensure a Claude-tailored resume and cover letter exist

Same check as `fill-form` Step 1: confirm `PRIVATE\Resumes\JOB_ID\JOB_ID_data.json` exists, matching resume/cover-letter PDFs exist alongside it, and `data.json`'s `tailor_model` contains `"claude"` (case-insensitive).

- **All true** → use as-is.
- **Anything false or missing** → run the **tailor-resume** skill technique (`.claude/commands/tailor-resume.md`, i.e. `/tailor-resume JOB_ID`), then re-check.

```powershell
$resumePdf = Get-ChildItem "PRIVATE\Resumes\JOB_ID\*_resume.pdf"        | Select-Object -First 1 -ExpandProperty FullName
$coverPdf  = Get-ChildItem "PRIVATE\Resumes\JOB_ID\*_cover_letter.pdf"  | Select-Object -First 1 -ExpandProperty FullName
```
Abort this job (skip to the next `JOB_ID`) if either is still missing after tailoring.

Read `PRIVATE\Resumes\JOB_ID\JOB_ID_data.json` for `EMAIL_LANG`: if the top-level `resume.labels` key is present, the posting was Finnish (per `tailor-resume`'s own convention) → `EMAIL_LANG = "fi"`; otherwise `EMAIL_LANG = "en"`.

---

## Step 3 — Resolve the recipient email address

Priority order, stopping at the first hit:

1. Firestore cache: `python job_status_store.py get --url "JOB_URL" --field apply_email`. If present (not `NONE`), use it.
2. Otherwise, apply the **find-apply-link** skill technique (`.claude/commands/find-apply-link.md`) using `JOB_URL` as `BASE_URL` and `JOB_ID` as `JOB_ID`. It self-persists `apply_email`/`apply_url` to Firestore.
   - `RESULT_TYPE: email` → use `RESULT`.
   - `RESULT_TYPE: form` → **this job has an actual application form, not an email-only path.** Print `JOB_ID resolves to a web form (APPLY_URL) — use /fill-form instead, not /email-apply.` and skip to the next `JOB_ID`.
   - `RESULT_TYPE: not_found` → print a warning and skip to the next `JOB_ID`.

Sanitize `TO_EMAIL`: strip a leading `mailto:`, strip any `?subject=...`/query-string suffix, trim whitespace. Validate it looks like a plain address (`local@domain`) — if it doesn't, skip this job and report the raw value for manual handling rather than guessing.

**Safety check:** if `TO_EMAIL` equals `munchnambiar@gmail.com` (Manju's own address) or is empty, something upstream resolved wrong — skip this job and report it rather than drafting a self-addressed or blank-recipient email.

---

## Step 4 — Compose and create the Gmail draft

**Why browser automation, not the Gmail MCP's `create_draft` attachments:** that tool takes attachment bytes as inline base64 in the request. Tried directly (2026-09-09) — reading a resume PDF's base64 (a few hundred KB of file → 300k+ base64 characters) back through the Read tool costs on the order of **3 tokens per base64 character** (measured directly: a 70,364-character cover-letter base64 blob cost 67,022 tokens for just the first third of it), so a real tailored resume would cost roughly a million tokens to move through context and back out as one tool-call argument — with no guarantee a single response can even emit an argument that large without silent truncation, which would mean a corrupted PDF sitting in a real, undetectable draft. Not worth the risk. Playwright's `set_input_files()` instead points the browser at the local file path directly — zero bytes ever pass through the model's context.

**Subject** (in `EMAIL_LANG`):
- `en`: `Application for JOB_TITLE – Manju Krishna Haridas`
- `fi`: `Hakemus: JOB_TITLE – Manju Krishna Haridas`

**Body** — a short, professional cover email (this is *not* the cover letter, which is already attached as a PDF — keep this to 3–4 short paragraphs, plain text):

`en` template:
```
Dear Hiring Manager,

I am writing to apply for the JOB_TITLE position at COMPANY[, JOB_LOCATION if set]. Please find my resume and cover letter attached, which outline my background in [1 short phrase tailored from resume.profile in JOB_ID_data.json] and how it aligns with this role.

I would welcome the opportunity to discuss my application further. Please don't hesitate to contact me if you need any additional information.

Best regards,
Manju Krishna Haridas
SENDER_CONTACT.phone
SENDER_CONTACT.email
SENDER_CONTACT.linkedin_url
```

`fi` template:
```
Hyvä vastaanottaja,

Haen täten JOB_TITLE-tehtävää yrityksessä COMPANY[, JOB_LOCATION jos asetettu]. Liitteenä ansioluetteloni ja hakemuskirjeeni, joissa kerron tarkemmin osaamisestani ja kiinnostuksestani tähän tehtävään.

Kerron mielelläni lisää hakemuksestani. Otattehan yhteyttä, mikäli tarvitsette lisätietoja.

Ystävällisin terveisin,
Manju Krishna Haridas
SENDER_CONTACT.phone
SENDER_CONTACT.email
SENDER_CONTACT.linkedin_url
```

Write both `[...]` placeholders in naturally, don't leave brackets in the actual email.

**Launch/confirm CDP Chrome** — identical to `fill-form.md` Step 4, but against `AUTOMATION_PROFILE` (the Manju-specific profile defined above):
```powershell
$port_open = Test-NetConnection -ComputerName 127.0.0.1 -Port 9222 -WarningAction SilentlyContinue
if (-not $port_open.TcpTestSucceeded) {
    Stop-Process -Name chrome -Force -ErrorAction SilentlyContinue
    taskkill /F /IM chrome.exe /T
    $batPath = "PUBLIC\scratch\launch_cdp_chrome.bat"
    Set-Content -Path $batPath -Value "@echo off`n`"C:\Program Files\Google\Chrome\Application\chrome.exe`" --remote-debugging-port=9222 --user-data-dir=`"$env:LOCALAPPDATA\Google\Chrome\Manju Automation Profile`""
    cmd /c "schtasks /delete /tn `"AntigravityVisibleBrowser`" /f & schtasks /create /tn `"AntigravityVisibleBrowser`" /tr `"\`"$batPath\`"`" /sc once /st 00:00 /ru vinee /it /f & schtasks /run /tn `"AntigravityVisibleBrowser`""
    Start-Sleep -Seconds 4
}
```
(`connect_over_cdp` is known to be flaky on the very first call after a fresh launch — see `memory.md`'s CDP flakiness section. Retry once if it hangs the full timeout before treating it as a real failure.)

**Write `PUBLIC\scratch\email_apply_JOB_ID.py`** — validated selectors (confirmed live 2026-09-09; Gmail's DOM can drift, re-diagnose with `page.eval_on_selector_all` over `input, textarea, div[contenteditable='true'], div[role='textbox']` if any of these stop matching):
```python
from playwright.sync_api import sync_playwright

TO = "TO_EMAIL"
SUBJECT = "SUBJECT"
BODY = "BODY"   # exact multi-line string composed above — pass as a real Python string, not shell-escaped
RESUME = r"RESUME_PDF_PATH"
COVER = r"COVER_PDF_PATH"

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    context = browser.contexts[0]
    page = context.new_page()
    page.set_default_timeout(15000)

    page.goto("https://mail.google.com/mail/u/0/?view=cm&fs=1", timeout=30000)
    page.wait_for_timeout(2500)

    to_field = page.locator('input[aria-label="To recipients"]')
    to_field.click()
    to_field.fill(TO)
    page.keyboard.press("Tab")

    subj_field = page.locator("input[name='subjectbox']")
    subj_field.click()
    subj_field.fill(SUBJECT)

    body_field = page.locator('div[aria-label="Message Body"][role="textbox"]')
    body_field.click()
    body_field.fill(BODY)

    # Direct file input — no dialog, no click-and-catch-filechooser needed,
    # and nowhere near the Send button (which sits right next to the paperclip icon).
    file_input = page.locator('input[name="Filedata"]')
    file_input.set_input_files([RESUME, COVER])

    page.wait_for_timeout(6000)
    for name in (RESUME.split("\\")[-1], COVER.split("\\")[-1]):
        page.get_by_text(name, exact=False).first.wait_for(timeout=20000)
        print(f"attached: {name}")

    # Gmail's ?view=cm&fs=1 opens FULL-SCREEN compose, not a popup dialog — there is
    # no "Save & close" button to click. It autosaves continuously; just wait for the
    # autosave to catch up, then close the tab. Never click Send or the trash icon.
    page.wait_for_timeout(3000)
    page.close()
    browser.close()
    print("Draft saved. Never clicked Send.")
```
Run it: `python -u PUBLIC\scratch\email_apply_JOB_ID.py`

**Never click, locate-and-click, or otherwise target the Send button (`role=button`, text "Send") or the discard/trash icon anywhere in this script.**

---

## Step 5 — Verify, persist, and hand off

**Verify the draft actually landed** (the browser script has no direct feedback beyond the attachment-chip check) — use the Gmail MCP, which is cheap here since we're only asking for small metadata, not attachment bytes:
```
mcp__claude_ai_Gmail__list_drafts, query: "to:TO_EMAIL", view: DRAFT_VIEW_FULL, pageSize: 5
```
Match the entry whose `subject` equals `SUBJECT` (composed in Step 4) — take its `id` as `DRAFT_ID` and `threadId` as `THREAD_ID`. If no match is found, something went wrong (autosave didn't catch up, or a selector silently matched nothing) — do not guess; report the failure for this job and skip to the next rather than writing a fabricated `email_draft` record.

Optionally sanity-check attachments actually made it in via `mcp__claude_ai_Gmail__get_draft` with `messageFormat: RAW` on `DRAFT_ID` — **don't read its content**, just note the reported character count in the tool's own size-limit response; a MIME size in the hundreds of KB (roughly matching the two PDFs' combined size, base64-inflated) confirms real attachments, a MIME size of a few KB means they didn't attach and this job needs to be retried from Step 4.

Record the draft so re-runs don't duplicate it, and surface it on the dashboard:

```powershell
$emailDraft = [ordered]@{
    status     = "created"
    draft_id   = "DRAFT_ID"
    thread_id  = "THREAD_ID"
    to         = "TO_EMAIL"
    created_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
} | ConvertTo-Json -Compress
$tmpFile = "PUBLIC\scratch\email_draft_JOB_ID.json"
Set-Content -Path $tmpFile -Value $emailDraft -Encoding utf8 -NoNewline
python job_status_store.py set --url "JOB_URL" --field email_draft --json --value-file $tmpFile
Remove-Item $tmpFile -ErrorAction SilentlyContinue
```
(JSON must go through `--value-file`, never an inline `--value` — PowerShell 5.1 silently strips embedded double-quote characters from native-command arguments; see `job_status_store.py`'s own docstring.)

**Do not** touch `action_item.status` or `applied` here — those stay exactly as `fill-form`/`find-apply-link` leave them. Manju checking "Done" on the `email_application` action item in `firebase_app/review.html` (which sets `applied = yes`) remains the one and only signal that she actually reviewed and sent the email — this skill only stages the draft, never marks anything as sent.

Print, per job:
```
JOB_ID (JOB_TITLE @ COMPANY) — draft created in Gmail.
To           : TO_EMAIL
Resume       : $resumePdf
Cover letter : $coverPdf
Gmail draft id: DRAFT_ID
Review it in Gmail Drafts, then send it yourself — this skill never sends automatically. Checking "Done" on this job's Email Application action item in review.html marks it applied once you've actually sent it.
```

At the end of a multi-job run, print a summary table (Job ID | Title | Company | Recipient | Draft status).
