param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("crm-messages","task-management","analytics","debug","list")]
    [string]$Session
)
$PROJECT_ROOT = "C:\staging\jobos"
$SONNET = "claude-sonnet-4-6"
$HAIKU  = "claude-haiku-4-5-20251001"
$sessions = @{
    "crm-messages" = @{
        model = $SONNET
        label = "TASK-019 - CRM Message Approval"
        prompt = "STOP if context exceeds 95%. Read api/routers/crm.py and frontend/src/pages/CRM.tsx. Build CRM message approval: Groq drafts outreach message for shortlisted candidate based on JD and candidate profile. Recruiter reviews and approves/edits. On approval send via email using existing send_email(). Store in crm_messages MongoDB collection. PDCA: list files, wait for confirm."
    }
    "task-management" = @{
        model = $SONNET
        label = "TASK-020 - Task Management"
        prompt = "STOP if context exceeds 95%. Read PRD Section 10 and api/routers/crm.py. Build task management: auto-create tasks on pipeline actions, task list UI for recruiters, call logging, due dates. PDCA: list files, wait for confirm."
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
