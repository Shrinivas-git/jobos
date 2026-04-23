# ==============================================================================
# g_setup_project_template.ps1
# Copy this, rename setup-<project>.ps1, fill the 5 variables.
# PRD.md MUST exist in PROJECT_ROOT before running.
# Owner: Srinivas / Fidelitus Corp
# Developer Edition -- Gemini CLI.
# Mirrors: setup-project-template.ps1 (Claude Code edition)
#
# v2: Step 7 now generates <project>-sessions.ps1 with all modules pre-filled.
#     Step 8 prepares PRD-read prompt and launches gemini.
# ==============================================================================

# -- FILL THESE 5 VARIABLES ----------------------------------------------------
$PROJECT_NAME  = "your-project-name"
$PROJECT_ROOT  = "D:\staging\your-project"
$STACK         = "Python 3.11, FastAPI, PostgreSQL, Docker"
$MODULES       = @("module1", "module2", "module3")
$PHASE_CURRENT = 0
# ------------------------------------------------------------------------------

$FLASH = "gemini-2.0-flash"
$PRO   = "gemini-2.5-pro"

Write-Host ""
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host "  $PROJECT_NAME -- PROJECT BOOTSTRAP (GEMINI CLI)" -ForegroundColor Magenta
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host ""

if (-not (Test-Path $PROJECT_ROOT)) {
    New-Item -ItemType Directory -Path $PROJECT_ROOT | Out-Null
}
Set-Location $PROJECT_ROOT

# -- 0. PRD.md check -- hard stop if missing -----------------------------------
Write-Host "[ 0/8 ] Checking for PRD.md..." -ForegroundColor Yellow

$prdPath = Join-Path $PROJECT_ROOT "PRD.md"
if (-not (Test-Path $prdPath)) {
    Write-Host ""
    Write-Host "  FAIL  PRD.md not found at: $prdPath" -ForegroundColor Red
    Write-Host ""
    Write-Host "  You MUST create PRD.md before running this script." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  How to create PRD.md:" -ForegroundColor White
    Write-Host "    1. Open masterprompt.txt from your _gemini-setup folder" -ForegroundColor Cyan
    Write-Host "    2. Paste it into https://gemini.google.com (use Gemini 2.5 Pro)" -ForegroundColor Cyan
    Write-Host "    3. Answer all questions Gemini asks (7 sections)" -ForegroundColor Cyan
    Write-Host "    4. Copy the full output into PRD.md in this folder" -ForegroundColor Cyan
    Write-Host "    5. Re-run this script" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}
Write-Host "  OK  PRD.md found." -ForegroundColor Green

# -- 1. Folder structure -------------------------------------------------------
Write-Host ""
Write-Host "[ 1/8 ] Creating folder structure..." -ForegroundColor Yellow

$folders = @("tasks","docs","docs\plans","tests",".gemini\skills",".checkpoints") +
           ($MODULES | ForEach-Object { "app\$_" })
foreach ($f in $folders) {
    $path = Join-Path $PROJECT_ROOT $f
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path | Out-Null
        Write-Host "  OK  $f" -ForegroundColor Green
    } else {
        Write-Host "  .   $f (exists)" -ForegroundColor DarkGray
    }
}

# -- 2. GEMINI.md (project level) ----------------------------------------------
Write-Host ""
Write-Host "[ 2/8 ] Writing GEMINI.md..." -ForegroundColor Yellow

$moduleMap = ($MODULES | ForEach-Object { "  Session --> $_  : app\$_\ only" }) -join "`n"

$geminiMdContent = @"
# GEMINI.md -- $PROJECT_NAME
# Developer Edition -- Gemini CLI.
# Extends ~/.gemini/GEMINI.md global rules.

## Stack
$STACK

## Models
  Flash (fast/cheap)  : $FLASH
  Pro   (reasoning)   : $PRO

## Current Phase: $PHASE_CURRENT

## Module Boundaries
$moduleMap
  Session --> prd-read : reads PRD.md, creates all TASK-XXX stubs (ALWAYS FIRST)
  Session --> debug    : one error + one file per session

## Key Config
[Fill in: env vars, thresholds, IDs, API endpoints]

## Git
  main / dev / feature/TASK-XXX
  Format: [TASK-XXX] verb: what changed
"@

$geminiMdContent | Set-Content "$PROJECT_ROOT\GEMINI.md" -Encoding UTF8
Write-Host "  OK  GEMINI.md written. Fill in Key Config section." -ForegroundColor Green

