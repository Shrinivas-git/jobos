import os
import imaplib
import email
import logging
import time
import requests
import re
from email.header import decode_header
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

IMAP_HOST = os.getenv("EMAIL_IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.getenv("EMAIL_IMAP_PORT", 993))
IMAP_USER = os.getenv("EMAIL_IMAP_USER", "")
IMAP_PASSWORD = os.getenv("EMAIL_IMAP_PASSWORD", "")
IMAP_FOLDER = os.getenv("INTAKE_EMAIL_FOLDER", "INBOX")
INTAKE_API_URL = os.getenv("INTAKE_API_URL", "http://api:8000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
INTAKE_BASE_PATH = "/data/resumes/intake"
POLL_INTERVAL = int(os.getenv("EMAIL_POLL_INTERVAL_SECS", 60))

# JD-ID pattern: JD-YYYYMMDD-xxxxxxxx
JD_ID_PATTERN = r'JD-\d{8}-[a-f0-9]{8}'


def create_intake_folder():
    """Ensure intake folder exists."""
    Path(INTAKE_BASE_PATH).mkdir(parents=True, exist_ok=True)
    logger.info(f"Intake folder ready: {INTAKE_BASE_PATH}")


def connect_imap():
    """Connect to IMAP server with error handling."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASSWORD)
        logger.info(f"Connected to {IMAP_HOST} as {IMAP_USER}")
        return mail
    except Exception as e:
        logger.error(f"IMAP connection failed: {e}")
        return None


def extract_jd_id(subject: str, body: str) -> str | None:
    """Extract JD-ID from email subject or body."""
    for text in [subject, body]:
        if text:
            match = re.search(JD_ID_PATTERN, text, re.IGNORECASE)
            if match:
                return match.group(0).upper()
    return None


def get_email_parts(msg) -> tuple:
    """Extract subject, body, and attachments from email message."""
    subject = ""
    body = ""
    attachments = []

    try:
        subject_header = msg.get("Subject", "")
        if isinstance(subject_header, str):
            subject = subject_header
        else:
            decoded = decode_header(subject_header)
            subject = "".join(
                part.decode(charset or "utf-8") if isinstance(part, bytes) else part
                for part, charset in decoded
            )
    except Exception as e:
        logger.warning(f"Failed to decode subject: {e}")
        subject = "(decode error)"

    for part in msg.walk():
        content_type = part.get_content_type()
        content_disposition = part.get("Content-Disposition", "")

        if content_disposition.startswith("attachment"):
            filename = part.get_filename()
            if filename:
                if filename.lower().endswith(('.pdf', '.docx')):
                    attachments.append({
                        "filename": filename,
                        "content": part.get_payload(decode=True)
                    })
        elif content_type == "text/plain":
            try:
                charset = part.get_content_charset() or "utf-8"
                body = part.get_payload(decode=True).decode(charset)
            except Exception as e:
                logger.warning(f"Failed to decode body: {e}")

    return subject, body, attachments


def save_attachment(filename: str, content: bytes) -> str:
    """Save attachment to intake folder and return file path."""
    # Use timestamp + original filename to avoid collisions
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{filename}"
    file_path = os.path.join(INTAKE_BASE_PATH, safe_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(f"Saved attachment: {file_path}")
    return file_path


def call_intake_api(file_path: str, jd_id: str | None, source_email: str):
    """Call POST /candidates/email-intake endpoint."""
    try:
        payload = {
            "file_path": file_path,
            "source_email": source_email
        }
        if jd_id:
            payload["jd_id"] = jd_id

        response = requests.post(
            f"{INTAKE_API_URL}/candidates/email-intake",
            json=payload,
            headers={"X-Internal-Key": INTERNAL_API_KEY},
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            logger.info(f"API success: candidate_id={result.get('candidate_id')}, jd_id={jd_id or 'auto-match'}")
            return True
        else:
            logger.error(f"API error: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"Failed to call intake API: {e}")
        return False


def process_email(mail, email_id: bytes):
    """Process a single email: extract attachments, parse JD-ID, call API."""
    try:
        status, msg_data = mail.fetch(email_id, "(RFC822)")
        if status != "OK":
            logger.error(f"Failed to fetch email {email_id}")
            return False

        msg = email.message_from_bytes(msg_data[0][1])
        from_addr = msg.get("From", "unknown@example.com")
        subject, body, attachments = get_email_parts(msg)

        if not attachments:
            logger.info(f"No resume attachments in email from {from_addr}")
            return True

        jd_id = extract_jd_id(subject, body)
        logger.info(f"Processing {len(attachments)} attachment(s) | JD-ID: {jd_id or 'none'} | From: {from_addr}")

        for att in attachments:
            file_path = save_attachment(att["filename"], att["content"])
            success = call_intake_api(file_path, jd_id, from_addr)
            if not success:
                logger.warning(f"API call failed for {att['filename']}, but continuing")

        return True

    except Exception as e:
        logger.error(f"Error processing email {email_id}: {e}")
        return False


def mark_seen(mail, email_id: bytes):
    """Mark email as SEEN."""
    try:
        mail.store(email_id, "+FLAGS", "\\Seen")
    except Exception as e:
        logger.warning(f"Failed to mark email as seen: {e}")


def poll_emails():
    """Main polling loop."""
    logger.info("Starting email watcher loop")
    create_intake_folder()

    while True:
        try:
            mail = connect_imap()
            if not mail:
                logger.warning("IMAP connection failed, retrying in 60s")
                time.sleep(60)
                continue

            mail.select(IMAP_FOLDER)

            # Search for UNSEEN emails
            status, email_ids = mail.search(None, "UNSEEN")
            if status != "OK":
                logger.warning("Failed to search for unseen emails")
                mail.close()
                mail.logout()
                time.sleep(POLL_INTERVAL)
                continue

            email_list = email_ids[0].split()
            if email_list:
                logger.info(f"Found {len(email_list)} unseen email(s)")
                for email_id in email_list:
                    success = process_email(mail, email_id)
                    if success:
                        mark_seen(mail, email_id)
            else:
                logger.debug("No unseen emails")

            mail.close()
            mail.logout()

        except Exception as e:
            logger.error(f"Polling error: {e}")

        logger.debug(f"Sleeping for {POLL_INTERVAL}s before next poll")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    if not IMAP_USER or not IMAP_PASSWORD:
        logger.error("EMAIL_IMAP_USER and EMAIL_IMAP_PASSWORD must be set")
        exit(1)

    poll_emails()
