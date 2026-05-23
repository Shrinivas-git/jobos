import os
import logging
from datetime import datetime, timezone
from time import time
from collections import defaultdict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from celery_app import celery
from routers import auth, candidates, jd, matching, pipeline, documents, crm, analytics, notifications, feedback, recruiter_tasks, admin, assessments, invoices, forms, indeed, linkedin, publish
from middleware.audit import AuditMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="JobOS API", version="2.0")

# ── Rate limiting (in-memory sliding window, 100 req/min per IP) ─────────────
_rl_hits: dict = defaultdict(list)
_RL_CALLS = int(os.getenv("RATE_LIMIT_CALLS", "100"))
_RL_PERIOD = int(os.getenv("RATE_LIMIT_PERIOD", "60"))
_RL_SKIP = {"/health", "/docs", "/openapi.json", "/redoc"}

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _RL_SKIP:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time()
        window_start = now - _RL_PERIOD

        hits = [t for t in _rl_hits[client_ip] if t > window_start]
        if len(hits) >= _RL_CALLS:
            return JSONResponse({"detail": "Rate limit exceeded. Try again later."}, status_code=429)
        hits.append(now)
        _rl_hits[client_ip] = hits

        return await call_next(request)


# ── Security headers ──────────────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none';"
        )
        return response


# Middleware order: outermost first (last added = outermost)
app.add_middleware(AuditMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(candidates.router)
app.include_router(jd.router)
app.include_router(matching.router)
app.include_router(pipeline.router)
app.include_router(documents.router)
app.include_router(crm.router)
app.include_router(analytics.router)
app.include_router(notifications.router)
app.include_router(feedback.router)
app.include_router(recruiter_tasks.router)
app.include_router(admin.router)
app.include_router(assessments.router)
app.include_router(invoices.router)
app.include_router(forms.router)
app.include_router(indeed.router)
app.include_router(linkedin.router)
app.include_router(publish.router)


@app.get("/")
async def root():
    return {"message": "JobOS API v2.0 is running", "status": "online"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