# -- 3. TOOLS.md ---------------------------------------------------------------
Write-Host ""
Write-Host "[ 3/8 ] Writing TOOLS.md..." -ForegroundColor Yellow

@"
# TOOLS.md -- $PROJECT_NAME

## Models
  Pro   (real coding) : $PRO
  Flash (mechanical)  : $FLASH

## Extensions: superpowers (brainstorm/plan/execute)
## MCPs: filesystem, memory, sequential-thinking

## Session Launcher
  .\${PROJECT_NAME}-sessions.ps1 -Session list
  .\${PROJECT_NAME}-sessions.ps1 -Session prd-read     <-- ALWAYS run first

## Model switch inside gemini session
  /model gemini-2.5-pro
  /model gemini-2.0-flash

## Checkpoint / resume
  Checkpoints auto-written to .checkpoints\ckNN.md after each session.
  Next session auto-resumes from latest checkpoint.

## Test Commands
  [Fill in your test commands here]
"@ | Set-Content "$PROJECT_ROOT\TOOLS.md" -Encoding UTF8
Write-Host "  OK  TOOLS.md written." -ForegroundColor Green

# -- 4. SKILLS.md + skill files ------------------------------------------------
Write-Host ""
Write-Host "[ 4/8 ] Writing SKILLS.md + skill files..." -ForegroundColor Yellow

@"
# SKILLS.md -- $PROJECT_NAME

| Command      | File                            | What it does                  |
|--------------|---------------------------------|-------------------------------|
| task-create  | .gemini\skills\task-create.md   | Create a new TASK-XXX.md      |
| prd-parse    | .gemini\skills\prd-parse.md     | Read PRD, emit task stubs     |
"@ | Set-Content "$PROJECT_ROOT\SKILLS.md" -Encoding UTF8

@'
# Skill: task-create
1. Ask: task title + phase
2. Find next TASK number in tasks/
3. Create tasks/TASK-XXX-<slug>.md with PDCA template
4. Create branch: feature/TASK-XXX
5. Report path + branch
'@ | Set-Content "$PROJECT_ROOT\.gemini\skills\task-create.md" -Encoding UTF8

@'
# Skill: prd-parse
1. Read PRD.md in full using filesystem MCP
2. Identify all features, epics, and deliverables
3. For each deliverable create tasks/TASK-XXX-<slug>.md with:
   - Status: PLANNING
   - Phase from PRD
   - Objective from PRD feature description
   - Empty PDCA log
4. List all created task files
5. Do NOT write any code. This is planning only.
'@ | Set-Content "$PROJECT_ROOT\.gemini\skills\prd-parse.md" -Encoding UTF8
Write-Host "  OK  SKILLS.md + task-create + prd-parse written." -ForegroundColor Green

# -- 5. TASK-000 ---------------------------------------------------------------
Write-Host ""
Write-Host "[ 5/8 ] Creating TASK-000 (Repo Init)..." -ForegroundColor Yellow

@"
# TASK-000: Repo Init

## Status: PLANNING
## Phase: 0
## Objective
[What does done look like?]

## PDCA Log
### Cycle 1
**Plan:**
**Approved:** Pending
**Do:**
**Check:**
**Act:**

## Checkpoints
| Step | Status | Git Commit | Notes |
|------|--------|------------|-------|
"@ | Set-Content "$PROJECT_ROOT\tasks\TASK-000-repo-init.md" -Encoding UTF8
Write-Host "  OK  tasks/TASK-000-repo-init.md" -ForegroundColor Green

# -- 6. .gemini/settings.json (project scoped MCP) ----------------------------
Write-Host ""
Write-Host "[ 6/8 ] Writing .gemini/settings.json (project MCP scope)..." -ForegroundColor Yellow

$geminiProjDir = Join-Path $PROJECT_ROOT ".gemini"
if (-not (Test-Path $geminiProjDir)) { New-Item -ItemType Directory -Path $geminiProjDir | Out-Null }

$npmGlobalRoot = (npm root -g 2>$null).Trim()

$projSettings = @"
{
  "defaultModel": "gemini-2.5-pro",
  "mcpServers": {
    "filesystem": {
      "command": "node",
      "args": ["$npmGlobalRoot\\@modelcontextprotocol\\server-filesystem\\dist\\index.js", "$PROJECT_ROOT"],
      "trust": false
    },
    "memory": {
      "command": "node",
      "args": ["$npmGlobalRoot\\@modelcontextprotocol\\server-memory\\dist\\index.js"],
      "trust": false
    },
    "sequential-thinking": {
      "command": "node",
      "args": ["$npmGlobalRoot\\@modelcontextprotocol\\server-sequential-thinking\\dist\\index.js"],
      "trust": false
    }
  }
}
"@

