# ==============================================================================
# g_setup_generic.ps1
# One-time machine bootstrap — Gemini CLI Developer Edition.
# Owner: Srinivas / Fidelitus Corp
# Run once per machine. Safe to re-run.
# Mirrors: setup-generic.ps1 (Claude Code edition)
# ==============================================================================

Write-Host ""
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host "  GEMINI CLI -- GENERIC MACHINE BOOTSTRAP" -ForegroundColor Magenta
Write-Host "  Developer Edition. Run once per machine. Safe to re-run." -ForegroundColor Magenta
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host ""

# -- 1. Prerequisites ----------------------------------------------------------
Write-Host "[ 1/7 ] Checking prerequisites..." -ForegroundColor Yellow

$missing = @()
if (-not (Get-Command node  -ErrorAction SilentlyContinue)) { $missing += "Node.js  --> https://nodejs.org (use LTS)" }
if (-not (Get-Command npm   -ErrorAction SilentlyContinue)) { $missing += "npm      --> comes with Node.js" }
if (-not (Get-Command git   -ErrorAction SilentlyContinue)) { $missing += "Git      --> https://git-scm.com" }
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { $missing += "Python   --> https://python.org (check Add to PATH)" }

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "  FAIL  Missing prerequisites:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "  Install the above then re-run this script." -ForegroundColor Yellow
    exit 1
}
Write-Host "  OK  Node, npm, Git, Python all present." -ForegroundColor Green

# -- 2. Install Gemini CLI -----------------------------------------------------
Write-Host ""
Write-Host "[ 2/7 ] Installing Gemini CLI..." -ForegroundColor Yellow
Write-Host "  Package: @google/gemini-cli" -ForegroundColor DarkGray

npm install -g @google/gemini-cli 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK  Gemini CLI installed." -ForegroundColor Green
} else {
    Write-Host "  FAIL  npm install failed. Try running PowerShell as Administrator." -ForegroundColor Red
    exit 1
}

$geminiCmd = Get-Command gemini -ErrorAction SilentlyContinue
if ($geminiCmd) {
    Write-Host "  OK  gemini command found at: $($geminiCmd.Source)" -ForegroundColor Green
} else {
    Write-Host "  WARN  gemini command not found in PATH yet." -ForegroundColor Yellow
    Write-Host "  Close and reopen PowerShell then re-run this script." -ForegroundColor Yellow
    exit 1
}

# -- 3. Gemini API key ---------------------------------------------------------
Write-Host ""
Write-Host "[ 3/7 ] Checking Gemini API key..." -ForegroundColor Yellow
Write-Host "  For Pro plan: get key at https://aistudio.google.com/app/apikey" -ForegroundColor DarkGray

if (-not $env:GEMINI_API_KEY) {
    Write-Host ""
    Write-Host "  WARN  GEMINI_API_KEY not set." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  To fix (run this, then restart PowerShell):" -ForegroundColor White
    Write-Host "  [System.Environment]::SetEnvironmentVariable('GEMINI_API_KEY','YOUR_KEY','User')" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Continuing setup -- gemini will prompt for auth on first run." -ForegroundColor DarkGray
} else {
    $tail = $env:GEMINI_API_KEY.Substring([Math]::Max(0, $env:GEMINI_API_KEY.Length - 6))
    Write-Host "  OK  GEMINI_API_KEY present (ending: ...$tail)" -ForegroundColor Green
}

# -- 4. MCP servers ------------------------------------------------------------
Write-Host ""
Write-Host "[ 4/7 ] Installing global MCP servers..." -ForegroundColor Yellow
Write-Host "  Same MCP servers work with Gemini CLI." -ForegroundColor DarkGray

$mcpPackages = @(
    "@modelcontextprotocol/server-filesystem",
    "@modelcontextprotocol/server-memory",
    "@modelcontextprotocol/server-sequential-thinking"
)

foreach ($pkg in $mcpPackages) {
    Write-Host "  --> $pkg" -ForegroundColor DarkGray
    npm install -g $pkg 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Host "    OK" -ForegroundColor Green }
    else { Write-Host "    FAIL  run manually: npm install -g $pkg" -ForegroundColor Red }
}

# -- 5. Write ~/.gemini/settings.json ------------------------------------------
Write-Host ""
Write-Host "[ 5/7 ] Writing ~/.gemini/settings.json..." -ForegroundColor Yellow

$geminiDir = "$env:USERPROFILE\.gemini"
if (-not (Test-Path $geminiDir)) { New-Item -ItemType Directory -Path $geminiDir | Out-Null }

$npmGlobalRoot = (npm root -g 2>$null).Trim()

