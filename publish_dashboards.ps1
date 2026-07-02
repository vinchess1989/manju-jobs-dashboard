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
git add jobs.json seen_urls.json checkpoint.json job_descriptions job_requirements.md firebase_app/index.html firebase_app/firestore.rules scraper.py tests/ jobs_history.json deleted.json publish_dashboards.ps1 next_session_prompt.md html_to_pdf.py find_matching_jobs.py make_resume.py upload_resume_links.py input.csv curated_jobs.json scrape_application.py fill_application.py fill_agent.py sync_resume_links.py .claude/commands/tailor-resume.md .claude/commands/fill-form.md
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
git add jobs.json seen_urls.json checkpoint.json firebase_app/index.html firebase_app/firestore.rules scraper.py tests/ jobs_history.json job_descriptions deleted.json job_requirements.md .gitignore
$vineethStaged = git diff --cached --name-only
if ($vineethStaged) {
    git commit -m "chore: update vineeth dashboard [all tests passing]"
    Write-Host "Committed staged changes for vineeth_jobs." -ForegroundColor Green
} else {
    Write-Host "No staged changes to commit for vineeth_jobs." -ForegroundColor Yellow
}
if ($env:GITHUB_TOKEN) {
    $vineethRemote = git remote get-url origin
    git push ($vineethRemote -replace "https://", "https://x-access-token:$($env:GITHUB_TOKEN)@")
} else {
    git push
}

Write-Host "`n=== Step 6: Deploying vineeth_jobs Firebase ===" -ForegroundColor Cyan
Set-Location "c:\Users\vinee\vineeth_jobs\firebase_app"
firebase deploy --only hosting --non-interactive

Write-Host "`n=== Step 7: Committing & Pushing Manju_jobs_private ===" -ForegroundColor Cyan
$PRIVATE = if ($env:MANJU_PRIVATE_DIR) { $env:MANJU_PRIVATE_DIR } else { "C:\Users\vinee\Manju_jobs_private" }
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

Write-Host "`n=== SUCCESS: Both dashboards are live and private repo is synced! ===" -ForegroundColor Green
