# TASK-016 — Why-Not-Selected Engine

## Goal
When a candidate is rejected, Groq generates constructive feedback explaining why.
Candidates receive this as a weekly email digest.

## Scope
- Trigger: when recruiter clicks Reject in RecruiterDashboard
- Groq generates 3-5 sentence feedback based on JD requirements vs candidate profile
- Store feedback in MongoDB candidate_feedback collection
- Weekly Celery Beat task sends digest email to candidate email address

## API Endpoints needed
- POST /feedback/generate/{candidate_id}/{jd_id} — generate and store feedback
- GET /feedback/{candidate_id} — get all feedback for a candidate

## Files to touch
- api/tasks/feedback_tasks.py (new)
- api/routers/feedback.py (new)
- api/main.py (register router)
- api/celery_app.py (add weekly beat task)
- api/utils/gemini_utils.py (add generate_rejection_feedback function)
- api/tasks/matching_tasks.py (trigger feedback on reject action)
