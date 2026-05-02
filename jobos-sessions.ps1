param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("retention","analytics","admin-config","debug","list")]
    [string]$Session
)
$PROJECT_ROOT = "C:\staging\jobos"
$SONNET = "claude-sonnet-4-6"
$HAIKU  = "claude-haiku-4-5-20251001"
$sessions = @{
    "retention" = @{
        model = $HAIKU
        label = "TASK-022 - Retention Clock and Finance"
        prompt = "STOP if context exceeds 95%. Read api/routers/pipeline.py and api/tasks/notification_tasks.py. Task: when candidate reaches joined stage, start a 180-day retention clock. At 90 days send warning to manager. At 180 days send invoice reminder. Store retention records in MongoDB retention_tracking collection. Add Celery Beat task check_retention_clock running daily. PDCA: list files, wait for confirm."
    }
    "analytics" = @{
        model = $SONNET
        label = "TASK-023 - Analytics Dashboard"
        prompt = "STOP if context exceeds 95%. Read api/routers/analytics.py and frontend/src/pages/Dashboard.tsx. Build analytics page at /analytics: pipeline health, recruiter performance, time-to-fill. PDCA: list files, wait for confirm."
    }
    "admin-config" = @{
        model = $HAIKU
        label = "TASK-024 - Admin Config UI"
        prompt = "STOP if context exceeds 95%. Build admin config page at /admin: edit p_threshold, k_threshold, batch_size. Admin role only. PDCA: list files, wait for confirm."
    }
    "debug" = @{
        model = $SONNET
        label = "Debug session"
        prompt = "STOP if context exceeds 95%. One error, one file. Paste traceback and function."
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
