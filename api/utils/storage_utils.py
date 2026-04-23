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
