<#
    Machine-agnostic by design: every path is resolved relative to this
    script's own location ($PSScriptRoot) or via directory-signature /
    convention-based detection -- nothing is hardcoded. Drop this file in the
    root of any "jobs dashboard" repo (one with scraper.py +
    firebase_app/firebase.json) and it works unmodified on any machine.

    - THIS project = the repo this script lives in ($PSScriptRoot).
    - SIBLING project(s) = any directory alongside THIS one that has the same
      signature (scraper.py + firebase_app/firebase.json) -- e.g. a
      "vineeth_jobs"-style second dashboard, if this machine has one. If none
      is found, that step is skipped with a log line, not an error.
    - Firebase project id is read from each project's own
      firebase_app/.firebaserc rather than passed with --project, so no
      project id needs to be hardcoded here either.
    - PRIVATE companion repo (Resumes/) is resolved the same way the
      tailor-resume / fill-form skills already do: $env:MANJU_PRIVATE_DIR,
      else a sibling directory with "private" in its name, else a sibling
      directory containing a Resumes\ subfolder.
#>
$ErrorActionPreference = "Continue"

function Find-Python([string]$projectDir) {
    foreach ($candidate in @(".venv\Scripts\python.exe", "venv\Scripts\python.exe")) {
        $full = Join-Path $projectDir $candidate
        if (Test-Path $full) { return $full }
    }
    return "python"
}

# NOTE on $script:lastProjectOk vs `return`: pytest/git/firebase all print
# output that isn't redirected here (deliberately -- we want it visible in
# the log). In PowerShell, any such unredirected output produced inside a
# function becomes part of that function's return value stream alongside an
# explicit `return`, turning a captured `$x = Publish-Project ...` into a
# multi-element array whose truthiness in `if ($x)` no longer reflects the
# intended boolean (a non-empty array is always truthy, regardless of its
# last element). Using a script-scoped variable instead of a return value
# sidesteps that pitfall entirely.
function Publish-Project([string]$name, [string]$projectDir) {
    $script:lastProjectOk = $true
    Write-Host "=== Testing $name ($projectDir) ===" -ForegroundColor Cyan
    if (-not (Test-Path $projectDir)) {
        Write-Host "SKIP: $name not found on this machine ($projectDir)." -ForegroundColor Yellow
        return
    }

    Set-Location $projectDir
    $pythonExe = Find-Python $projectDir
    if (Test-Path (Join-Path $projectDir "tests")) {
        & $pythonExe -m pytest tests/ -v
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: $name tests failed! Aborting publish for this project." -ForegroundColor Red
            $script:lastProjectOk = $false
            return
        }
        Write-Host "All $name tests passed! Proceeding to publish." -ForegroundColor Green
    } else {
        Write-Host "No tests/ directory for $name -- skipping test step." -ForegroundColor Yellow
    }

    Write-Host "`n=== Committing & Pushing $name ===" -ForegroundColor Cyan
    Set-Location $projectDir
    $candidateFiles = @(
        "jobs.json", "seen_urls.json", "checkpoint.json", "job_descriptions",
        "job_requirements.md", "CLAUDE.md", "firebase_app/index.html", "firebase_app/review.html",
        "firebase_app/firestore.rules", "scraper.py", "orchestrator.py", "db_utils.py",
        "curate_jobs.py", "evaluate_with_local_llm.py", "tests", "jobs_history.json",
        "deleted.json", "publish_dashboards.ps1", "html_to_pdf.py", "make_resume.py",
        "upload_resume_links.py", "input.csv", "sync_resume_links.py", "add_job.py",
        "scrape_application.py", "fill_agent.py", "scratch/update_status.py",
        "job_status_store.py",
        ".claude", ".agents", ".gitignore", ".nojekyll"
    )
    $existing = $candidateFiles | Where-Object { Test-Path (Join-Path $projectDir $_) }
    if ($existing.Count -gt 0) {
        git add $existing
    }
    $staged = git diff --cached --name-only
    if ($staged) {
        git commit -m "chore: update $name dashboard [all tests passing]"
        Write-Host "Committed staged changes for $name." -ForegroundColor Green
    } else {
        Write-Host "No staged changes to commit for $name." -ForegroundColor Yellow
    }
    git push
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Push rejected -- pulling --rebase and retrying once..." -ForegroundColor Yellow
        git pull --rebase
        git push
    }

    $firebaseAppDir = Join-Path $projectDir "firebase_app"
    if (Test-Path (Join-Path $firebaseAppDir "firebase.json")) {
        Write-Host "`n=== Deploying $name Firebase ===" -ForegroundColor Cyan
        if (Get-Command firebase -ErrorAction SilentlyContinue) {
            Set-Location $firebaseAppDir
            # Project id comes from firebase_app/.firebaserc (no --project needed).
            firebase deploy --only hosting --non-interactive
        } else {
            Write-Host "WARNING: firebase CLI not found on PATH -- skipping deploy for $name." -ForegroundColor Yellow
        }
    }
}

