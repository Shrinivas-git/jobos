param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("pipeline-ui","why-not-selected","debug","list")]
    [string]$Session
)
$PROJECT_ROOT = "C:\staging\jobos"
$SONNET = "claude-sonnet-4-6"
$HAIKU  = "claude-haiku-4-5-20251001"
$sessions = @{
    "pipeline-ui" = @{
        model = $SONNET
        label = "TASK-015 - Pipeline Stage Management UI"
        prompt = "STOP if context exceeds 95%. Read PRD Section 7.1-7.2 and tasks/TASK-015-closure-enforcement.md and frontend/src/pages/RecruiterDashboard.tsx first. TASK-015 UI: Add a Pipeline tab inside RecruiterDashboard. For each shortlisted candidate show: current stage (shortlist/interview_1/interview_final/offer/joined), time remaining as progress bar (green=safe, yellow=75%, red=100%), Advance Stage button, Request Extension button. For managers show: Approve/Deny extension requests, breach list of overdue candidates. Use GET /pipeline/{jd_id}, POST /pipeline/advance/{jd_id}/{candidate_id}, POST /pipeline/extension-request, POST /pipeline/extension-approve endpoints. PDCA: list all files, wait for confirm, then apply."
    }
    "why-not-selected" = @{
        model = $SONNET
        label = "TASK-016 - Why Not Selected feedback engine"
        prompt = "STOP if context exceeds 95%. Read tasks/TASK-016-why-not-selected.md and api/utils/gemini_utils.py first. Build feedback generation: when candidate is rejected, Groq generates constructive feedback explaining why. Store in MongoDB. Send weekly digest email to candidates. PDCA: list files, wait for confirm."
    }
    "debug" = @{
        model = $SONNET
        label = "Debug session"
        prompt = "STOP if context exceeds 95%. Stack: Python/FastAPI/Groq/Docker. One error, one file, one session. Paste: (1) full traceback (2) only the function that threw it."
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
