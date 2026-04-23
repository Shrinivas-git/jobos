# ==============================================================================
# setup-jobos-v4.ps1
# CUSTOMIZED for JobOS based on Gemini-v4 superior setup.
# ==============================================================================

# -- CONFIGURATION -------------------------------------------------------------
$PROJECT_NAME  = "jobos"
$PROJECT_ROOT  = "C:\staging\jobos"
$STACK         = "Python, FastAPI, React, MongoDB, Qdrant, Docker, Gemini API"
$MODULES       = @("api", "frontend", "email-watcher", "naukri-sourcer")
$PHASE_CURRENT = 1

$FLASH = "gemini-2.0-flash"
$PRO   = "gemini-2.5-pro"

Write-Host "================================================================" -ForegroundColor Magenta
Write-Host "  $PROJECT_NAME -- UPGRADE TO V4 WORKFLOW" -ForegroundColor Magenta
Write-Host "================================================================" -ForegroundColor Magenta

if (-not (Test-Path $PROJECT_ROOT)) {
    New-Item -ItemType Directory -Path $PROJECT_ROOT | Out-Null
}
Set-Location $PROJECT_ROOT

# -- 1. Folder structure -------------------------------------------------------
Write-Host "[ 1/3 ] Ensuring folder structure..." -ForegroundColor Yellow
$folders = @("tasks","docs","docs\plans","tests",".gemini\skills",".checkpoints")
foreach ($f in $folders) {
    $path = Join-Path $PROJECT_ROOT $f
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path | Out-Null
        Write-Host "  OK  $f" -ForegroundColor Green
    }
}

# -- 2. GEMINI.md --------------------------------------------------------------
Write-Host "[ 2/3 ] Writing GEMINI.md..." -ForegroundColor Yellow
$moduleMap = ($MODULES | ForEach-Object { "  Session --> $_  : $_\ only" }) -join "`n"
$geminiMd = @"
# GEMINI.md -- $PROJECT_NAME
# Developer Edition -- Gemini CLI V4.

## Stack
$STACK

## Models
  Flash : $FLASH
  Pro   : $PRO

## Current Phase: $PHASE_CURRENT

## Module Boundaries
$moduleMap
  Session --> prd-read : reads PRD.md, creates all TASK-XXX stubs (ALWAYS FIRST)
  Session --> debug    : one error + one file per session

## Git
  Format: [TASK-XXX] verb: what changed
"@
$geminiMd | Set-Content "$PROJECT_ROOT\GEMINI.md" -Encoding UTF8

# -- 3. Generate launcher (jobos-sessions.ps1) ---------------------------------
Write-Host "[ 3/3 ] Generating jobos-sessions.ps1..." -ForegroundColor Yellow

$sessionKeys = @("prd-read", "debug", "list") + $MODULES
$validateSet = ($sessionKeys | ForEach-Object { "'$_'" }) -join ","

