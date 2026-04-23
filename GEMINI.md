# GEMINI.md -- jobos
# Developer Edition -- Gemini CLI V4.

## Stack
Python, FastAPI, React, MongoDB, Qdrant, Docker, Gemini API

## Models
  Flash : gemini-2.0-flash
  Pro   : gemini-2.5-pro

## Current Phase: 1

## Module Boundaries
  Session --> api  : api\ only
  Session --> frontend  : frontend\ only
  Session --> email-watcher  : email-watcher\ only
  Session --> naukri-sourcer  : naukri-sourcer\ only
  Session --> prd-read : reads PRD.md, creates all TASK-XXX stubs (ALWAYS FIRST)
  Session --> debug    : one error + one file per session

## Git
  Format: [TASK-XXX] verb: what changed
