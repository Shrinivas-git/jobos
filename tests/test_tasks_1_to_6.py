import os
import sys
import pytest
import logging
from unittest.mock import MagicMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add current dir to sys.path
sys.path.append(os.getcwd())

# Mock heavy modules GLOBALLY for other tests, but we'll manage them carefully
# Actually, let's NOT mock globally if it causes issues.
# Just mock them inside the tests that need them.

def clear_project_modules():
    """Clears project-specific modules from sys.modules to ensure clean state."""
    to_delete = [m for m in sys.modules if m.startswith('utils') or m.startswith('auth') or m.startswith('tasks') or m == 'slugify' or m == 'pymongo']
    for m in to_delete:
        del sys.modules[m]

# TASK-001: Auth Keycloak Setup
def test_task_001_auth_logic():
    clear_project_modules()
    logger.info("Verifying TASK-001: Auth Logic...")
    from auth import check_role
    dependency = check_role(["recruiter"])
    assert callable(dependency)
    logger.info(" - Auth logic check: PASSED")

# TASK-002 & TASK-003: Data Model & API Skeleton
def test_task_002_003_infrastructure():
    logger.info("Verifying TASK-002 & TASK-003: Infrastructure...")
    assert os.path.exists("routers")
    assert os.path.exists("utils")
    assert os.path.exists("tasks")
    assert os.path.exists("main.py")
    logger.info(" - Directory structure check: PASSED")

# TASK-004: JD Intake Engine
def test_task_004_jd_intake_logic():
    clear_project_modules()
    logger.info("Verifying TASK-004: JD Intake Logic...")
    
    with patch("utils.client_utils.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        mock_db.clients.find_one.return_value = None
        
        from utils.client_utils import find_or_create_client
        client = find_or_create_client("test@fidelitus.com")
        # Ensure slugify worked (it should be real unless mocked)
        assert client["slug"] == "fidelitus"
        assert mock_db.clients.insert_one.called
    logger.info(" - JD intake client mapping: PASSED")

# TASK-005: JD Structuring
def test_task_005_jd_structuring_logic():
    clear_project_modules()
    logger.info("Verifying TASK-005: JD Structuring Logic...")
    
    with patch("google.generativeai.GenerativeModel") as mock_model_class:
        mock_model = mock_model_class.return_value
        mock_response = MagicMock()
        mock_response.text = '{"title": "Software Engineer", "skills": ["Python", "Docker"]}'
        mock_model.generate_content.return_value = mock_response
        
        from utils.gemini_utils import extract_jd_data
        data = extract_jd_data("Need a Python dev with Docker.")
        assert data["title"] == "Software Engineer"
        assert "Python" in data["skills"]
    logger.info(" - JD structuring Gemini extraction: PASSED")

# TASK-006: Resume Ingestion Pipeline
def test_task_006_resume_ingestion_logic():
    clear_project_modules()
    logger.info("Verifying TASK-006: Resume Ingestion Logic...")
    
    # Mocking external libs
    sys.modules["google.generativeai"] = MagicMock()
    sys.modules["sentence_transformers"] = MagicMock()
    sys.modules["torch"] = MagicMock()
    
    with patch("pdfplumber.open") as mock_pdf:
        mock_pdf_instance = mock_pdf.return_value.__enter__.return_value
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "John Doe Resume Text"
        mock_pdf_instance.pages = [mock_page]
        
        from utils.resume_utils import extract_text_from_file
        text = extract_text_from_file("dummy.pdf")
        assert "John Doe" in text
    logger.info(" - Resume text extraction (PDF): PASSED")

# Real Database & Qdrant connectivity check (TASK-002 Verification)
def test_task_002_connectivity():
    clear_project_modules()
    if 'qdrant_client' in sys.modules:
        del sys.modules['qdrant_client']
    if 'qdrant_client.http' in sys.modules:
        del sys.modules['qdrant_client.http']
        
    logger.info("Verifying TASK-002: Real Connectivity...")
    
    from utils.client_utils import get_db
    from qdrant_client import QdrantClient
    
    # Test MongoDB (Real connection)
    db = get_db()
    collections = db.list_collection_names()
    logger.info(f" - MongoDB collections found: {collections}")
    assert "candidates" in collections
    assert "job_descriptions" in collections
    
    # Test Qdrant (Real connection)
    q_host = os.getenv("QDRANT_HOST", "qdrant")
    q_client = QdrantClient(host=q_host, port=6333)
    q_collections = [c.name for c in q_client.get_collections().collections]
    logger.info(f" - Qdrant collections found: {q_collections}")
    assert "jd_vectors" in q_collections
    assert "resume_vectors" in q_collections
    logger.info(" - Real connectivity check: PASSED")
