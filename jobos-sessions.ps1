param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('prd-read','debug','list','api','frontend','email-watcher','naukri-sourcer')]
    [string]$Session
)

$PROJECT_ROOT    = "C:\staging\jobos"
$CHECKPOINTS_DIR = Join-Path $PROJECT_ROOT ".checkpoints"
$FLASH           = "gemini-2.0-flash"
$PRO             = "gemini-2.5-pro"
$STACK           = "Python, FastAPI, React, MongoDB, Qdrant, Docker, Gemini API"

function Get-LatestCheckpoint {
    if (-not (Test-Path $CHECKPOINTS_DIR)) { return $null }
    $files = Get-ChildItem -Path $CHECKPOINTS_DIR -Filter "ck*.md" -File | Sort-Object Name -Descending
    if ($files.Count -eq 0) { return $null }
    return $files[0]
}

function Get-NextCheckpointPath {
    $files = Get-ChildItem -Path $CHECKPOINTS_DIR -Filter "ck*.md" -File
    $next  = ($files.Count + 1).ToString("D2")
    return Join-Path $CHECKPOINTS_DIR "ck$next.md"
}
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
$sessions = @{
    'prd-read' = @{
        model = $PRO
        task  = "TASK-000"
        label = "Session 0 -- PRD Read"
        prompt = "Read PRD.md and sync tasks."
    }
    'api' = @{
        model = $PRO
        task  = 'TASK-???'
        label = 'Session -- api'
        prompt = 'Focus on api module.'
    }

    'frontend' = @{
        model = $PRO
        task  = 'TASK-???'
        label = 'Session -- frontend'
        prompt = 'Focus on frontend module.'
    }

    'email-watcher' = @{
        model = $PRO
        task  = 'TASK-???'
        label = 'Session -- email-watcher'
        prompt = 'Focus on email-watcher module.'
    }

    'naukri-sourcer' = @{
        model = $PRO
        task  = 'TASK-???'
        label = 'Session -- naukri-sourcer'
        prompt = 'Focus on naukri-sourcer module.'
    }
    'debug' = @{
        model = $PRO
        task  = "DEBUG"
        label = "Debug Session"
        prompt = "Debug one error in one file."
    }
}
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
