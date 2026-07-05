$ErrorActionPreference = "Continue"

$MANJU_PUBLIC  = "C:\Users\vinee\Documents\manju jobs dashboard\manju-jobs-dashboard"
$MANJU_FIREBASE = "$MANJU_PUBLIC\firebase_app"
$PYTHON = "C:\Users\vinee\AppData\Local\Python\bin\python.exe"
$PRIVATE = if ($env:MANJU_PRIVATE_DIR) { $env:MANJU_PRIVATE_DIR } else { "C:\Users\vinee\Documents\manju jobs dashboard\Manju-jobs" }

Write-Host "=== Step 1: Testing manju_jobs ===" -ForegroundColor Cyan
Set-Location $MANJU_PUBLIC
& $PYTHON -m pytest tests/ -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: manju_jobs tests failed! Aborting publish." -ForegroundColor Red
    exit 1
}

Write-Host "`n=== All tests passed! Proceeding to publish. ===" -ForegroundColor Green

Write-Host "`n=== Step 2: Committing & Pushing manju_jobs ===" -ForegroundColor Cyan
Set-Location $MANJU_PUBLIC
git add jobs.json seen_urls.json checkpoint.json job_descriptions job_requirements.md firebase_app/index.html firebase_app/firestore.rules scraper.py tests/ jobs_history.json deleted.json publish_dashboards.ps1 html_to_pdf.py make_resume.py upload_resume_links.py input.csv sync_resume_links.py add_job.py scrape_application.py fill_agent.py .claude/commands/
$manjuStaged = git diff --cached --name-only
if ($manjuStaged) {
    git commit -m "chore: update manju dashboard [all tests passing]"
    Write-Host "Committed staged changes for manju_jobs." -ForegroundColor Green
} else {
    Write-Host "No staged changes to commit for manju_jobs." -ForegroundColor Yellow
}
git push

Write-Host "`n=== Step 3: Deploying manju_jobs Firebase ===" -ForegroundColor Cyan
Set-Location $MANJU_FIREBASE
firebase deploy --only hosting --non-interactive --project manju-jobs-dashboard

Write-Host "`n=== Step 4: Committing & Pushing Manju_jobs_private ===" -ForegroundColor Cyan
if (Test-Path $PRIVATE) {
    Set-Location $PRIVATE
    git add Resumes\
    $privateStaged = git diff --cached --name-only
    if ($privateStaged) {
        git commit -m "chore: update private resumes [auto-publish]"
        Write-Host "Committed staged changes for Manju_jobs_private." -ForegroundColor Green
    } else {
        Write-Host "No staged changes to commit for Manju_jobs_private." -ForegroundColor Yellow
    }
    git push
} else {
    Write-Host "WARNING: Private repo not found at $PRIVATE - set MANJU_PRIVATE_DIR env var to fix." -ForegroundColor Yellow
}

Write-Host "`n=== SUCCESS: Dashboard is live and private repo is synced! ===" -ForegroundColor Green
