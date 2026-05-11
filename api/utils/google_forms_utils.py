import os
import json
import logging
import io

logger = logging.getLogger(__name__)

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("Google libraries not installed. Run: pip install google-auth google-auth-httplib2 google-api-python-client")

GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "{}")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
VIDEO_STORAGE_PATH = os.getenv("VIDEO_STORAGE_PATH", "/tmp/video_resumes")
os.makedirs(VIDEO_STORAGE_PATH, exist_ok=True)

try:
    CREDENTIALS_DICT = json.loads(GOOGLE_CREDENTIALS_JSON)
except json.JSONDecodeError:
    CREDENTIALS_DICT = {}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

def _get_credentials():
    if not GOOGLE_AVAILABLE or not CREDENTIALS_DICT:
        return None
    try:
        return service_account.Credentials.from_service_account_info(CREDENTIALS_DICT, scopes=SCOPES)
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")
        return None

def _get_sheets_service():
    creds = _get_credentials()
    if not creds:
        return None
    return build("sheets", "v4", credentials=creds)

def _get_drive_service():
    creds = _get_credentials()
    if not creds:
        return None
    return build("drive", "v3", credentials=creds)

def get_sheet_responses(sheet_id: str = None) -> list[dict]:
    """
    Fetch all rows from the Google Sheet linked to the Form.
    Returns list of dicts keyed by column header.
    Expected columns: Timestamp, Full Name, Email Address, Phone Number,
                      Aadhar Number, LinkedIn Profile URL, Alternate Phone Number,
                      Telegram Handle, Video Resume
    """
    sheet_id = sheet_id or GOOGLE_SHEET_ID
    if not sheet_id:
        logger.error("GOOGLE_SHEET_ID not configured")
        return []

    service = _get_sheets_service()
    if not service:
        return []

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="A1:Z1000"
        ).execute()
        rows = result.get("values", [])
        if len(rows) < 2:
            return []

        headers = rows[0]
        responses = []
        for row in rows[1:]:
            padded = row + [""] * (len(headers) - len(row))
            responses.append(dict(zip(headers, padded)))
        logger.info(f"Fetched {len(responses)} rows from sheet {sheet_id}")
        return responses
    except Exception as e:
        logger.error(f"Failed to fetch sheet responses: {e}")
        return []

def find_video_in_drive(candidate_email: str, folder_id: str = None) -> str | None:
    """
    Find the video file uploaded by a candidate in Google Drive.
    Google Forms stores files in a subfolder named after the respondent's email.
    Returns the Drive file ID or None.
    """
    folder_id = folder_id or GOOGLE_DRIVE_FOLDER_ID
    if not folder_id:
        return None

    service = _get_drive_service()
    if not service:
        return None

    try:
        # Files are stored in subfolders inside the form uploads folder
        result = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, mimeType, parents)",
            pageSize=100
        ).execute()
        files = result.get("files", [])

        # Look for video files (mp4, mov, avi, webm)
        video_mimes = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm"}
        for f in files:
            if f.get("mimeType") in video_mimes:
                return f["id"]
            # Check subfolders
            if f.get("mimeType") == "application/vnd.google-apps.folder":
                sub = service.files().list(
                    q=f"'{f['id']}' in parents and trashed=false",
                    fields="files(id, name, mimeType)"
                ).execute()
                for sf in sub.get("files", []):
                    if sf.get("mimeType") in video_mimes:
                        return sf["id"]
        return None
    except Exception as e:
        logger.error(f"Failed to search Drive: {e}")
        return None

def download_video_from_drive(file_id: str, candidate_id: str, jd_id: str) -> str | None:
    """
    Download a video from Google Drive and save to local storage.
    Returns local path or None on failure.
    """
    service = _get_drive_service()
    if not service:
        return None

    try:
        subdir = os.path.join(VIDEO_STORAGE_PATH, jd_id, candidate_id)
        os.makedirs(subdir, exist_ok=True)
        local_path = os.path.join(subdir, "video_resume.mp4")

        request = service.files().get_media(fileId=file_id)
        fh = io.FileIO(local_path, "wb")
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.close()
        logger.info(f"Downloaded video from Drive {file_id} -> {local_path}")
        return local_path
    except Exception as e:
        logger.error(f"Failed to download video from Drive: {e}")
        return None

def get_video_storage_path(candidate_id: str, jd_id: str) -> str:
    subdir = os.path.join(VIDEO_STORAGE_PATH, jd_id, candidate_id)
    os.makedirs(subdir, exist_ok=True)
    return os.path.join(subdir, "video_resume.mp4")

def save_video_file(video_data: bytes, candidate_id: str, jd_id: str) -> str | None:
    try:
        video_path = get_video_storage_path(candidate_id, jd_id)
        with open(video_path, "wb") as f:
            f.write(video_data)
        return video_path
    except Exception as e:
        logger.error(f"Failed to save video: {e}")
        return None
