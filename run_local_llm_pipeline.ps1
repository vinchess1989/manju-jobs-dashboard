param(
    [Parameter(Mandatory=$true)]
    [string[]]$JobIds
)

$ErrorActionPreference = "Stop"

$PUBLIC_DIR = "C:\Users\vinee\manju_jobs"
$PRIVATE_DIR = "C:\Users\vinee\Manju_jobs_private"

Write-Host "=== STARTING LOCAL LLM PIPELINE ===" -ForegroundColor Yellow

Write-Host "`n[1/5] Tailoring resumes with local LLM..." -ForegroundColor Cyan
Set-Location $PUBLIC_DIR
$env:LOCAL_LLM_ENDPOINT = "http://localhost:1234/v1/chat/completions"
$env:LOCAL_LLM_MODEL = "hermes-3-llama-3.1-8b"
foreach ($id in $JobIds) {
    Write-Host "Generating JSON for $id..."
    .\venv\Scripts\python tailor_with_local_llm.py $id
}

Write-Host "`n[2/5] Building HTML & PDF Resumes..." -ForegroundColor Cyan
.\venv\Scripts\python build_resumes.py $JobIds

Write-Host "`n[3/5] Committing to Private Repo..." -ForegroundColor Cyan
Set-Location $PRIVATE_DIR
git add Resumes/
$status = git status --porcelain
if ($status) {
    $jobArgs = $JobIds -join " "
    git commit -m "Add resumes tailored via local LLM for $jobArgs"
    git push
} else {
    Write-Host "No changes to commit in private repository." -ForegroundColor Yellow
}

Write-Host "`n[4/5] Syncing to Firestore..." -ForegroundColor Cyan
Set-Location $PUBLIC_DIR
.\venv\Scripts\python sync_resume_links.py --upload

Write-Host "`n[5/5] Committing to Public Repo..." -ForegroundColor Cyan
Set-Location $PUBLIC_DIR
$pub_status = git status --porcelain
if ($pub_status) {
    $jobArgs = $JobIds -join " "
    git add input.csv curated_jobs.json
    git commit -m "Update resume links for local LLM batch $jobArgs"
    git push origin main
} else {
    Write-Host "No changes to commit in public repository." -ForegroundColor Yellow
}

Write-Host "`n=== PIPELINE SUCCESSFULLY COMPLETED ===" -ForegroundColor Green
