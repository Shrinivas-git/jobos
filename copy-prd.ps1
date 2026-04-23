$prdContent = Get-Content "C:\staging\jobos\PRD.md" -Raw
$prompt = @"
FIRST SESSION -- PRD READ AND TASK GENERATION
==============================================
Project : jobos
Stack   : React, FastAPI, MongoDB, Qdrant, Keycloak, Docker, Gemini API, AWS

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
$prompt | Set-Clipboard
Write-Host "Copied to clipboard"