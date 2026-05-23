import logging
from datetime import datetime, timedelta
from celery_app import celery
from utils.client_utils import get_db
from utils.email_utils import send_email
from utils.telegram_utils import send_telegram_message, format_reminder_message, notify_recruiter, TELEGRAM_ENABLED

logger = logging.getLogger(__name__)

# Stage configurations with templates
STAGE_CONFIG = {
    "form": {
        "label": "Form Submission",
        "templates": {
            1: "📋 <b>Reminder #1 of 5</b><br>Please fill and submit the candidate form with video resume.<br>Visit: [FORM_LINK]",
            2: "📋 <b>Reminder #2 of 5</b><br>Form still pending. Please submit soon to proceed with shortlisting.",
            3: "📋 <b>Reminder #3 of 5</b><br>Urgent: Form deadline approaching. Please submit immediately.",
            4: "📋 <b>Reminder #4 of 5</b><br>Critical: Form submission required to continue pipeline.",
            5: "📋 <b>Final Reminder #5 of 5</b><br>🚨 Please submit form immediately to avoid delays.",
        }
    },
    "interview": {
        "label": "Interview Confirmation",
        "templates": {
            1: "🎯 <b>Reminder #1 of 5</b><br>Please confirm your availability for the interview scheduled on [DATE].",
            2: "🎯 <b>Reminder #2 of 5</b><br>Interview confirmation pending. Please respond at your earliest convenience.",
            3: "🎯 <b>Reminder #3 of 5</b><br>Urgent: Interview confirmation needed. Please confirm availability.",
            4: "🎯 <b>Reminder #4 of 5</b><br>Critical: Interview confirmation required. Please respond immediately.",
            5: "🎯 <b>Final Reminder #5 of 5</b><br>🚨 Interview confirmation deadline. Please confirm or reschedule now.",
        }
    },
    "interest": {
        "label": "Interest & Joining Date",
        "templates": {
            1: "💼 <b>Reminder #1 of 5</b><br>Please confirm your interest in the role and preferred joining date.",
            2: "💼 <b>Reminder #2 of 5</b><br>Interest confirmation pending. Please provide your response.",
            3: "💼 <b>Reminder #3 of 5</b><br>Urgent: Please confirm interest and joining date preference.",
            4: "💼 <b>Reminder #4 of 5</b><br>Critical: Interest confirmation required to proceed.",
            5: "💼 <b>Final Reminder #5 of 5</b><br>🚨 Please confirm interest and joining date immediately.",
        }
    },
    "offer": {
        "label": "Offer Acceptance",
        "templates": {
            1: "🎉 <b>Reminder #1 of 5</b><br>Please review the offer details and respond with your decision.",
            2: "🎉 <b>Reminder #2 of 5</b><br>Offer awaiting your response. Please confirm acceptance or discuss modifications.",
            3: "🎉 <b>Reminder #3 of 5</b><br>Urgent: Offer decision pending. Please respond soon.",
            4: "🎉 <b>Reminder #4 of 5</b><br>Critical: Offer expiration approaching. Please respond immediately.",
            5: "🎉 <b>Final Reminder #5 of 5</b><br>🚨 Offer decision required immediately.",
        }
    },
    "client": {
        "label": "Client Decision",
        "templates": {
            1: "✓ <b>Reminder #1 of 5</b><br>Please review the candidate profile and provide your decision (Shortlist/Interview/Reject/Offer).",
            2: "✓ <b>Reminder #2 of 5</b><br>Client decision pending. Please review candidate details and respond.",
            3: "✓ <b>Reminder #3 of 5</b><br>Urgent: Client decision needed. Please review and provide feedback.",
            4: "✓ <b>Reminder #4 of 5</b><br>Critical: Client decision required. Please respond.",
            5: "✓ <b>Final Reminder #5 of 5</b><br>🚨 Client decision deadline. Please respond immediately.",
        }
    }
}

