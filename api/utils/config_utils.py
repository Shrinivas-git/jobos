import os
import yaml
import logging

logger = logging.getLogger(__name__)

# Correct path assuming running from /app in Docker
CONFIG_PATH = os.getenv("CONFIG_PATH", "/config/config.yaml")

def get_config():
    """Loads and returns the configuration from config.yaml."""
    try:
        # Check local relative path if /config/config.yaml doesn't exist
        path = CONFIG_PATH
        if not os.path.exists(path):
            # Fallback for local dev if not in container exactly as expected
            path = "config/config.yaml"
            if not os.path.exists(path):
                # Another fallback
                path = "../config/config.yaml"
                
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
            return config
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        # Return sensible defaults
        return {
            "matching": {
                "p_threshold": 0.50,
                "k_threshold": 10
            }
        }

def get_matching_thresholds():
    """Returns p_threshold and k_threshold."""
    config = get_config()
    matching = config.get("matching", {})
    return (
        matching.get("p_threshold", 0.50),
        matching.get("k_threshold", 10)
    )


_PIPELINE_DEFAULTS = {
    "stage_order": ["shortlist", "interview_1", "interview_final", "offer", "joined"],
    "sla_hours": {
        "shortlist": 72,
        "interview_1": 120,
        "interview_final": 168,
        "offer": 72,
        "joined": 360,
    },
    "warning_threshold": 0.75,
    "monitor_interval_minutes": 30,
    "escalation_roles": ["manager", "admin"],
}


def get_pipeline_config():
    cfg = get_config().get("pipeline") or {}
    merged = {**_PIPELINE_DEFAULTS, **cfg}
    merged["sla_hours"] = {**_PIPELINE_DEFAULTS["sla_hours"], **(cfg.get("sla_hours") or {})}
    return merged
