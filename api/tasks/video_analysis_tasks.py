import os
import logging
from datetime import datetime
from celery_app import celery
from utils.client_utils import get_db
from utils.video_analysis_utils import analyze_video_resume as run_gemini_analysis

logger = logging.getLogger(__name__)

@celery.task(name="tasks.video_analysis_tasks.analyze_video_resume")
def analyze_video_resume(candidate_id: str, jd_id: str, video_path: str):
    """
    Analyze video resume and extract traits
    Triggered after form submission with video
    """
    logger.info(f"Starting video analysis for {candidate_id} - JD: {jd_id}")
    db = get_db()

    try:
        # Check if video file exists
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            db.form_responses.update_one(
                {"jd_id": jd_id, "candidate_id": candidate_id},
                {"$set": {
                    "video_analysis": {
                        "status": "failed",
                        "error": "Video file not found",
                        "analyzed_at": datetime.utcnow()
                    },
                    "updated_at": datetime.utcnow()
                }}
            )
            return {"status": "failed", "error": "Video file not found"}

        # Analyze video
        analysis_result = run_gemini_analysis(video_path)

        if "error" in analysis_result:
            logger.error(f"Video analysis failed: {analysis_result['error']}")
            db.form_responses.update_one(
                {"jd_id": jd_id, "candidate_id": candidate_id},
                {"$set": {
                    "video_analysis": {
                        "status": "failed",
                        "error": analysis_result["error"],
                        "analyzed_at": datetime.utcnow()
                    },
                    "updated_at": datetime.utcnow()
                }}
            )
            return {"status": "failed", "error": analysis_result["error"]}

        # Store analysis results
        analysis_result["status"] = "completed"
        analysis_result["analyzed_at"] = datetime.utcnow()

        db.form_responses.update_one(
            {"jd_id": jd_id, "candidate_id": candidate_id},
            {"$set": {
                "video_analysis": analysis_result,
                "updated_at": datetime.utcnow()
            }}
        )

        # Update candidate profile with video analysis traits
        db.candidates.update_one(
            {"candidate_id": candidate_id},
            {"$set": {
                "video_resume_traits": analysis_result.get("traits", []),
                "updated_at": datetime.utcnow()
            }}
        )

        logger.info(f"Video analysis complete for {candidate_id}: {analysis_result.get('traits', [])}")

        return {
            "status": "completed",
            "traits": analysis_result.get("traits", []),
            "overall_impression": analysis_result.get("overall_impression", ""),
            "scores": {
                "confidence": analysis_result.get("confidence_score", 0),
                "articulation": analysis_result.get("articulation_score", 0),
                "eye_contact": analysis_result.get("eye_contact_score", 0),
                "professionalism": analysis_result.get("professionalism_score", 0),
            }
        }

    except Exception as e:
        logger.error(f"Video analysis task failed: {e}")
        db.form_responses.update_one(
            {"jd_id": jd_id, "candidate_id": candidate_id},
            {"$set": {
                "video_analysis": {
                    "status": "failed",
                    "error": str(e),
                    "analyzed_at": datetime.utcnow()
                },
                "updated_at": datetime.utcnow()
            }}
        )
        return {"status": "failed", "error": str(e)}
