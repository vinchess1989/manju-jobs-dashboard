# CLAUDE.md

Instructions for any Claude Code session (interactive or via a skill/slash-command) working in this repo.

## Two machines, one `jobs.json` — read this before touching it

The scraper (`scraper.py`) runs autonomously on one PC, committing and pushing to `origin/main` roughly every **12 minutes**, rewriting `jobs.json` wholesale each time (it's the full scraped job list, ~9,500 entries). Tailoring/apply-link work (`/tailor-resume`, `/tailor-resume-n-fill-form`, `/find-apply-link`, this session) often happens on a **different PC**, hours or days apart from when it last synced.

**`jobs.json` is scraper-owned. Treat it as read-only from every other skill/script.** Never add, edit, or patch a field into it directly (`apply_url`, `apply_email`, `tailor_model`, `needs_re_review`, anything) — even via a "small inline Python snippet." Two independent processes writing the same file is what causes merge conflicts; a skill that never writes to it can't conflict on it, no matter how stale the local clone is.

**Where tailoring metadata actually goes:** Firestore, `shared_state/job_status`, keyed by job URL — via `job_status_store.py`:
```powershell
python job_status_store.py get --url "<job_url>" --field apply_url   # NONE if unset
python job_status_store.py set --url "<job_url>" --field apply_url --value "<result>"
```
This is the same document `upload_resume_links.py` already writes `tailor_model`/`resume_url`/`cover_letter_url` to, and the same one the live dashboard (`firebase_app/index.html`) reads as an override layer on top of `jobs.json`. It's open read/update (`firebase_app/firestore.rules`), no auth needed.

## Git hygiene — do this in every skill that touches the PUBLIC repo

1. **Pull first, always:** `git pull --rebase` before starting any work that reads `jobs.json` for a decision (e.g. `matches_requirements`) — a stale local clone silently gives wrong answers, not just merge trouble. `jobs.json` moves roughly every 12 minutes.
2. **Don't let commits sit unpushed.** Check `git rev-list --count origin/main..HEAD` at the start of a session; if non-zero, a prior session left work stranded — push it (with the retry below) before starting anything new. Local-only commits accumulate silently and turn into avoidable rebase conflicts the longer they sit.
3. **Push with retry, not push-and-hope:** the scraper may push again in the seconds/minutes your session was running. A rejected push is routine, not a failure:
   ```powershell
   git push origin main
   # if rejected:
   git pull --rebase origin main   # resolve any conflict per the rule below
   git push origin main            # retry, up to ~3 times total
   ```

Since jobs.json writes are now Firestore-only (see above), a `git pull --rebase` on `PUBLIC` should almost always be a clean fast-forward. If it still conflicts (legacy edits, a manual jobs.json patch that shouldn't have happened), resolve **per job entry, union the fields from both sides** — never just pick one side and discard the other's field. This is also exactly what `git_jobs_merge_driver.py` automates (see below) — if it's registered, you likely won't see a manual conflict at all.

## The jobs.json merge driver (automatic conflict resolution)

`git_jobs_merge_driver.py` resolves `jobs.json` conflicts **per job `id`** instead of per-line: a job entry that only one side touched is taken as-is; a job entry both sides touched gets its fields unioned; a job entry where both sides set the *same* field to *different* values is a genuine conflict and is left for manual resolution (the driver prints exactly which job id / field / two values collided to stderr — read that instead of hunting for `<<<<<<<` markers, since a driver-declined conflict leaves the file as "ours," not marked up).

It's wired up via `.gitattributes` (`jobs.json merge=jobsjson`, committed, shared) + local git config (**not** shareable via the repo — arbitrary-command config is deliberately local-only). **Run once per machine:**
```powershell
powershell -File setup_merge_driver.ps1
```
Verify: `git config --get merge.jobsjson.driver` should print `python git_jobs_merge_driver.py %O %A %B`.

This is a safety net, not the primary fix — the primary fix is the read-only rule above. The driver should rarely even see a real two-sided conflict once no skill writes to `jobs.json` anymore.

**Gotcha if you ever re-register this by hand instead of via the script:** Windows PowerShell 5.1 mis-splits a git-config value that contains embedded `"..."` quotes when passed as a native-command argument (a stray `"` inside the value prematurely closes/reopens argv parsing, so `git config key value` silently receives extra positional args and fails with `error: no action specified`, without actually setting the key). The fix used here is a **relative** path (`git_jobs_merge_driver.py`, not the absolute path with spaces) — git always invokes merge drivers with cwd = repo root, so no quoting is needed at all. Don't "fix" this back to an absolute path.

**When writing anything that writes `jobs.json`** (the merge driver, or any future script): match the scraper's exact serialization or every write reformats the entire ~9,500-job file and turns a 1-field change into a 135,000-line diff. That's `json.dump(data, f, indent=2)` — **no** `ensure_ascii=False` (the scraper uses the `ensure_ascii=True` default) — and `open(path, "w", encoding="utf-8", newline="\n")` (explicit `newline="\n"`, since Windows Python's default text-mode write silently converts `\n` → `\r\n`, and the scraper's own output is LF-only).

## Writing a new skill that touches this repo

If you're adding or editing a `.claude/commands/*.md` skill that reads or writes job data, follow the two rules above: read `jobs.json` freely, never write to it, put any per-job metadata in Firestore via `job_status_store.py`, and pull-rebase at the start / push-with-retry at the end if the skill commits to `PUBLIC`. `find-apply-link.md` and `tailor-resume-n-fill-form.md` are the reference implementations.
