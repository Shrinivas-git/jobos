# ==============================================================================
# g_setup_project_template.ps1
# Copy this, rename setup-<project>.ps1, fill the 5 variables.
# PRD.md MUST exist in PROJECT_ROOT before running.
# Owner: Srinivas / Fidelitus Corp
# Developer Edition -- Gemini CLI.
# Mirrors: setup-project-template.ps1 (Claude Code edition)
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
Write-Host "[ 0/7 ] Checking for PRD.md..." -ForegroundColor Yellow

$prdPath = Join-Path $PROJECT_ROOT "PRD.md"
if (-not (Test-Path $prdPath)) {
    Write-Host ""
    Write-Host "  FAIL  PRD.md not found at: $prdPath" -ForegroundColor Red
    Write-Host ""
    Write-Host "  You MUST create PRD.md before running this script." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  How to create PRD.md:" -ForegroundColor White
    Write-Host "    1. Open masterprompt.txt from your _claude-setup folder" -ForegroundColor Cyan
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
Write-Host "[ 1/7 ] Creating folder structure..." -ForegroundColor Yellow

$folders = @("tasks","docs","docs\plans","tests",".gemini\skills") + ($MODULES | ForEach-Object { "app\$_" })
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
Write-Host "[ 2/7 ] Writing GEMINI.md..." -ForegroundColor Yellow

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
Write-Host "[ 3/7 ] Writing TOOLS.md..." -ForegroundColor Yellow

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

## Save and resume session
  /chat save <name>
  /chat resume <name>

## Test Commands
  [Fill in your test commands here]
"@ | Set-Content "$PROJECT_ROOT\TOOLS.md" -Encoding UTF8
Write-Host "  OK  TOOLS.md written." -ForegroundColor Green

# -- 4. SKILLS.md + skill files ------------------------------------------------
Write-Host ""
Write-Host "[ 4/7 ] Writing SKILLS.md + skill files..." -ForegroundColor Yellow

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
Write-Host "[ 5/7 ] Creating TASK-000 (Repo Init)..." -ForegroundColor Yellow

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
Write-Host "[ 6/7 ] Writing .gemini/settings.json (project MCP scope)..." -ForegroundColor Yellow

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

# -- 7. PRD-read session prompt ------------------------------------------------
Write-Host ""
Write-Host "[ 7/7 ] Preparing PRD-read session prompt..." -ForegroundColor Yellow

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

--- PRD.md ---
$prdContent
--- END PRD.md ---
"@

$prdReadPrompt | Set-Clipboard
Write-Host "  OK  PRD-read session prompt copied to clipboard." -ForegroundColor Green

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  OK  $PROJECT_NAME bootstrap complete." -ForegroundColor Green
Write-Host "  Launching gemini now with gemini-2.5-pro..." -ForegroundColor Cyan
Write-Host "  Paste clipboard when gemini opens." -ForegroundColor Cyan
Write-Host "  Then type: superpowers brainstorm" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""

Set-Location $PROJECT_ROOT
gemini --model $PRO
