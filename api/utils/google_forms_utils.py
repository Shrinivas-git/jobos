import os
import json
import logging

logger = logging.getLogger(__name__)

# Try to import Google libraries (optional for now)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("Google libraries not installed. Install with: pip install google-auth google-auth-httplib2 google-auth-oauthlib google-api-python-client")

# Load Google credentials from environment
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "{}")
try:
    CREDENTIALS_DICT = json.loads(GOOGLE_CREDENTIALS_JSON)
except json.JSONDecodeError:
    CREDENTIALS_DICT = {}

# Video storage path (local filesystem)
VIDEO_STORAGE_PATH = os.getenv("VIDEO_STORAGE_PATH", "/tmp/video_resumes")
os.makedirs(VIDEO_STORAGE_PATH, exist_ok=True)

# Initialize Google API clients
def _get_forms_service():
    if not GOOGLE_AVAILABLE:
        logger.error("Google libraries not available")
        return None
    if not CREDENTIALS_DICT:
        logger.error("Google credentials not configured")
        return None
    try:
        credentials = service_account.Credentials.from_service_account_info(
            CREDENTIALS_DICT,
            scopes=["https://www.googleapis.com/auth/forms.responses.readonly"]
        )
        return build("forms", "v1", credentials=credentials)
    except Exception as e:
        logger.error(f"Failed to create Forms service: {e}")
        return None

def get_form_responses(form_id: str, limit: int = 100):
    """
    Fetch all responses from a Google Form
    Returns: List of response dicts with question answers
    """
    if not GOOGLE_AVAILABLE:
        logger.warning("Google Forms API not available")
        return []

    try:
        service = _get_forms_service()
        if not service:
            return []

        form = service.forms().get(formId=form_id).execute()
        responses = service.forms().responses().list(formId=form_id).execute()

        parsed_responses = []
        for response in responses.get("responses", [])[:limit]:
            parsed = _parse_form_response(form, response)
            parsed_responses.append(parsed)

        logger.info(f"Fetched {len(parsed_responses)} responses from form {form_id}")
        return parsed_responses
    except Exception as e:
        logger.error(f"Failed to fetch form responses: {e}")
        return []

def _parse_form_response(form: dict, response: dict) -> dict:
    """Parse a single form response into structured data"""
    parsed = {
        "response_id": response.get("responseId"),
        "timestamp": response.get("createTime"),
        "answers": {}
    }

    # Build question ID to title map
    question_map = {}
    for item in form.get("items", []):
        question_map[item.get("questionItem", {}).get("question", {}).get("questionId")] = {
            "title": item.get("title"),
            "type": item.get("questionItem", {}).get("question", {}).get("questionType")
        }

    # Extract answers
    answers = response.get("answers", {})
    for question_id, answer in answers.items():
        question_info = question_map.get(question_id, {})
        question_title = question_info.get("title", question_id)

        # Extract text responses
        if "textAnswers" in answer:
            text_answers = answer["textAnswers"].get("answers", [])
            parsed["answers"][question_title] = text_answers[0]["value"] if text_answers else None
        elif "fileUploadAnswers" in answer:
            file_answers = answer["fileUploadAnswers"].get("answers", [])
            parsed["answers"][question_title] = file_answers[0] if file_answers else None

    return parsed

def get_video_storage_path(candidate_id: str, jd_id: str) -> str:
    """
    Get local path where video resume should be stored
    Args:
        candidate_id: Candidate ID
        jd_id: JD ID
    Returns:
        Full path for video file
    """
    subdir = os.path.join(VIDEO_STORAGE_PATH, jd_id, candidate_id)
    os.makedirs(subdir, exist_ok=True)
    return os.path.join(subdir, "video_resume.mp4")

def save_video_file(video_data: bytes, candidate_id: str, jd_id: str) -> str:
    """
    Save video file to local storage
    Args:
        video_data: Binary video data
        candidate_id: Candidate ID
        jd_id: JD ID
    Returns:
        Path to saved file, or None on failure
    """
    try:
        video_path = get_video_storage_path(candidate_id, jd_id)
        with open(video_path, "wb") as f:
            f.write(video_data)
        logger.info(f"Video saved: {video_path}")
        return video_path
    except Exception as e:
        logger.error(f"Failed to save video: {e}")
        return None
