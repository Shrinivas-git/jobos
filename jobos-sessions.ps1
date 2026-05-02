param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("live-sync","document-vault","analytics","debug","list")]
    [string]$Session
)
$PROJECT_ROOT = "C:\staging\jobos"
$SONNET = "claude-sonnet-4-6"
$HAIKU  = "claude-haiku-4-5-20251001"
$sessions = @{
    "live-sync" = @{
        model = $HAIKU
        label = "TASK-018 - Candidate Live Sync"
        prompt = "STOP if context exceeds 95%. Read api/routers/candidates.py PUT /me endpoint. Task: when candidate updates profile via PUT /candidates/me, re-generate embedding and upsert to Qdrant resume_vectors. Also re-run matching for all open JDs this candidate is in. Scope: api/routers/candidates.py and api/tasks/resume_tasks.py ONLY. PDCA: list exact changes, wait for confirm."
    }
    "document-vault" = @{
        model = $SONNET
        label = "TASK-017 - Document Vault"
        prompt = "STOP if context exceeds 95%. Read api/routers/documents.py and PRD Section 8. Build document vault: candidates upload documents, access gated by pipeline stage, immutable access log, consent gating. PDCA: list all files, wait for confirm."
    }
    "analytics" = @{
        model = $SONNET
        label = "TASK-023 - Analytics Dashboard"
        prompt = "STOP if context exceeds 95%. Read api/routers/analytics.py and frontend/src/pages/Dashboard.tsx. Build analytics: pipeline health, recruiter performance, time-to-fill metrics. PDCA: list files, wait for confirm."
    }
    "debug" = @{
        model = $SONNET
        label = "Debug session"
        prompt = "STOP if context exceeds 95%. One error, one file. Paste: (1) full traceback (2) only the function that threw it."
    }
}
if ($Session -eq "list") {
    Write-Host ""
    Write-Host "  Available sessions:" -ForegroundColor Cyan
    foreach ($key in $sessions.Keys | Sort-Object) {
        Write-Host "  $key  ->  $($sessions[$key].label)" -ForegroundColor White
    }
    Write-Host ""
    exit 0
}
$s = $sessions[$Session]
Write-Host ""
Write-Host "  $($s.label)" -ForegroundColor Cyan
Write-Host "  Model: $($s.model)" -ForegroundColor DarkGray
Write-Host ""
$s.prompt | Set-Clipboard
Write-Host "  Copied to clipboard. Paste into Claude Code and press Enter" -ForegroundColor Green
Write-Host ""
Set-Location $PROJECT_ROOT
claude --model $s.model