def _get_html_email_template(stage: str, reminder_number: int, recipient_name: str) -> tuple:
    """Get HTML email template for reminder"""
    stage_info = STAGE_CONFIG.get(stage, {})
    subject = f"Reminder #{reminder_number}: {stage_info.get('label', stage)} - {recipient_name}"

    template = stage_info.get("templates", {}).get(reminder_number, f"Please respond to {stage} request")

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #e2e8f0;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background-color: #1e293b; border-radius: 12px; padding: 24px; border: 1px solid #334155;">
            <h2 style="color: #60a5fa; margin-top: 0;">{subject}</h2>
            <p style="font-size: 14px; line-height: 1.6;">{template}</p>
            <p style="font-size: 12px; color: #94a3b8; margin-top: 24px;">
                Reminder {reminder_number} of 5
            </p>
        </div>
        <p style="text-align: center; color: #64748b; font-size: 11px; margin-top: 16px;">
            JobOS Recruitment System
        </p>
    </div>
    </body>
    </html>
    """

    return subject, html

@celery.task(name="tasks.reminder_tasks.process_pending_responses")
def process_pending_responses():
    """
    Runs 2x per day (9am + 5pm UTC)
    Checks all stages with pending responses and sends reminders
    """
    logger.info("Starting pending response reminder task")
    db = get_db()

    total_reminders_sent = 0

    try:
        # Get all pipeline stages with pending form submissions
        pending_forms = list(db.pipeline_stages.find({
            "response_tracking.form_submitted.status": "pending"
        }))

        for doc in pending_forms:
            result = _process_pending_stage(db, doc, "form_submitted", "form", "candidate_id")
            total_reminders_sent += result

        # Process pending interview confirmations
        pending_interviews = list(db.pipeline_stages.find({
            "response_tracking.interview_availability.status": "pending"
        }))

        for doc in pending_interviews:
            result = _process_pending_stage(db, doc, "interview_availability", "interview", "candidate_id")
            total_reminders_sent += result

        # Process pending interest confirmations
        pending_interest = list(db.pipeline_stages.find({
            "response_tracking.interest_confirmation.status": "pending"
        }))

        for doc in pending_interest:
            result = _process_pending_stage(db, doc, "interest_confirmation", "interest", "candidate_id")
            total_reminders_sent += result

        # Process pending offer responses
        pending_offers = list(db.pipeline_stages.find({
            "response_tracking.offer_acceptance.status": "pending"
        }))

        for doc in pending_offers:
            result = _process_pending_stage(db, doc, "offer_acceptance", "offer", "candidate_id")
            total_reminders_sent += result

        # Process pending client decisions
        pending_client = list(db.pipeline_stages.find({
            "response_tracking.client_feedback.status": "pending"
        }))

        for doc in pending_client:
            result = _process_pending_stage(db, doc, "client_feedback", "client", "client_email")
            total_reminders_sent += result

        logger.info(f"Reminder task complete. Sent {total_reminders_sent} reminders")
        return {"status": "completed", "reminders_sent": total_reminders_sent}

    except Exception as e:
        logger.error(f"Reminder task failed: {e}")
        return {"status": "failed", "error": str(e)}

def _process_pending_stage(db, pipeline_doc: dict, stage_key: str, stage_name: str, recipient_id_field: str) -> int:
    """
    Process a single pending stage and send reminders if needed
    Returns: Number of reminders sent (0 or 1)
    """
    try:
        stage_tracking = pipeline_doc.get("response_tracking", {}).get(stage_key, {})
        reminder_count = stage_tracking.get("reminder_count", 0)

        # Check if max reminders reached
        if reminder_count >= 5:
            return 0

        # Check if already reminded today (2x daily limit)
        last_reminder = stage_tracking.get("last_reminder_at")
        if last_reminder and _already_reminded_today(last_reminder):
            return 0

        # Get recipient (candidate or client)
        recipient = None
        recipient_email = None
        recipient_name = None

        if recipient_id_field == "candidate_id":
            candidate = db.candidates.find_one({"candidate_id": pipeline_doc.get("candidate_id")})
            if candidate:
                recipient_email = candidate.get("email")
                recipient_name = candidate.get("name", pipeline_doc.get("candidate_id"))
                recipient_telegram_id = candidate.get("telegram_handle")
        else:  # client_email
            jd = db.job_descriptions.find_one({"jd_id": pipeline_doc.get("jd_id")})
            if jd:
                recipient_email = jd.get("client_email")
                recipient_name = jd.get("title", "Client")
                recipient_telegram_id = None

        if not recipient_email:
            logger.warning(f"No recipient email found for {stage_name} reminder")
            return 0

        # Send reminder
        next_reminder_number = reminder_count + 1
        subject, html_body = _get_html_email_template(stage_name, next_reminder_number, recipient_name)

        # Send email
        email_sent = send_email(recipient_email, subject, html_body)

        # Send Telegram to candidate (if they have a handle) and always to recruiter
        telegram_sent = False
        if TELEGRAM_ENABLED:
            reminder_msg = format_reminder_message(
                next_reminder_number,
                stage_name,
                recipient_name,
                {"due_date": "ASAP"}
            )
            # Candidate Telegram (if available)
            if recipient_id_field == "candidate_id" and recipient_telegram_id:
                telegram_sent = send_telegram_message(recipient_telegram_id, reminder_msg)

            # Always notify recruiter
            jd_id = pipeline_doc.get("jd_id", "")
            recruiter_msg = (
                f"🔔 <b>Reminder #{next_reminder_number} sent</b>\n"
                f"<b>Candidate:</b> {recipient_name}\n"
                f"<b>Stage:</b> {stage_name}\n"
                f"<b>JD:</b> {jd_id}"
            )
            notify_recruiter(recruiter_msg)

        # Update tracking
        db.pipeline_stages.update_one(
            {"_id": pipeline_doc.get("_id")},
            {"$set": {
                f"response_tracking.{stage_key}.reminder_count": next_reminder_number,
                f"response_tracking.{stage_key}.last_reminder_at": datetime.utcnow()
            }}
        )

        # Log reminder
        db.reminder_log.insert_one({
            "jd_id": pipeline_doc.get("jd_id"),
            "candidate_id": pipeline_doc.get("candidate_id"),
            "stage": stage_name,
            "reminder_number": next_reminder_number,
            "recipient_type": "candidate" if recipient_id_field == "candidate_id" else "client",
            "recipient_email": recipient_email,
            "channels_sent": ["email"] + (["telegram"] if telegram_sent else []),
            "sent_at": datetime.utcnow(),
            "response_received": False
        })

        logger.info(f"Reminder #{next_reminder_number} sent for {stage_name}: {recipient_email}")
        return 1

    except Exception as e:
        logger.error(f"Error processing {stage_name} reminder: {e}")
        return 0

def _already_reminded_today(last_reminder_dt) -> bool:
    """Check if reminder was sent less than 12 hours ago (2x daily max)"""
    if not last_reminder_dt:
        return False

    hours_since = (datetime.utcnow() - last_reminder_dt).total_seconds() / 3600
    return hours_since < 12  # Only one reminder per 12 hours (2x daily max)
