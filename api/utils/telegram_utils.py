import os
import logging
import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN)

def send_telegram_message(chat_id: str, message: str) -> bool:
    """
    Send a text message via Telegram Bot API
    Args:
        chat_id: Telegram chat ID (numeric or string)
        message: Message text (supports basic HTML formatting)
    Returns:
        True if sent successfully, False otherwise
    """
    if not TELEGRAM_ENABLED:
        logger.warning("Telegram not configured (TELEGRAM_BOT_TOKEN missing)")
        return False

    try:
        url = f"{TELEGRAM_API_URL}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        response = httpx.post(url, json=payload, timeout=10)
        success = response.status_code == 200

        if success:
            logger.info(f"Telegram message sent to {chat_id}")
        else:
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")

        return success
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False

def send_telegram_voice(chat_id: str, audio_file_path: str, caption: str = "") -> bool:
    """
    Send a voice message via Telegram Bot API
    Args:
        chat_id: Telegram chat ID
        audio_file_path: Path to audio file (MP3, OGG)
        caption: Optional caption
    Returns:
        True if sent successfully, False otherwise
    """
    if not TELEGRAM_ENABLED:
        logger.warning("Telegram not configured")
        return False

    if not os.path.exists(audio_file_path):
        logger.error(f"Audio file not found: {audio_file_path}")
        return False

    try:
        url = f"{TELEGRAM_API_URL}/sendVoice"
        with open(audio_file_path, "rb") as audio:
            files = {"voice": audio}
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption

            response = httpx.post(url, files=files, data=data, timeout=30)
            success = response.status_code == 200

            if success:
                logger.info(f"Telegram voice message sent to {chat_id}")
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")

            return success
    except Exception as e:
        logger.error(f"Failed to send Telegram voice: {e}")
        return False

def format_reminder_message(reminder_number: int, stage: str, recipient_name: str, details: dict = None) -> str:
    """
    Format a reminder message for Telegram
    Args:
        reminder_number: Which reminder (1, 2, 3, 4, 5)
        stage: Stage name ("form", "interview", "interest", "offer", "client")
        recipient_name: Candidate/client name
        details: Optional dict with additional details
    Returns:
        Formatted HTML message
    """
    emoji_map = {
        "form": "📋",
        "interview": "🎯",
        "interest": "💼",
        "offer": "🎉",
        "client": "✓"
    }

    stage_text_map = {
        "form": "form submission",
        "interview": "interview confirmation",
        "interest": "interest confirmation",
        "offer": "offer response",
        "client": "client decision"
    }

    emoji = emoji_map.get(stage, "🔔")
    stage_text = stage_text_map.get(stage, stage)

    # Build message with escalating urgency
    urgency_map = {
        1: "Please action this soon",
        2: "Reminder: Still pending",
        3: "Urgent: Action required",
        4: "Critical: Please respond",
        5: "🚨 Final reminder: Immediate action needed"
    }

    message = f"{emoji} <b>Reminder #{reminder_number}</b>\n"
    message += f"<b>Candidate:</b> {recipient_name}\n"
    message += f"<b>Stage:</b> {stage_text}\n\n"
    message += urgency_map.get(reminder_number, "Please respond")

    if details:
        if "due_date" in details:
            message += f"\n<b>Due:</b> {details['due_date']}"
        if "action_url" in details:
            message += f"\n<a href='{details['action_url']}'>Respond Now</a>"

    return message