# We build the sessions script by pieces to avoid nested here-string issues
$header = @"
param(
    [Parameter(Mandatory=`$true)]
    [ValidateSet($validateSet)]
    [string]`$Session
)

`$PROJECT_ROOT    = "$PROJECT_ROOT"
`$CHECKPOINTS_DIR = Join-Path `$PROJECT_ROOT ".checkpoints"
`$FLASH           = "$FLASH"
`$PRO             = "$PRO"
`$STACK           = "$STACK"

function Get-LatestCheckpoint {
    if (-not (Test-Path `$CHECKPOINTS_DIR)) { return `$null }
    `$files = Get-ChildItem -Path `$CHECKPOINTS_DIR -Filter "ck*.md" -File | Sort-Object Name -Descending
    if (`$files.Count -eq 0) { return `$null }
    return `$files[0]
}

function Get-NextCheckpointPath {
    `$files = Get-ChildItem -Path `$CHECKPOINTS_DIR -Filter "ck*.md" -File
    `$next  = (`$files.Count + 1).ToString("D2")
    return Join-Path `$CHECKPOINTS_DIR "ck`$next.md"
}
"@

$helpers = @'
function Write-Checkpoint {
    param($SessionKey, $TaskId, $Label)
    $ckPath = Get-NextCheckpointPath
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm"
    $changed = git -C $PROJECT_ROOT diff --name-only HEAD 2>$null
    $changedList = if ($changed) { $changed -join "`n" } else { "(no changes)" }
    
    $content = @"
# Checkpoint -- $Label
**Session :** $SessionKey
**Task     :** $TaskId
**Saved    :** $ts

## What was completed
[Paste SESSION-SUMMARY from Gemini here]

## Files changed
$changedList
"@
    $content | Set-Content $ckPath -Encoding UTF8
    Write-Host ""
    Write-Host "  CHECKPOINT  $ckPath" -ForegroundColor Cyan
}

function Invoke-GitCommitPush {
    param($TaskId, $Label)
    Write-Host "[ GIT ] Staging and committing..." -ForegroundColor Yellow
    git -C $PROJECT_ROOT add -A
    $msg = "[$TaskId] $Label -- session end"
    git -C $PROJECT_ROOT commit -m $msg
    $branch = git -C $PROJECT_ROOT rev-parse --abbrev-ref HEAD
    Write-Host "[ GIT ] Pushing $branch..." -ForegroundColor Yellow
    git -C $PROJECT_ROOT push origin $branch
}

function Get-ResumeBlock {
    $ck = Get-LatestCheckpoint
    if ($null -eq $ck) { return "" }
    $ckContent = Get-Content $ck.FullName -Raw
    return "`n======================================================`nRESUME FROM CHECKPOINT: $($ck.Name)`n$ckContent`n======================================================`n"
}
'@

$sessionsDefStart = "`n`$sessions = @{`n"
$prdReadDef = @"
    'prd-read' = @{
        model = `$PRO
        task  = "TASK-000"
        label = "Session 0 -- PRD Read"
        prompt = "Read PRD.md and sync tasks."
    }
"@

$moduleBlocks = ""
foreach ($mod in $MODULES) {
    $moduleBlocks += "`n    '$mod' = @{`n"
    $moduleBlocks += "        model = `$PRO`n"
    $moduleBlocks += "        task  = 'TASK-???'`n"
    $moduleBlocks += "        label = 'Session -- $mod'`n"
    $moduleBlocks += "        prompt = 'Focus on $mod module.'`n"
    $moduleBlocks += "    }`n"
}

$debugDef = @"
    'debug' = @{
        model = `$PRO
        task  = "DEBUG"
        label = "Debug Session"
        prompt = "Debug one error in one file."
    }
}
"@

$launcherLogic = @'
if ($Session -eq "list") {
    Write-Host "`n  Available sessions:" -ForegroundColor Magenta
    foreach ($key in $sessions.Keys | Sort-Object) {
        Write-Host "    $key"
    }
    exit 0
}

$s = $sessions[$Session]
$resume = Get-ResumeBlock
$prompt = $resume + $s.prompt + "`n`nEND OF SESSION: Type SESSION-SUMMARY: <paragraph>."

$prompt | Set-Clipboard
Write-Host "`n  LAUNCHING: $($s.label)" -ForegroundColor Magenta
gemini --model $s.model

Write-Checkpoint -SessionKey $Session -TaskId $s.task -Label $s.label
$doGit = Read-Host "  Commit and push? [Y/n]"
if ($doGit -ne "n") { Invoke-GitCommitPush -TaskId $s.task -Label $s.label }
'@

$finalScript = $header + "`n" + $helpers + $sessionsDefStart + $prdReadDef + $moduleBlocks + $debugDef + "`n" + $launcherLogic
$finalScript | Set-Content "$PROJECT_ROOT\jobos-sessions.ps1" -Encoding UTF8

Write-Host "================================================================" -ForegroundColor Green
Write-Host "  BOOTSTRAP COMPLETE." -ForegroundColor Green
Write-Host "  1. Run: .\jobos-sessions.ps1 -Session list" -ForegroundColor Cyan
Write-Host "  2. Start with: .\jobos-sessions.ps1 -Session prd-read" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Green
