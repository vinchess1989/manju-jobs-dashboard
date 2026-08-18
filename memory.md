# Project Memory — manju_jobs

Durable, cross-session knowledge about this project that isn't already in `CLAUDE.md` (which
covers git hygiene / jobs.json-is-read-only / the merge driver — read that first). This file is
maintained by Claude Code across sessions; update it whenever something here goes stale or a new
durable fact/gotcha is discovered. It's a reference for future work, not a session changelog —
prune outdated entries rather than letting them accumulate.

## System overview

Two sibling dashboards, manju_jobs (Finnish job market, generalist roles) and vineeth_jobs
(global semiconductor/VLSI roles), sharing a lot of infrastructure. See
[vineeth_jobs/memory.md](../vineeth_jobs/memory.md) for its side. Each repo has:
- `scraper.py` — Playwright scraper + local-LLM job review, runs as a long-lived loop.
- `orchestrator.py` — thin wrapper that logs to `orchestrator.log`, launched by a Windows
  Scheduled Task (`ManjuJobsLocalLLMOrchestrator` / `VineethJobsLocalLLMOrchestrator`).
- `firebase_app/` — the live dashboard UI (`index.html`), deployed via Firebase Hosting.

## Shared local LLM (LM Studio) infrastructure

One LM Studio server at `http://127.0.0.1:1234`, shared by both scrapers **and** by OpenClaw
(`~/.openclaw`, a separate agent framework also configured to hit it via its own `openclaw.json`
`baseUrl`).

- Validated/tuned per-model settings (context length, parallel, GPU) live in
  `C:\Users\vinee\.claude\local_llm_models.json`. Always check this file, and cross-check with
  `lms ps` for what's *actually* loaded right now — LM Studio's just-in-time auto-load silently
  falls back to its own defaults (context = model's max, parallel = 4) whenever a request hits a
  model that wasn't already `lms load`-ed with the tuned flags. This mismatch was the root cause
  of repeated `ReadTimeout`/`ConnectionResetError` failures in production (2026-08-04). After
  restarting either scraper, or after any model swap, verify `lms ps` shows the tuned
  context/parallel — don't assume it does.
- Priority order for the shared server: **OpenClaw (or any external consumer) > manju_jobs >
  vineeth_jobs**, implemented via real OS-level file locks (crash-safe — a killed process
  auto-releases them, no stale-flag cleanup needed):
  - `MANJU_PRIORITY_LOCK_FILE` (`~/.claude/scraper_manju_priority.lock`) — manju_jobs claims this
    before requesting the shared pipeline lock; vineeth_jobs checks/defers to it first.
  - `PIPELINE_LOCK_FILE` (`~/.claude/scraper_pipeline.lock`) — the actual mutex around the LLM
    HTTP call.
  - `_wait_for_external_llm_idle()` polls `lms ps --json` (`status`/`queued` fields) and backs off
    while anything is generating/queued, before either scraper starts its own call. This is how
    OpenClaw gets de facto priority without any change on its side — its actual code lives in a
    content-hashed, auto-generated `dist/` bundle (npm package `openclaw`), unsafe to hand-patch,
    so the whole burden of yielding is put on our side instead.
  - Only the HTTP call itself is locked (inside `_post_llm_with_retry`), **not** the whole
    scrape+review cycle — scraping (Playwright, no LLM) runs fully unlocked so both dashboards can
    browse concurrently; only the brief LLM call is serialized.
  - `_post_llm_with_retry` also retries transient `Timeout`/`ConnectionError` (2 retries, 10s
    backoff) before giving up and marking a job `'error'` — which both scrapers' pending-job
    filters already pick up and retry on the next cycle regardless.

## GitHub Pages — load-bearing, do NOT disable

`firebase_app/index.html` does **not** read job data from Firebase — it fetches raw
`jobs.json` / `deleted.json` / `jobs_history.json` straight from **GitHub Pages**
(`https://vinchess1989.github.io/<repo>/jobs.json`), enabled on both repos (source = `main`
branch / root).

- GitHub's auto-generated "pages build and deployment" workflow re-triggers on every push (the
  scraper pushes ~every 12 min) and its `deploy` step has been consistently reporting `failure`
  with annotation `Timeout reached, aborting!` — this is the `deploy-pages` action's own
  status-confirmation polling timing out, **not** an actual publish failure: verified (2026-08-07)
  that `jobs.json`'s `Last-Modified` header tracks the latest commit within ~30s regardless. It's
  email-spam noise, not a functional problem.
