# ==============================================================================
# g_sessions_template.ps1
# Copy this, rename <project>-sessions.ps1, fill sessions hashtable.
# Owner: Srinivas / Fidelitus Corp
# Developer Edition -- Gemini CLI.
# Mirrors: sessions-template.ps1 (Claude Code edition)
#
# v2 additions:
#   - Local checkpoint file written to .checkpoints\ckXX.md after every session
#   - Memory compression block injected into session prompt when checkpoint exists
#   - Auto git commit + push at end of session (staged files only)
# ==============================================================================

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("prd-read","module1","module2","debug","list")]
    [string]$Session
)

$PROJECT_ROOT    = "D:\staging\your-project"
$CHECKPOINTS_DIR = Join-Path $PROJECT_ROOT ".checkpoints"
$FLASH           = "gemini-2.0-flash"    # Fast + cheap  --> boilerplate, config, CRUD, JSON
$PRO             = "gemini-2.5-pro"      # Reasoning     --> real coding, APIs, debugging, docs

# ==============================================================================
# HELPER -- find the latest checkpoint file (ckNN.md), return $null if none
# ==============================================================================
function Get-LatestCheckpoint {
    if (-not (Test-Path $CHECKPOINTS_DIR)) { return $null }
    $files = Get-ChildItem -Path $CHECKPOINTS_DIR -Filter "ck*.md" -File |
             Sort-Object Name -Descending
    if ($files.Count -eq 0) { return $null }
    return $files[0]
}

# ==============================================================================
# HELPER -- derive next checkpoint filename  ck01.md, ck02.md ...
# ==============================================================================
function Get-NextCheckpointPath {
    if (-not (Test-Path $CHECKPOINTS_DIR)) {
        New-Item -ItemType Directory -Path $CHECKPOINTS_DIR | Out-Null
    }
    $files = Get-ChildItem -Path $CHECKPOINTS_DIR -Filter "ck*.md" -File
    $next  = ($files.Count + 1).ToString("D2")
    return Join-Path $CHECKPOINTS_DIR "ck$next.md"
}

# ==============================================================================
# HELPER -- write checkpoint file after session ends
# ==============================================================================
function Write-Checkpoint {
    param([string]$SessionKey, [string]$TaskId, [string]$Label)

    $ckPath = Get-NextCheckpointPath
    $ts     = Get-Date -Format "yyyy-MM-dd HH:mm"

    $content = @"
# Checkpoint -- $Label
**Session :** $SessionKey
**Task     :** $TaskId
**Saved    :** $ts
**Model    :** $PRO / $FLASH (see session def)

## What was completed this session
[Gemini did not auto-fill this -- summarise manually or paste /chat save output]

## Files changed
$(
    $changed = git -C $PROJECT_ROOT diff --name-only HEAD 2>$null
    if ($changed) { $changed } else { "(run: git diff --name-only HEAD)" }
)

## Decisions made
- [decision 1]
- [decision 2]

## Blockers / open items
- [blocker 1]

## Next session should start with
- Task  : [next task id]
- Focus : [one sentence]
"@

    $content | Set-Content $ckPath -Encoding UTF8
    Write-Host ""
    Write-Host "  CHECKPOINT  $ckPath" -ForegroundColor Cyan
    Write-Host "  Edit it now to capture what Gemini completed." -ForegroundColor DarkGray
}

# ==============================================================================
# HELPER -- git commit + push staged + untracked files
# ==============================================================================
function Invoke-GitCommitPush {
    param([string]$TaskId, [string]$Label)

    Write-Host ""
    Write-Host "[ GIT ] Staging all changes..." -ForegroundColor Yellow
    git -C $PROJECT_ROOT add -A 2>&1 | Out-Null

    $status = git -C $PROJECT_ROOT status --porcelain 2>$null
    if (-not $status) {
        Write-Host "  GIT  Nothing to commit. Working tree clean." -ForegroundColor DarkGray
        return
    }

    $msg = "[$TaskId] $Label -- session end"
    git -C $PROJECT_ROOT commit -m $msg 2>&1 | ForEach-Object { Write-Host "  $_" }

    $branch = git -C $PROJECT_ROOT rev-parse --abbrev-ref HEAD 2>$null
    Write-Host ""
    Write-Host "[ GIT ] Pushing branch '$branch' to origin..." -ForegroundColor Yellow
    $pushResult = git -C $PROJECT_ROOT push origin $branch 2>&1
    $pushResult | ForEach-Object { Write-Host "  $_" }

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK  Pushed to origin/$branch" -ForegroundColor Green
    } else {
        Write-Host "  WARN  Push failed -- check remote / auth." -ForegroundColor Red
    }
}

# ==============================================================================
# HELPER -- build memory-resume prefix from latest checkpoint
# ==============================================================================
function Get-ResumeBlock {
    $ck = Get-LatestCheckpoint
    if ($null -eq $ck) { return "" }

    $ckContent = Get-Content $ck.FullName -Raw
    return @"

======================================================
RESUME FROM CHECKPOINT: $($ck.Name)
======================================================
$ckContent
======================================================
Continue from the NEXT SESSION section above.
Do NOT repeat completed work. Ask if anything is unclear.
======================================================

"@
}

