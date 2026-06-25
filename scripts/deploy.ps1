param(
    [switch]$SkipPush,
    [string]$CommitMessage = ""
)

# Spot On — push to GitHub and deploy on Ubuntu server
# Setup: copy deploy.config.ps1.example to deploy.config.ps1 and fill in values.
# Usage: .\scripts\deploy.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot

$configPath = Join-Path $RepoRoot "deploy.config.ps1"
if (-not (Test-Path $configPath)) {
    Write-Host "Missing deploy.config.ps1" -ForegroundColor Red
    Write-Host "Run: Copy-Item deploy.config.ps1.example deploy.config.ps1"
    Write-Host "Then edit deploy.config.ps1 with your GitHub token and SSH details."
    exit 1
}

$assignmentLines = Get-Content -Path $configPath -Encoding UTF8 | Where-Object {
    $_ -match '^\s*\$Deploy[A-Za-z]+\s*='
}
if (-not $assignmentLines) {
    Write-Host "No settings found in deploy.config.ps1" -ForegroundColor Red
    exit 1
}
Invoke-Expression ($assignmentLines -join [Environment]::NewLine)

foreach ($name in @(
        'DeployGitHubUser', 'DeployGitHubToken', 'DeployGitBranch',
        'DeploySshUser', 'DeploySshHost', 'DeployRemotePath'
    )) {
    if (-not (Get-Variable -Name $name -ValueOnly -ErrorAction SilentlyContinue)) {
        Write-Host "deploy.config.ps1 is missing `$$name" -ForegroundColor Red
        exit 1
    }
}

if ($DeployGitHubToken -match 'your_token_here') {
    Write-Host "Set a real GitHub token in deploy.config.ps1" -ForegroundColor Red
    exit 1
}

function Write-Step([string]$Text) {
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

# --- Local: optional commit + push ---
if (-not $SkipPush) {
    Write-Step "Checking git status"
    $status = git status --porcelain
    if ($status) {
        if ($CommitMessage) {
            Write-Step "Committing changes"
            git add -A
            git commit -m $CommitMessage
        } else {
            Write-Host "You have uncommitted changes:" -ForegroundColor Yellow
            git status -s
            $answer = Read-Host "Commit all and push? (y/N)"
            if ($answer -match '^[Yy]') {
                $msg = Read-Host "Commit message"
                if (-not $msg) { $msg = "Deploy $(Get-Date -Format 'yyyy-MM-dd HH:mm')" }
                git add -A
                git commit -m $msg
            } else {
                Write-Host "Push anyway without committing? Uncommitted files stay local only." -ForegroundColor Yellow
                $pushAnyway = Read-Host "Push current branch? (y/N)"
                if ($pushAnyway -notmatch '^[Yy]') { exit 1 }
            }
        }
    }

    Write-Step "Pushing to GitHub ($DeployGitBranch)"
    git push origin $DeployGitBranch
    if ($LASTEXITCODE -ne 0) {
        Write-Host "git push failed" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Step "Skipping push (-SkipPush)"
}

# --- Remote deploy via SSH ---
Write-Step "Deploying on $DeploySshUser@$DeploySshHost"

# Base64-encode credentials so special characters in tokens are safe over SSH
$userB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($DeployGitHubUser))
$tokenB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($DeployGitHubToken))
$branchB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($DeployGitBranch))
$pathB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($DeployRemotePath))
$buildArgsB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$DeployDockerBuildArgs"))

$remoteScript = @'
set -e
GH_USER=$(echo '__USER_B64__' | base64 -d)
GH_TOKEN=$(echo '__TOKEN_B64__' | base64 -d)
BRANCH=$(echo '__BRANCH_B64__' | base64 -d)
APP_PATH=$(echo '__PATH_B64__' | base64 -d)
BUILD_ARGS=$(echo '__BUILD_ARGS_B64__' | base64 -d)

echo "==> cd $APP_PATH"
cd "$APP_PATH"

echo "==> docker compose down"
docker compose down

echo "==> git pull"
git pull "https://${GH_USER}:${GH_TOKEN}@github.com/pcmodder2001/spotoncleaning.git" "$BRANCH"

echo "==> docker compose up -d --build $BUILD_ARGS"
# shellcheck disable=SC2086
docker compose up -d --build $BUILD_ARGS

echo "==> container status"
docker compose ps

echo "==> recent logs"
docker compose logs web --tail 20

echo "Deploy finished."
'@

$remoteScript = $remoteScript.Replace('__USER_B64__', $userB64)
$remoteScript = $remoteScript.Replace('__TOKEN_B64__', $tokenB64)
$remoteScript = $remoteScript.Replace('__BRANCH_B64__', $branchB64)
$remoteScript = $remoteScript.Replace('__PATH_B64__', $pathB64)
$remoteScript = $remoteScript.Replace('__BUILD_ARGS_B64__', $buildArgsB64)
$remoteScript = $remoteScript -replace "`r`n", "`n"

$remoteScript | ssh -o StrictHostKeyChecking=accept-new "${DeploySshUser}@${DeploySshHost}" "bash -s"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Remote deploy failed" -ForegroundColor Red
    exit 1
}

Write-Step "Done"
Write-Host "Site: https://spotonappliancecleaning.co.uk" -ForegroundColor Green
Write-Host "Server: http://${DeploySshHost}:8999" -ForegroundColor Green
