param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("notifications","candidate-page","jd-fix","debug","list")]
    [string]$Session
)
$PROJECT_ROOT = "C:\staging\jobos"
$SONNET = "claude-sonnet-4-6"
$HAIKU  = "claude-haiku-4-5-20251001"
$sessions = @{
    "notifications" = @{
        model = $SONNET
        label = "TASK-009 - Manager and HOD notifications"
        prompt = "Read PRD.md Section 6.5 and tasks/TASK-009-manager-hod-notifications.md first. Stack: FastAPI/MongoDB/SMTP. Task: TASK-009. Build notification system: when Pass 2 matching completes for a JD, send email digest to Manager and HOD with stack-ranked candidate list including name, fitment score, strengths, gaps, recommendation. Also add in-app notification badge in the frontend header. PDCA: list all files, wait for confirm before touching anything."
    }
    "candidate-page" = @{
        model = $HAIKU
        label = "TASK-012 - Candidate simple landing page"
        prompt = "Stack: React frontend. Scope: frontend/src only. When user role is candidate, show a simple page instead of recruiter dashboard. Content: their name, email, skills, experience. Message: Your profile has been received. Our team will be in touch. No dashboard stats, no JD list, no matching engine. PDCA: list files, wait for confirm."
    }
    "jd-fix" = @{
        model = $HAIKU
        label = "JD intake fixes"
        prompt = "Stack: Python/FastAPI. Read api/tasks/jd_tasks.py first. Fix any remaining JD intake issues. PDCA: show plan before touching anything."
    }
    "debug" = @{
        model = $SONNET
        label = "Debug session"
        prompt = "Stack: Python/FastAPI/Groq/Docker. One error, one file, one session. Paste: (1) full traceback (2) only the function that threw it."
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