# ==============================================================================
# SESSION DEFINITIONS
# ==============================================================================
$sessions = @{

    # -- ALWAYS THE FIRST SESSION ON ANY PROJECT --------------------------------
    "prd-read" = @{
        model = $PRO
        task  = "TASK-000"
        label = "Session 0 -- PRD Read and Task Generation"
        prompt = @'
FIRST SESSION -- PRD READ AND TASK GENERATION
==============================================
Your ONLY job this session:
1. Use filesystem MCP to read PRD.md in full.
2. Run skill: prd-parse
3. Create one TASK-XXX-<slug>.md per deliverable in tasks/
4. List all created tasks (number + title).
5. Do NOT write any code. Planning only.

PDCA: Present task list BEFORE creating files. Wait for approval.

END OF SESSION: When done, type exactly:
  SESSION-SUMMARY: <one paragraph of what was completed, decisions made, next task>
'@
    }

    # -- MECHANICAL SESSION -- use Flash ----------------------------------------
    module1 = @{
        model = $FLASH
        task  = "TASK-001"
        label = "Session 1 -- Module 1 name"
        prompt = @'
Stack: [your stack]
Task file: tasks/TASK-001-[slug].md
Module scope: app/module1/ ONLY.

Key facts:
- [fact 1]
- [fact 2]

Use context7 for [library] API.
PDCA: present plan before touching any file.

END OF SESSION: When done, type exactly:
  SESSION-SUMMARY: <one paragraph of what was completed, decisions made, next task>
'@
    }

    # -- REASONING SESSION -- use Pro -------------------------------------------
    module2 = @{
        model = $PRO
        task  = "TASK-002"
        label = "Session 2 -- Module 2 name"
        prompt = @'
Stack: [your stack]
Task file: tasks/TASK-002-[slug].md
Module scope: app/module2/ ONLY.

Key facts:
- [fact 1]

Use context7 for [library] API.
PDCA: present plan before touching any file.

END OF SESSION: When done, type exactly:
  SESSION-SUMMARY: <one paragraph of what was completed, decisions made, next task>
'@
    }

    # -- DEBUG SESSION -- always Pro --------------------------------------------
    debug = @{
        model = $PRO
        task  = "TASK-???"
        label = "Debug Session"
        prompt = @'
Stack: [your stack]
Task: one error, one file, one session.
Paste: (1) full traceback (2) only the function that threw it.
Known gotchas: [list project-specific gotchas]

Think step by step. Do not touch any file outside the one that threw the error.

END OF SESSION: When done, type exactly:
  SESSION-SUMMARY: <one paragraph of what was completed, decisions made, next task>
'@
    }
}

# ==============================================================================
# LIST
# ==============================================================================
if ($Session -eq "list") {
    Write-Host ""
    Write-Host "  Available sessions:" -ForegroundColor Magenta
    Write-Host ""
    foreach ($key in $sessions.Keys | Sort-Object) {
        $s = $sessions[$key]
        if ($s.model -like "*flash*") { $tag = "Flash  (fast/cheap)" }
        else                          { $tag = "Pro    (reasoning)"  }
        Write-Host ("  {0,-14}  {1,-40}  [{2}]" -f $key, $s.label, $tag)
    }
    Write-Host ""

    # Show latest checkpoint if exists
    $ck = Get-LatestCheckpoint
    if ($ck) {
        Write-Host "  Latest checkpoint: $($ck.Name)  ($($ck.LastWriteTime.ToString('yyyy-MM-dd HH:mm')))" -ForegroundColor Cyan
    } else {
        Write-Host "  No checkpoints yet." -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  Model strings:" -ForegroundColor DarkGray
    Write-Host "    Flash = $FLASH" -ForegroundColor DarkGray
    Write-Host "    Pro   = $PRO"   -ForegroundColor DarkGray
    Write-Host ""
    exit 0
}

# ==============================================================================
# LAUNCH
# ==============================================================================
$s = $sessions[$Session]

# -- prepend resume block if a checkpoint exists
$resumeBlock = Get-ResumeBlock
$fullPrompt  = $resumeBlock + $s.prompt

Write-Host ""
Write-Host "  +----------------------------------------------+" -ForegroundColor Magenta
Write-Host ("  |  {0,-44}|" -f $s.label) -ForegroundColor Magenta
Write-Host ("  |  Model : {0,-37}|" -f $s.model) -ForegroundColor Magenta
Write-Host ("  |  Task  : {0,-37}|" -f $s.task) -ForegroundColor Magenta
if ($resumeBlock) {
Write-Host "  |  RESUME: checkpoint injected into prompt      |" -ForegroundColor Cyan
}
Write-Host "  +----------------------------------------------+" -ForegroundColor Magenta
Write-Host ""
Write-Host $fullPrompt -ForegroundColor White
Write-Host ""
$fullPrompt | Set-Clipboard
Write-Host "  OK  Prompt copied to clipboard." -ForegroundColor Green
Write-Host "  Paste into gemini when it opens, then: superpowers brainstorm" -ForegroundColor Cyan
Write-Host ""

Set-Location $PROJECT_ROOT
gemini --model $s.model

# ==============================================================================
# POST-SESSION -- runs after gemini exits
# ==============================================================================
Write-Host ""
Write-Host "  Gemini session ended." -ForegroundColor Yellow
Write-Host ""

# 1. Write checkpoint
Write-Checkpoint -SessionKey $Session -TaskId $s.task -Label $s.label

# 2. Git commit + push
$doGit = Read-Host "  Commit and push to GitHub? [Y/n]"
if ($doGit -ne "n" -and $doGit -ne "N") {
    Invoke-GitCommitPush -TaskId $s.task -Label $s.label
}

Write-Host ""
Write-Host "  Done. Next run will resume from the checkpoint above." -ForegroundColor Green
Write-Host ""
