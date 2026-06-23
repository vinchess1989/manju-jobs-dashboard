# run_make_resume_pipeline.ps1
# Combined script to execute the entire make-resume workflow in a single run.

# Dynamically discover repository paths using find_repos.py
$repos = python "$PSScriptRoot\find_repos.py" --json | ConvertFrom-Json
$PUBLIC_DIR = $repos.public
$PRIVATE_DIR = $repos.private

if (-not $PUBLIC_DIR -or -not $PRIVATE_DIR) {
    Write-Error "ERROR: Could not locate both public and private repositories using find_repos.py."
    Exit 1
}

# Exit on error
$ErrorActionPreference = "Stop"

Write-Host "=== STARTING MAKE-RESUMES PIPELINE ===" -ForegroundColor Yellow
Write-Host "Public Directory:  $PUBLIC_DIR"
Write-Host "Private Directory: $PRIVATE_DIR"

# Step 1: Pull both repositories
Write-Host "`n[1/5] Pulling latest changes from repositories..." -ForegroundColor Cyan
Write-Host "Pulling Public Repo..."
git -C $PUBLIC_DIR pull
Write-Host "Pulling Private Repo..."
git -C $PRIVATE_DIR pull

# Step 2: Build HTML & PDF Resumes (using the python batch builder)
Write-Host "`n[2/5] Running resume builder script..." -ForegroundColor Cyan
python "$PUBLIC_DIR\build_resumes.py" $args

# Step 3: Push generated files to Private Repo
Write-Host "`n[3/5] Committing and pushing resumes to Private Repo..." -ForegroundColor Cyan
git -C $PRIVATE_DIR add Resumes/
# Check if there are changes to commit to avoid error
$status = git -C $PRIVATE_DIR status --porcelain
if ($status) {
    git -C $PRIVATE_DIR commit -m "Add resume docs for batch: Optimate, Gofore, Kela, Skyline Legal, Academic Work"
    git -C $PRIVATE_DIR push
    Write-Host "Changes pushed to private repository." -ForegroundColor Green
} else {
    Write-Host "No changes to commit in private repository." -ForegroundColor Yellow
}

# Step 4: Sync resume links to Firestore (requires running inside Public Repo directory)
Write-Host "`n[4/5] Syncing resume links to Firestore..." -ForegroundColor Cyan
Push-Location $PUBLIC_DIR
try {
    python sync_resume_links.py --upload
} finally {
    Pop-Location
}

# Step 5: Push Public Repo updates (input.csv)
Write-Host "`n[5/5] Committing and pushing resume links to Public Repo..." -ForegroundColor Cyan
$pub_status = git -C $PUBLIC_DIR status --porcelain
if ($pub_status) {
    git -C $PUBLIC_DIR add input.csv
    git -C $PUBLIC_DIR commit -m "Update resume links for batch"
    git -C $PUBLIC_DIR push origin main
    Write-Host "Changes pushed to public repository." -ForegroundColor Green
} else {
    Write-Host "No changes to commit in public repository." -ForegroundColor Yellow
}

Write-Host "`n=== PIPELINE SUCCESSFULLY COMPLETED ===" -ForegroundColor Green