$projSettings | Set-Content "$geminiProjDir\settings.json" -Encoding UTF8
Write-Host "  OK  .gemini/settings.json written." -ForegroundColor Green

# -- 7. Generate <project>-sessions.ps1 with all modules pre-filled -----------
Write-Host ""
Write-Host "[ 7/8 ] Generating ${PROJECT_NAME}-sessions.ps1..." -ForegroundColor Yellow

# Build the ValidateSet string from known session keys
$sessionKeys = @("prd-read", "debug") + $MODULES
$validateSet  = ($sessionKeys | ForEach-Object { "`"$_`"" }) -join ","

# Build one session block per module
$moduleSessionBlocks = ""
$taskNum = 1
foreach ($mod in $MODULES) {
    $taskId  = "TASK-" + $taskNum.ToString("D3")
    $model   = if ($taskNum % 2 -eq 0) { '$PRO' } else { '$FLASH' }   # alternate Flash/Pro; adjust as needed
    $taskNum++
    $moduleSessionBlocks += @"

    # --------------------------------------------------------------------------
    $mod = @{
        model = $model
        task  = "$taskId"
        label = "Session $($taskNum-1) -- $mod"
        prompt = @'
Stack: $STACK
Task file: tasks/$taskId-$mod.md
Module scope: app\$mod\ ONLY.

Key facts:
- [fill in key facts for $mod]

Use context7 for [library] API.
PDCA: present plan before touching any file.

END OF SESSION: When done, type exactly:
  SESSION-SUMMARY: <one paragraph -- what completed, decisions made, next task>
'@
    }
"@
}

$sessionsFileContent = @"
# ==============================================================================
# ${PROJECT_NAME}-sessions.ps1
# AUTO-GENERATED by g_setup_project_template.ps1 -- do not hand-edit header.
# Fill in: Key facts, library names, TASK slugs per module session.
# Owner: Srinivas / Fidelitus Corp
# Developer Edition -- Gemini CLI.
# ==============================================================================

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

# ==============================================================================
# HELPER -- find the latest checkpoint file (ckNN.md)
# ==============================================================================
function Get-LatestCheckpoint {
    if (-not (Test-Path `$CHECKPOINTS_DIR)) { return `$null }
    `$files = Get-ChildItem -Path `$CHECKPOINTS_DIR -Filter "ck*.md" -File |
             Sort-Object Name -Descending
    if (`$files.Count -eq 0) { return `$null }
    return `$files[0]
}

# ==============================================================================
# HELPER -- next checkpoint path  ck01.md, ck02.md ...
# ==============================================================================
function Get-NextCheckpointPath {
    if (-not (Test-Path `$CHECKPOINTS_DIR)) {
        New-Item -ItemType Directory -Path `$CHECKPOINTS_DIR | Out-Null
    }
    `$files = Get-ChildItem -Path `$CHECKPOINTS_DIR -Filter "ck*.md" -File
    `$next  = (`$files.Count + 1).ToString("D2")
    return Join-Path `$CHECKPOINTS_DIR "ck`$next.md"
}

