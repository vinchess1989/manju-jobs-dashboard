$ErrorActionPreference = "Continue"

Write-Host "=== Step 1: Testing manju_jobs ===" -ForegroundColor Cyan
Set-Location "c:\Users\vinee\manju_jobs"
.\venv\Scripts\python -m pytest tests/ -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: manju_jobs tests failed! Aborting publish." -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Step 2: Testing vineeth_jobs ===" -ForegroundColor Cyan
Set-Location "c:\Users\vinee\vineeth_jobs"
.\venv\Scripts\python -m pytest tests/ -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: vineeth_jobs tests failed! Aborting publish." -ForegroundColor Red
    exit 1
}

Write-Host "`n=== All tests passed! Proceeding to publish. ===" -ForegroundColor Green

Write-Host "`n=== Step 3: Committing & Pushing manju_jobs ===" -ForegroundColor Cyan
Set-Location "c:\Users\vinee\manju_jobs"
git add jobs.json seen_urls.json checkpoint.json dashboard.html job_descriptions job_requirements.md firebase_app/index.html firebase_app/firestore.rules scraper.py tests/ jobs_history.json deleted.json publish_dashboards.ps1
$manjuStaged = git diff --cached --name-only
if ($manjuStaged) {
    git commit -m "chore: update manju dashboard [all tests passing]"
    Write-Host "Committed staged changes for manju_jobs." -ForegroundColor Green
} else {
    Write-Host "No staged changes to commit for manju_jobs." -ForegroundColor Yellow
}
git push

Write-Host "`n=== Step 4: Deploying manju_jobs Firebase ===" -ForegroundColor Cyan
Set-Location "c:\Users\vinee\manju_jobs\firebase_app"
firebase deploy --only hosting --non-interactive

Write-Host "`n=== Step 5: Committing & Pushing vineeth_jobs ===" -ForegroundColor Cyan
Set-Location "c:\Users\vinee\vineeth_jobs"
git add jobs.json seen_urls.json checkpoint.json firebase_app/index.html firebase_app/firestore.rules scraper.py tests/ jobs_history.json job_descriptions deleted.json job_requirements.md
$vineethStaged = git diff --cached --name-only
if ($vineethStaged) {
    git commit -m "chore: update vineeth dashboard [all tests passing]"
    Write-Host "Committed staged changes for vineeth_jobs." -ForegroundColor Green
} else {
    Write-Host "No staged changes to commit for vineeth_jobs." -ForegroundColor Yellow
}
git push

Write-Host "`n=== Step 6: Deploying vineeth_jobs Firebase ===" -ForegroundColor Cyan
Set-Location "c:\Users\vinee\vineeth_jobs\firebase_app"
firebase deploy --only hosting --non-interactive

Write-Host "`n=== SUCCESS: Both dashboards are live! ===" -ForegroundColor Green
