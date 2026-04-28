# CLAUDE.md - jobos
# Extends ~/.claude/CLAUDE.md

## Stack
Python 3.13, FastAPI, PostgreSQL, Qdrant, Docker, Groq API

## Current Phase: 1

## Module Boundaries
  jd-intake        -> api/routers/jobs.py, api/tasks/jd_tasks.py
  resume-ingestion -> api/routers/candidates.py, api/utils/gemini_utils.py
  matching         -> api/routers/matching.py
  auth             -> api/routers/auth.py
  debug            -> one error + one file per session only

## Key Config
  GROQ_API_KEY     -> in .env (replace anthropic key)
  FAST_MODEL       -> llama-3.1-8b-instant
  REASON_MODEL     -> llama-3.3-70b-versatile
  DB               -> PostgreSQL via docker-compose
  VECTOR_DB        -> Qdrant

## Completed Tasks
  TASK-000 to TASK-008 done (infra, auth, DB, frontend, JD, resume, matching P1+P2)

## Current Task
  TASK-009: Switch AI from Gemini to Groq, fix resume metadata extraction

## Git
  main / dev / feature/TASK-XXX
  Format: [TASK-XXX] verb: what changed