# ==============================================================================
# HELPER -- write checkpoint after session
# ==============================================================================
function Write-Checkpoint {
    param([string]`$SessionKey, [string]`$TaskId, [string]`$Label)
    `$ckPath = Get-NextCheckpointPath
    `$ts     = Get-Date -Format "yyyy-MM-dd HH:mm"
    `$changed = git -C `$PROJECT_ROOT diff --name-only HEAD 2>`$null
    `$changedList = if (`$changed) { `$changed } else { "(run: git diff --name-only HEAD)" }
    `$content = @"
# Checkpoint -- `$Label
**Session :** `$SessionKey
**Task     :** `$TaskId
**Saved    :** `$ts

## What was completed this session
[Paste SESSION-SUMMARY from Gemini here]

## Files changed
`$changedList

## Decisions made
- [decision 1]

## Blockers / open items
- [none]

## Next session should start with
- Task  : [next task id]
- Focus : [one sentence]
"@
    `$content | Set-Content `$ckPath -Encoding UTF8
    Write-Host ""
    Write-Host "  CHECKPOINT  `$ckPath" -ForegroundColor Cyan
    Write-Host "  Paste Gemini SESSION-SUMMARY into the checkpoint file." -ForegroundColor DarkGray
}

# ==============================================================================
# HELPER -- git commit + push
# ==============================================================================
function Invoke-GitCommitPush {
    param([string]`$TaskId, [string]`$Label)
    Write-Host ""
    Write-Host "[ GIT ] Staging all changes..." -ForegroundColor Yellow
    git -C `$PROJECT_ROOT add -A 2>&1 | Out-Null
    `$status = git -C `$PROJECT_ROOT status --porcelain 2>`$null
    if (-not `$status) {
        Write-Host "  GIT  Nothing to commit. Working tree clean." -ForegroundColor DarkGray
        return
    }
    `$msg = "[`$TaskId] `$Label -- session end"
    git -C `$PROJECT_ROOT commit -m `$msg 2>&1 | ForEach-Object { Write-Host "  `$_" }
    `$branch = git -C `$PROJECT_ROOT rev-parse --abbrev-ref HEAD 2>`$null
    Write-Host ""
    Write-Host "[ GIT ] Pushing branch '`$branch' to origin..." -ForegroundColor Yellow
    `$pushResult = git -C `$PROJECT_ROOT push origin `$branch 2>&1
    `$pushResult | ForEach-Object { Write-Host "  `$_" }
    if (`$LASTEXITCODE -eq 0) {
        Write-Host "  OK  Pushed to origin/`$branch" -ForegroundColor Green
    } else {
        Write-Host "  WARN  Push failed -- check remote / auth." -ForegroundColor Red
    }
}

# ==============================================================================
# HELPER -- prepend latest checkpoint to prompt
# ==============================================================================
function Get-ResumeBlock {
    `$ck = Get-LatestCheckpoint
    if (`$null -eq `$ck) { return "" }
    `$ckContent = Get-Content `$ck.FullName -Raw
    return @"
======================================================
RESUME FROM CHECKPOINT: `$(`$ck.Name)
======================================================
`$ckContent
======================================================
Continue from the NEXT SESSION section above.
Do NOT repeat completed work. Ask if anything is unclear.
======================================================

"@
}

# ==============================================================================
# SESSION DEFINITIONS
# ==============================================================================
`$sessions = @{

    # -- ALWAYS THE FIRST SESSION ON ANY PROJECT --------------------------------
    "prd-read" = @{
        model = `$PRO
        task  = "TASK-000"
        label = "Session 0 -- PRD Read and Task Generation"
        prompt = @'
FIRST SESSION -- PRD READ AND TASK GENERATION
==============================================
Project : $PROJECT_NAME
Stack   : $STACK

Your ONLY job this session:
1. Use filesystem MCP to read PRD.md in full.
2. Run skill: prd-parse
3. Create one TASK-XXX-<slug>.md per deliverable in tasks/
4. List all created tasks (number + title).
5. Do NOT write any code. Planning only.

PDCA: Present task list BEFORE creating files. Wait for approval.

END OF SESSION: When done, type exactly:
  SESSION-SUMMARY: <one paragraph -- what completed, decisions made, next task>
'@
    }
$moduleSessionBlocks

    # -- DEBUG SESSION -- always Pro --------------------------------------------
    debug = @{
        model = `$PRO
        task  = "TASK-???"
        label = "Debug Session"
        prompt = @'
Project : $PROJECT_NAME
Stack   : $STACK
Task: one error, one file, one session.
Paste: (1) full traceback  (2) only the function that threw it.
Known gotchas: [list project-specific gotchas]

Think step by step. Do not touch any file outside the one that threw the error.

END OF SESSION: When done, type exactly:
  SESSION-SUMMARY: <one paragraph -- what completed, decisions made, next task>
'@
    }
}

# ==============================================================================
# LIST
# ==============================================================================
if (`$Session -eq "list") {
    Write-Host ""
    Write-Host "  Available sessions:" -ForegroundColor Magenta
    Write-Host ""
    foreach (`$key in `$sessions.Keys | Sort-Object) {
        `$s = `$sessions[`$key]
        if (`$s.model -like "*flash*") { `$tag = "Flash  (fast/cheap)" }
        else                           { `$tag = "Pro    (reasoning)"  }
        Write-Host ("  {0,-14}  {1,-40}  [{2}]" -f `$key, `$s.label, `$tag)
    }
    Write-Host ""
    `$ck = Get-LatestCheckpoint
    if (`$ck) {
        Write-Host "  Latest checkpoint: `$(`$ck.Name)  (`$(`$ck.LastWriteTime.ToString('yyyy-MM-dd HH:mm')))" -ForegroundColor Cyan
    } else {
        Write-Host "  No checkpoints yet." -ForegroundColor DarkGray
    }
    Write-Host ""
    exit 0
}

# ==============================================================================
# LAUNCH
# ==============================================================================
`$s = `$sessions[`$Session]
`$resumeBlock = Get-ResumeBlock
`$fullPrompt  = `$resumeBlock + `$s.prompt

Write-Host ""
Write-Host "  +----------------------------------------------+" -ForegroundColor Magenta
Write-Host ("  |  {0,-44}|" -f `$s.label) -ForegroundColor Magenta
Write-Host ("  |  Model : {0,-37}|" -f `$s.model) -ForegroundColor Magenta
Write-Host ("  |  Task  : {0,-37}|" -f `$s.task) -ForegroundColor Magenta
if (`$resumeBlock) {
Write-Host "  |  RESUME: checkpoint injected into prompt      |" -ForegroundColor Cyan
}
Write-Host "  +----------------------------------------------+" -ForegroundColor Magenta
Write-Host ""
Write-Host `$fullPrompt -ForegroundColor White
Write-Host ""
`$fullPrompt | Set-Clipboard
Write-Host "  OK  Prompt copied to clipboard." -ForegroundColor Green
Write-Host "  Paste into gemini when it opens, then: superpowers brainstorm" -ForegroundColor Cyan
Write-Host ""

Set-Location `$PROJECT_ROOT
gemini --model `$s.model

# ==============================================================================
# POST-SESSION
# ==============================================================================
Write-Host ""
Write-Host "  Gemini session ended." -ForegroundColor Yellow
Write-Host ""

Write-Checkpoint -SessionKey `$Session -TaskId `$s.task -Label `$s.label

`$doGit = Read-Host "  Commit and push to GitHub? [Y/n]"
if (`$doGit -ne "n" -and `$doGit -ne "N") {
    Invoke-GitCommitPush -TaskId `$s.task -Label `$s.label
}

Write-Host ""
Write-Host "  Done. Next run will resume from the checkpoint above." -ForegroundColor Green
Write-Host ""
"@

$sessionsFilePath = Join-Path $PROJECT_ROOT "${PROJECT_NAME}-sessions.ps1"
$sessionsFileContent | Set-Content $sessionsFilePath -Encoding UTF8
Write-Host "  OK  ${PROJECT_NAME}-sessions.ps1 written." -ForegroundColor Green
Write-Host "  Edit: fill in Key facts and TASK slugs per module session." -ForegroundColor DarkGray

# -- 8. PRD-read session prompt + launch ---------------------------------------
Write-Host ""
Write-Host "[ 8/8 ] Preparing PRD-read session prompt..." -ForegroundColor Yellow

$prdContent = Get-Content $prdPath -Raw

$prdReadPrompt = @"
FIRST SESSION -- PRD READ AND TASK GENERATION
==============================================
Project : $PROJECT_NAME
Stack   : $STACK

Your ONLY job this session:
1. Read the PRD.md content below completely.
2. Run skill: prd-parse
3. Create one TASK-XXX-<slug>.md per deliverable in tasks/
4. List all created tasks with their numbers and titles.
5. Do NOT write any code. Planning only.

PDCA: Present the list of tasks you plan to create BEFORE creating them.
Wait for my approval. Then create them.

END OF SESSION: When done, type exactly:
  SESSION-SUMMARY: <one paragraph -- what completed, decisions made, next task>

--- PRD.md ---
$prdContent
--- END PRD.md ---
"@

$prdReadPrompt | Set-Clipboard
Write-Host "  OK  PRD-read session prompt copied to clipboard." -ForegroundColor Green

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  OK  $PROJECT_NAME bootstrap complete." -ForegroundColor Green
Write-Host ""
Write-Host "  Files created:" -ForegroundColor White
Write-Host "    GEMINI.md, TOOLS.md, SKILLS.md" -ForegroundColor DarkGray
Write-Host "    tasks\TASK-000-repo-init.md" -ForegroundColor DarkGray
Write-Host "    .gemini\settings.json" -ForegroundColor DarkGray
Write-Host "    .checkpoints\ (folder)" -ForegroundColor DarkGray
Write-Host "    ${PROJECT_NAME}-sessions.ps1  <-- your session launcher" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "    1. Edit ${PROJECT_NAME}-sessions.ps1 -- fill Key facts per module" -ForegroundColor Cyan
Write-Host "    2. Gemini is launching now -- paste clipboard to start PRD read" -ForegroundColor Cyan
Write-Host "    3. After that: .\\${PROJECT_NAME}-sessions.ps1 -Session list" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""

Set-Location $PROJECT_ROOT
gemini --model $PRO
