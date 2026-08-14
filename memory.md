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

## Open/unresolved

- `jobs_history.json.corrupt-20260813_150257` exists in the repo root as of 2026-08-14 — some
  past corruption event left a backup copy under this name. Not yet investigated; worth checking
  whether `jobs_history.json` itself is currently healthy.

---
Last updated: 2026-08-14
