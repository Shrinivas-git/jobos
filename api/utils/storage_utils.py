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

def save_resume_file(candidate_id: str, original_filename: str, content: bytes):
    """
    Saves a resume file in /data/resumes/<candidate_id>/ with versioning.
    Format: <candidate_id>_v<version>.<ext>
    """
    resume_dir = os.path.join(BASE_DATA_DIR, "resumes", candidate_id)
    os.makedirs(resume_dir, exist_ok=True)
    
    ext = original_filename.split('.')[-1].lower() if '.' in original_filename else "pdf"
    
    # Determine version
    existing_files = [f for f in os.listdir(resume_dir) if f.startswith(f"{candidate_id}_v")]
    version = 1
    if existing_files:
        versions = []
        for f in existing_files:
            try:
                # Extract X from can_id_vX.ext
                v_part = f.split('_v')[-1].split('.')[0]
                versions.append(int(v_part))
            except:
                continue
        if versions:
            version = max(versions) + 1
            
    filename = f"{candidate_id}_v{version}.{ext}"
    file_path = os.path.join(resume_dir, filename)
    
    with open(file_path, "wb") as f:
        f.write(content)
        
    return file_path

def save_candidate_match_results(client_slug: str, jd_id: str, candidate_id: str, match_data: dict, pointer_data: dict):
    """
    Saves match_score.json and pointer.json in /data/clients/<client_slug>/<jd_id>/candidates/<candidate_id>/
    """
    can_match_dir = os.path.join(BASE_DATA_DIR, "clients", client_slug, jd_id, "candidates", candidate_id)
    os.makedirs(can_match_dir, exist_ok=True)
    
    import json
    from datetime import datetime

    def _default(o):
        if isinstance(o, datetime):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    # Save match_score.json
    with open(os.path.join(can_match_dir, "match_score.json"), "w") as f:
        json.dump(match_data, f, indent=2, default=_default)

    # Save pointer.json
    with open(os.path.join(can_match_dir, "pointer.json"), "w") as f:
        json.dump(pointer_data, f, indent=2, default=_default)
        
    return can_match_dir


def save_document_file(candidate_id: str, doc_id: str, ext: str, content: bytes) -> str:
    doc_dir = os.path.join(BASE_DATA_DIR, "documents", candidate_id)
    os.makedirs(doc_dir, exist_ok=True)
    file_path = os.path.join(doc_dir, f"{doc_id}.{ext}")
    with open(file_path, "wb") as f:
        f.write(content)
    return file_path
