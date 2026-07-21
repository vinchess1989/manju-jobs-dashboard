Publish both dashboards using the publish script. Before running, review the script to make sure it is up to date.

## Step 1 — Review and update the script if needed

Read `c:\Users\vinee\manju_jobs\publish_dashboards.ps1` and check that it reflects the current state of both projects:
- The `git add` lines for manju_jobs and vineeth_jobs include all tracked files (compare against what each scraper's `update_git()` stages)
- Both test steps point to the correct venv paths
- Both Firebase deploy steps target the correct `firebase_app/` directories
- Step 7 (Manju_jobs_private) path resolves correctly — either via `MANJU_PRIVATE_DIR` env var or the hardcoded fallback

If anything is outdated or missing, edit the script to fix it before proceeding.

## Step 2 — Run the script

```powershell
cd c:\Users\vinee\manju_jobs
.\publish_dashboards.ps1
```

Report the full output and whether each step (tests, git push, Firebase deploy) succeeded or failed.
