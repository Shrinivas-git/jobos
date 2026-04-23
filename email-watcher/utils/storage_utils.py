import os
import shutil

BASE_DATA_DIR = "/data"

def create_jd_folder_structure(client_slug: str, jd_id: str):
    jd_path = os.path.join(BASE_DATA_DIR, "clients", client_slug, jd_id)
    raw_path = os.path.join(jd_path, "raw")
    candidates_path = os.path.join(jd_path, "candidates")
    
    os.makedirs(raw_path, exist_ok=True)
    os.makedirs(candidates_path, exist_ok=True)
    
    return {
        "jd_path": jd_path,
        "raw_path": raw_path,
        "candidates_path": candidates_path
    }

def save_raw_jd_content(raw_path: str, filename: str, content: bytes):
    file_path = os.path.join(raw_path, filename)
    with open(file_path, "wb") as f:
        f.write(content)
    return file_path
