param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("invoice","analytics","debug","list")]
    [string]$Session
)
$PROJECT_ROOT = "C:\staging\jobos"
$SONNET = "claude-sonnet-4-6"
$HAIKU  = "claude-haiku-4-5-20251001"
$sessions = @{
    "invoice" = @{
        model = $HAIKU
        label = "TASK-021 - Invoice Generation"
        prompt = "STOP if context exceeds 95%. Read api/routers/pipeline.py advance_stage endpoint. Task: when candidate reaches joined stage, auto-generate a PDF invoice for the client. Invoice should include: candidate name, JD title, client email, placement date, fee (15% of compensation_range from JD). Store invoice in MongoDB invoices collection. Save PDF to /data/invoices/. Send PDF via email to client. Use reportlab for PDF generation. PDCA: list files, wait for confirm."
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
