Run the full test suite for both manju_jobs and vineeth_jobs, then publish all changes if tests pass.

## Steps

### 1. Run manju_jobs tests
```powershell
cd c:\Users\vinee\manju_jobs
.\venv\Scripts\python -m pytest tests/ -v
```
Report each test result. If ANY test fails, stop here — do NOT proceed to publish.

### 2. Run vineeth_jobs tests
```powershell
cd c:\Users\vinee\vineeth_jobs
.\venv\Scripts\python -m pytest tests/ -v
```
Report each test result. If ANY test fails, stop here — do NOT proceed to publish.

### 3. Commit and push manju_jobs — only if all tests passed
```powershell
cd c:\Users\vinee\manju_jobs
git add jobs.json seen_urls.json checkpoint.json dashboard.html job_descriptions job_requirements.md firebase_app/index.html scraper.py tests/ jobs_history.json
git status --porcelain
git commit -m "chore: update manju dashboard [all tests passing]"
git push
```

### 4. Deploy manju Firebase Hosting
```powershell
cd c:\Users\vinee\manju_jobs\firebase_app
firebase deploy --only hosting --non-interactive
```

### 5. Commit and push vineeth_jobs — only if all tests passed
```powershell
cd c:\Users\vinee\vineeth_jobs
git add jobs.json seen_urls.json checkpoint.json firebase_app/index.html scraper.py tests/ jobs_history.json job_descriptions
git status --porcelain
git commit -m "chore: update vineeth dashboard [all tests passing]"
git push
```

### 6. Deploy vineeth Firebase Hosting
```powershell
cd c:\Users\vinee\vineeth_jobs\firebase_app
firebase deploy --only hosting --non-interactive
```

### 7. Report
Summarise: manju tests (passed/failed), vineeth tests (passed/failed), whether each git push succeeded, whether each Firebase deploy succeeded or needs manual action.