- **Do not unpublish/disable Pages on either repo.** This was almost done by mistake earlier in
  the project based on an incomplete test (checking only the bare Pages root URL, which 404s
  because there's no `index.html` at repo root — the human-facing UI is served by Firebase
  Hosting instead — but Pages is still the CDN the UI's own JS depends on for its data).
- Division of labor: Firebase Hosting (`publish_dashboards.ps1`) serves the UI; GitHub Pages
  serves the raw data files that UI fetches. Both are load-bearing, for different things.

## Testing `firebase_app/index.html` locally

- A plain `file://` path does **not** work — the page references Firebase SDK scripts at
  `/__/firebase/*`, a Firebase-Hosting-only reserved path with no real file backing it. Loading
  via `file://` leaves Firebase permanently uninitialized (page hangs on "Loading jobs
  database...").
- Correct approach: `firebase serve --only hosting --port <port>` from inside `firebase_app/`
  (uses `firebase_app/firebase.json`) — this correctly emulates the `/__/firebase/*` init
  endpoint.
- The dashboard requires Google Sign-In (Firebase Auth), and auth is **per Firebase project** —
  being signed in on manju's dashboard does not carry over to vineeth's (separate project), even
  same browser profile / same Google account. Each needs its own one-time sign-in.
- There's a persistent, already-authenticated Chrome profile at
  `C:\Users\vinee\AppData\Local\Google\Chrome\Automation Profile` (CDP port 9222 when running),
  reused across several unrelated projects — not the per-project profile the `chrome-automation`
  skill would normally create. Prefer reconnecting to this one for dashboard testing over
  launching a fresh per-project profile that needs sign-in from scratch. If it's running with a
  stale/hung CDP connection, `Stop-Process -Force` the parent `chrome.exe` (matches
  `*Automation Profile*`, no `--type=` flag, has `--remote-debugging-port`) and relaunch on 9222
  with the same `--user-data-dir` — the signed-in session persists.

## Dashboard chart architecture (`firebase_app/index.html`)

- `_renderChart(canvas, data, metric, opts)` draws the trend charts (Yes&Maybe / Applied / Maybe /
  Total). `metric` selects the plotted line(s) (`LINES`) and which single field (`CHURN_KEY`) the
  Added/Deleted bars track. Added/Deleted are the net day-over-day change in `d[CHURN_KEY]`
  specifically — **not** overall dataset-wide added/deleted — so e.g. the Applied chart's bars
  reflect applied-count churn only, not every job added/removed across the whole board (fixed
  2026-08-07; previously all charts showed whole-dataset churn regardless of metric).
- Hover-popup + click-to-modal wiring is `_attachChartHover(el, metric)`, currently attached to
  `#stat-total`, `#stat-yes`, `#stat-maybe`, `#applied-counter`.
- Header stat counts (Yes/Maybe/No/Pending/Re-review/Applied/Reviewed) always show the **true
  total** across all jobs, unaffected by column filters — only the Total count itself shows the
  filtered subset as its primary number (with `(filtered from X)`). The others show the total as
  primary with a `(N filtered)` note appended only when a filter is active.
- vineeth_jobs's `firebase_app/index.html` mirrors this architecture (cross-dashboard parity per
  the root `CLAUDE.md`) but isn't byte-identical — e.g. its default/`'total'` metric chart shows
  both Total+Yes lines where manju's shows Yes only, and `filterTable()` uses index-based
  `vals[i]` column access where manju uses `.col-*` CSS classes + `data-value` attributes. Check
  the actual code before assuming symmetry between the two.

## CDP Chrome connection flakiness (recurring — first seen 2026-08-15, confirmed again same day)

During unattended `/fill-form auto` cycles, `playwright.chromium.connect_over_cdp("http://127.0.0.1:9222")`
repeatedly hangs for the full timeout (180s for the actual API handshake, despite the raw TCP port and
`GET /json/version` HTTP endpoint both responding fine) or connects then gets refused/closed moments later
(`ECONNREFUSED` / "Connection closed while reading from the driver") — with no code change, same relaunch
sequence each time. **Confirmed recurring across two separate cycles the same day**, including immediately
after a full `taskkill`+relaunch with the port freshly verified open — so "just restart Chrome" is not a
reliable fix, only sometimes helps. Pattern observed: the very first `connect_over_cdp` call after a fresh
launch has better (not perfect) odds of succeeding; a second script run moments later against the same
still-running browser frequently fails even though nothing else changed. `Test-NetConnection`/TCP-level
checks and `/json/version` are **not sufficient** to confirm CDP is actually usable — only a real
`connect_over_cdp` call (with a short wrapper timeout; the library's own default is very long) proves it, and
even that can succeed once and fail the very next attempt seconds later. `Stop-Process -Force`/`taskkill /F`
often report success while a `chrome.exe` PID lingers — normal Chrome multi-process behavior (renderer/GPU/
utility processes all show as `chrome.exe`), not evidence of a stuck relaunch; process **count** (10-30+) is
not a useful signal by itself.

Root cause still not identified. Not yet tried: `launch_persistent_context` instead of `connect_over_cdp`
(avoids the separate CDP handshake entirely); checking Windows Defender/firewall for per-connection
inspection latency on repeated localhost socket opens; whether an idle keep-alive ping between script
invocations prevents the browser from letting the DevTools connection go stale. Worth investigating properly
in a future session if it keeps costing cycles — for now, treat it like the documented locked-PC case: after
one or two restart+retry attempts, stop and skip the cycle cleanly rather than burning many minutes on
repeated reconnects. Don't set `auto_fill_attempted_at` on whatever candidate was being attempted so it
retries next hour instead of getting stuck or silently half-filled.

## `scrape_application.py` cannot handle LinkedIn without credentials — and crashes ungracefully in `--non-interactive`

Discovered 2026-08-18 running `/fill-form auto` against jobs Manju had clicked Apply on in
`review.html`. `scrape_application.py --job-url <linkedin.com/...> --non-interactive` detects
`platform: linkedin`, then tries its own first-time-setup credential prompt (`input()` for email/
password to save into `PRIVATE\.env`) — it does **not** reuse the CDP browser's already-logged-in
LinkedIn session (the Automation Profile). In `--non-interactive` mode there's nobody to answer the
prompt, so it crashes with an unhandled `EOFError` at `ensure_credentials()` instead of writing a
`login_wall: true` questions.json like every other unsupported-ATS case does. No `PRIVATE\.env`
currently has LinkedIn credentials set, so **every LinkedIn job is currently a hard block** in
auto-mode, not just a soft "ambiguous ATS" case — WebFetch on `www.linkedin.com` job URLs also
reliably returns a generic logged-out search-results shell (no job content, no apply button) rather
than the real listing, so there's currently no way (WebFetch or the automation script) to resolve a
LinkedIn application's actual form/questions without a human doing it by hand in the browser. `fi.
linkedin.com` URLs are the one exception — WebFetch renders those fine (real job content, correct
open/closed status) even logged out; only `www.`/country-subdomain LinkedIn URLs hit the wall.
If LinkedIn volume ever justifies fixing this: either add LinkedIn credentials to `PRIVATE\.env` (a
real risk — LinkedIn is known to flag/lock automated-login accounts) or teach `scrape_application.py`
to catch `EOFError` in `--non-interactive` and fall back to `login_wall: true` like it should.

## `job_status_store.py set` does a full-document read-modify-write — races with review.html and can silently revert Manju's clicks

Discovered 2026-08-18, second `/fill-form auto` cycle same day. `set_job_field()` calls
`get_job_status()` (full GET of the whole `shared_state/job_status` doc), mutates one field in
memory, then `patch_job_status()` (full PATCH overwrite of the whole doc back). `review.html`, by
contrast, writes via the Firestore JS SDK's `update()` with individual `FieldPath`s — a real partial
update. If a `review.html` write (e.g. `applyWeakMatch`'s atomic `matches_requirements` + `user_review:
'done'` + `priority_fill_form_at` update, or `toggleActionItemDone`'s `create_login` branch) lands in
the window between this script's GET and PATCH, the script's stale full-doc snapshot silently
clobbers it on write — no error, no conflict, the field just reverts.

Caught in the act: a job had `matches_requirements: yes` (reason "Promoted from weak match via
review dashboard" — `applyWeakMatch`'s literal fallback string) and a same-day `priority_fill_form_at`
timestamp, but `user_review` read back as unset instead of `'done'` — the only two code paths that set
`priority_fill_form_at` are `applyWeakMatch` (which sets `user_review: 'done'` in the *same* atomic
call) and the `create_login` action-item "Done" checkbox (which requires an existing `action_item`,
and this job had none). The only coherent explanation is a genuine `applyWeakMatch` click whose
`user_review` write got raced away by a concurrent `job_status_store.py set` — almost certainly this
skill's own high-frequency calls during a `/fill-form auto` cycle (dozens of sequential `set` calls in
a short window while Manju may have had `review.html` open at the same time).

**Practical fallout:** don't trust `user_review == 'done'` in isolation as "no Apply click happened" —
cross-check `matches_requirements`, `user_reason` (the `applyWeakMatch` fallback string is a strong
tell), and `priority_fill_form_at` together before concluding a "yes" match wasn't an explicit pick.
When in doubt, the safer read is that a `matches_requirements: yes` + that reason string *is* an
explicit Apply click, full stop — same as [[respect weak-match Apply clicks]] already establishes for
jobs where `user_review` **is** intact.

**Real fix, not yet done:** switch `set_job_field`/`patch_job_status` to a targeted Firestore REST PATCH
with an `updateMask` query param scoped to the single field being written, instead of GET-modify-PATCH
of the entire document — that closes the race entirely instead of just working around it. Until that
lands, minimize back-to-back `job_status_store.py set` calls in any one script run (batch reads, but
each write still reopens the race window) and treat this as a live risk any time review.html might be
in concurrent use.

## Open/unresolved

- `jobs_history.json.corrupt-20260813_150257`: partially investigated (2026-08-14). The file
  itself isn't present in a fresh clone/this machine — it's a local, untracked artifact on
  whichever machine wrote it (not committed, not gitignored, just never `git add`ed), so it can
  only be inspected from that machine directly. What *is* confirmed: the live `jobs_history.json`
  in the repo is currently healthy (valid JSON, 2092 entries) and its timeline is continuous
  across that window — a manual jobs.json-merge-driver rebase conflict in this same file was
  resolved by hand around 2026-08-13 14:42 (two divergent snapshot entries unioned back in,
  chronological order preserved), and the scraper's own entries resume cleanly right after that
  (14:42:25 → next entries start 2026-08-14 08:07, matching a ~17.5h scraper outage window that
  night, not a data problem). Best guess: the `.corrupt-*` file is the scraper's own self-healing
  logic backing up a copy it couldn't parse *at that specific moment* (mid-rebase, when the file
  briefly had `<<<<<<<`/`=======`/`>>>>>>>` conflict markers in it) before either retrying or
  regenerating — i.e. a symptom of the conflict, already resolved, not a separate ongoing issue.
  Not fully confirmed since the actual `.corrupt-*` file content hasn't been read.

---
Last updated: 2026-08-18
