Run the full test suite for the manju_jobs project, then publish all changes if tests pass.

## Steps

1. **Run tests** — execute the test suite:
   ```
   .\venv\Scripts\python -m pytest tests/ -v
   ```
   Report each test result. If ANY test fails, stop here and show the failures — do NOT proceed to publish.

2. **Commit and push to GitHub** — only if all tests passed:
   ```
   git add jobs.json seen_urls.json checkpoint.json dashboard.html job_descriptions job_requirements.md firebase_app/index.html scraper.py tests/
   git status --porcelain
   ```
   If there are changes, commit with a message like `"chore: update dashboard and tests [passing]"` and push.

3. **Deploy to Firebase Hosting** — from within the `firebase_app/` directory:
   ```
   cd firebase_app
   firebase deploy --only hosting --non-interactive
   ```
   If the `firebase` CLI is not found, tell the user to run it manually.

4. **Report** — summarise: how many tests passed/failed, whether git push succeeded, whether Firebase deploy succeeded or needs manual action.