$settingsJson = @"
{
  "defaultModel": "gemini-2.5-pro",
  "autoAccept": false,
  "theme": "Default",
  "mcpServers": {
    "filesystem": {
      "command": "node",
      "args": ["$npmGlobalRoot\\@modelcontextprotocol\\server-filesystem\\dist\\index.js", "C:\\"],
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

$settingsJson | Set-Content "$geminiDir\settings.json" -Encoding UTF8
Write-Host "  OK  Written: $geminiDir\settings.json" -ForegroundColor Green

# -- 6. Write global GEMINI.md -------------------------------------------------
Write-Host ""
Write-Host "[ 6/7 ] Writing ~/.gemini/GEMINI.md (global rules)..." -ForegroundColor Yellow

$geminiMd = @'
# GEMINI.md -- Global Rules (All Projects)
# Owner: Srinivas / Fidelitus Corp
# Developer Edition -- Gemini CLI with Pro plan.
# Project GEMINI.md extends these. Never contradicts them.

## Model Tiers

| Task                                          | Model               |
|-----------------------------------------------|---------------------|
| Boilerplate, config, CRUD, JSON, renaming     | gemini-2.0-flash    |
| Real coding, APIs, debugging, Docker, docs    | gemini-2.5-pro      |
| Failed twice on 2.5-pro, hard architecture    | gemini-2.5-pro (*)  |

(*) Last resort: add "Think step by step, this is architecturally complex." to prompt.

Default = gemini-2.5-pro. Flash only for pure mechanical tasks.
Never type model names manually -- always use the session launcher.

## How to Switch Models in Session

  /model gemini-2.5-pro
  /model gemini-2.0-flash

## Context Window (CRITICAL)

- Watch token count -- hard limit is 50 percent of context.
- At 50 percent: finish current unit, /chat save mysession, start new session.
- One session = one module = one file scope.
- NEVER let context bloat. Use filesystem MCP to read files, not paste.

## Superpowers Workflow

Install superpowers extension (done by g_setup_generic.ps1).
Every session starts with: superpowers brainstorm

1. superpowers brainstorm   --> clarify, approaches, spec doc
2. superpowers write plan   --> spec to implementation plan
3. superpowers execute plan --> execute in isolated context

## Tool Policy

| Tool                | When                                              |
|---------------------|---------------------------------------------------|
| context7            | Any library/API -- prevents hallucinated calls    |
| sequential-thinking | Architecture, complex debugging                   |
| memory MCP          | Persist decisions, schema, open questions         |
| filesystem MCP      | Read files -- never paste entire files into chat  |

## PDCA

Plan --> present --> approval --> Do --> Check --> Act (commit or re-plan).
No scope creep. Every deviation = stop + re-plan.

## Git

- Never commit to main.
- Format: [TASK-XXX] verb: what changed
- Show diff before every commit.

## Paste Discipline

Paste only the function relevant to the task.
Use filesystem MCP for full files.

## Refactor Projects

Read before writing. Always audit first. Never rewrite what works.

## First Session Rule (ALL Projects)

Every new project starts with a PRD-read session.
Session launcher auto-reads PRD.md and generates task files.
Do NOT skip this. Do NOT write code before tasks exist.
'@

$geminiMd | Set-Content "$geminiDir\GEMINI.md" -Encoding UTF8
Write-Host "  OK  Written: $geminiDir\GEMINI.md" -ForegroundColor Green

# -- 7. Install superpowers extension ------------------------------------------
Write-Host ""
Write-Host "[ 7/7 ] Installing superpowers extension for Gemini CLI..." -ForegroundColor Yellow
Write-Host "  This gives brainstorm / write plan / execute plan workflow." -ForegroundColor DarkGray

gemini extensions install https://github.com/obra/superpowers 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  OK  superpowers installed." -ForegroundColor Green
} else {
    Write-Host "  WARN  superpowers install may need manual step." -ForegroundColor Yellow
    Write-Host "  Run inside gemini: /extensions install https://github.com/obra/superpowers" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host "  MANUAL STEPS (do these after this script)" -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "  1. Set your Gemini API key permanently (if not already done):" -ForegroundColor White
Write-Host "     [System.Environment]::SetEnvironmentVariable('GEMINI_API_KEY','YOUR_KEY','User')" -ForegroundColor Cyan
Write-Host ""
Write-Host "  2. Verify gemini works:" -ForegroundColor White
Write-Host "     gemini -p ""reply with: gemini ok""" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. Verify superpowers loaded -- inside gemini type:" -ForegroundColor White
Write-Host "     superpowers brainstorm" -ForegroundColor Cyan
Write-Host ""
Write-Host "  4. Warp terminal (recommended):" -ForegroundColor White
Write-Host "     https://warp.dev" -ForegroundColor Cyan
Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "  OK  Bootstrap complete." -ForegroundColor Green
Write-Host "  Next: read DEVELOPER-SETUP.txt for full onboarding steps." -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""