# ---------------------------------------------------------------------------
# Discover THIS project and any sibling project(s) with the same signature.
# ---------------------------------------------------------------------------

$thisProject = $PSScriptRoot
$parentDir = Split-Path $thisProject -Parent

$siblingProjects = @()
if ($parentDir -and (Test-Path $parentDir)) {
    $siblingProjects = Get-ChildItem $parentDir -Directory -ErrorAction SilentlyContinue | Where-Object {
        $_.FullName -ne $thisProject `
        -and (Test-Path (Join-Path $_.FullName "scraper.py")) `
        -and (Test-Path (Join-Path $_.FullName "firebase_app\firebase.json"))
    } | Select-Object -ExpandProperty FullName
}

$script:lastProjectOk = $true
Publish-Project (Split-Path $thisProject -Leaf) $thisProject | Out-Null
$allOk = $script:lastProjectOk

foreach ($sibling in $siblingProjects) {
    Write-Host ""
    Publish-Project (Split-Path $sibling -Leaf) $sibling | Out-Null
    $allOk = $allOk -and $script:lastProjectOk
}
if ($siblingProjects.Count -eq 0) {
    Write-Host "`nNo sibling dashboard project found alongside this one -- publishing just this project." -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# Private companion repo (Resumes/)
# ---------------------------------------------------------------------------

Write-Host "`n=== Committing & Pushing private companion repo ===" -ForegroundColor Cyan

$PRIVATE = $env:MANJU_PRIVATE_DIR
if (-not $PRIVATE -or -not (Test-Path $PRIVATE)) {
    $PRIVATE = Get-ChildItem $parentDir -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "private" } |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $PRIVATE) {
    $PRIVATE = Get-ChildItem $parentDir -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName "Resumes") } |
        Select-Object -First 1 -ExpandProperty FullName
}

if ($PRIVATE -and (Test-Path $PRIVATE)) {
    Write-Host "Using private repo: $PRIVATE"
    Set-Location $PRIVATE
    git add Resumes\
    $privateStaged = git diff --cached --name-only
    if ($privateStaged) {
        git commit -m "chore: update private resumes [auto-publish]"
        Write-Host "Committed staged changes for private repo." -ForegroundColor Green
    } else {
        Write-Host "No staged changes to commit for private repo." -ForegroundColor Yellow
    }
    git push
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Push rejected -- pulling --rebase and retrying once..." -ForegroundColor Yellow
        git pull --rebase
        git push
    }
} else {
    Write-Host "WARNING: No private companion repo found on this machine (checked `$env:MANJU_PRIVATE_DIR, sibling '*private*' dirs, sibling dirs with a Resumes\ folder)." -ForegroundColor Yellow
}

if ($allOk) {
    Write-Host "`n=== SUCCESS: Dashboard(s) published and private repo synced! ===" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n=== FAILED: One or more projects failed tests -- see above. ===" -ForegroundColor Red
    exit 1
}
