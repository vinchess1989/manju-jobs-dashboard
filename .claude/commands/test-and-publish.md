Publish this dashboard project (and any sibling dashboard project found alongside it) using the publish script. Before running, review the script to make sure it is up to date.

The script lives at `publish_dashboards.ps1` in the repo root and is machine-agnostic by design: it resolves the host project via its own location, discovers any sibling dashboard project (same signature: `scraper.py` + `firebase_app/firebase.json`) alongside it, and resolves the private companion repo the same way the tailor-resume / fill-form skills do (`$env:MANJU_PRIVATE_DIR`, else a sibling `*private*` directory, else a sibling directory containing a `Resumes\` folder). Nothing in it should ever be a machine-specific absolute path — if you find one, that's a regression to fix, not a convention to preserve.

## Step 1 — Review and update the script if needed

Read `publish_dashboards.ps1` (repo root — resolve with `$PUBLIC = (Get-Location).Path`, since Claude is always invoked from the repo root) and check that it reflects the current state of the project(s):
- The `git add` file list includes everything each scraper's `update_git()` stages, plus any new top-level scripts/dirs that should ship with a publish
- The test step uses a local venv if one exists (`.venv\Scripts\python.exe` or `venv\Scripts\python.exe`), else falls back to `python` on PATH — never a hardcoded venv path
- The Firebase deploy step targets each project's own `firebase_app/` directory and relies on that directory's own `.firebaserc` for the project id (no hardcoded `--project` flag)
- The private-repo resolution logic matches the convention above — no hardcoded fallback path

If anything is outdated, missing, or has drifted back to a hardcoded machine-specific path, edit the script to fix it before proceeding.

## Step 2 — Run the script

```powershell
.\publish_dashboards.ps1
```

Report the full output and, for each project it touched (host + any sibling found + the private repo), whether tests, git push, and Firebase deploy succeeded or failed. If a sibling project or the private repo wasn't found on this machine, that's an expected skip, not a failure — say so plainly rather than treating it as an error.
