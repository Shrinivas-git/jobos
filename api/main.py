import os
import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from celery_app import celery
from routers import auth, candidates, jd, matching, pipeline, documents, crm, analytics, notifications, feedback

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="JobOS API", version="2.0")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
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

@app.get("/")
async def root():
    return {"message": "JobOS API v2.0 is running", "status": "online"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
