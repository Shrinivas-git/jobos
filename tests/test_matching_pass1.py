import sys
import os
from unittest.mock import MagicMock, patch

import logging
logging.basicConfig(level=logging.INFO)

# 1. Mock all external dependencies BEFORE any imports from api
mock_modules = [
    "qdrant_client",
    "qdrant_client.http",
    "qdrant_client.http.models",
    "pymongo",
    "google.generativeai",
    "celery",
    "slugify"
]

for module in mock_modules:
    sys.modules[module] = MagicMock()

# 2. Mock project utils that connect to DB/Services
sys.modules["utils.client_utils"] = MagicMock()
mock_db = MagicMock()
sys.modules["utils.client_utils"].get_db = MagicMock(return_value=mock_db)

# Crucial: Mock Celery decorator to return the function unchanged
def mock_task_decorator(*args, **kwargs):
    def wrapper(f):
        f.delay = MagicMock() # Add .delay() support
        return f
    return wrapper

sys.modules["celery_app"] = MagicMock()
mock_celery = MagicMock()
mock_celery.task = mock_task_decorator
sys.modules["celery_app"].celery = mock_celery

# 3. Add api to path and import
sys.path.append(os.path.join(os.getcwd(), "api"))
from tasks.matching_tasks import run_matching

def test_run_matching_logic():
    print("Testing run_matching logic...")
    jd_id = "JD-TEST-001"
    
    # Setup internal mocks
    with patch("tasks.matching_tasks.get_jd_vector") as mock_get_vec, \
         patch("tasks.matching_tasks.search_resumes_by_vector") as mock_search, \
         patch("tasks.matching_tasks.get_matching_thresholds") as mock_thresholds, \
         patch("tasks.matching_tasks.run_pass_2") as mock_pass2:
        
        # Scenario 1: Successful match (above P, meet K)
        mock_thresholds.return_value = (0.5, 2)
        mock_get_vec.return_value = [0.1] * 768
        
        mock_res1 = MagicMock()
        mock_res1.score = 0.8
        mock_res1.payload = {"candidate_id": "CAN-1", "source": "internal"}
        
        mock_res2 = MagicMock()
        mock_res2.score = 0.6
        mock_res2.payload = {"candidate_id": "CAN-2", "source": "internal"}
        
        mock_search.return_value = [mock_res1, mock_res2]
        
        print("Calling run_matching...")
        result = run_matching(jd_id)
        print(f"Result returned: {result}")
        
        assert result["matches_count"] == 2
        assert result["pass_2_triggered"] is True
        assert mock_db.candidate_pools.update_one.call_count >= 2
        
        # Verify external sourcing is FALSE when K-threshold met
        mock_db.job_descriptions.update_one.assert_any_call(
            {"jd_id": jd_id},
            {"$set": {"needs_external_sourcing": False}}
        )
        print(" - Pass 1 (High match): Success")

        # Scenario 2: Below K-threshold (trigger external sourcing flag)
        mock_db.job_descriptions.update_one.reset_mock()
        mock_thresholds.return_value = (0.5, 5) # Need 5, only have 2
        
        result = run_matching(jd_id)
        
        assert result["matches_count"] == 2
        mock_db.job_descriptions.update_one.assert_any_call(
            {"jd_id": jd_id},
            {"$set": {"needs_external_sourcing": True, "sourcing_status": "pending"}}
        )
        print(" - Pass 1 (Below K-threshold): Success")

        # Scenario 3: Below P-threshold (should be filtered out)
        mock_res3 = MagicMock()
        mock_res3.score = 0.4 # Below 0.5
        mock_res3.payload = {"candidate_id": "CAN-3"}
        mock_search.return_value = [mock_res3]
        
        result = run_matching(jd_id)
        assert result["matches_count"] == 0
        assert result["pass_2_triggered"] is False
        print(" - Pass 1 (P-threshold filtering): Success")

if __name__ == "__main__":
    try:
        test_run_matching_logic()
        print("\nAll Matching Pass 1 logic tests PASSED.")
    except Exception as e:
        print(f"\nTests FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
