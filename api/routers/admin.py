from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import yaml
import os
import logging

from auth import check_role

logger = logging.getLogger(__name__)

CONFIG_PATH = os.getenv("CONFIG_PATH", "/config/config.yaml")

router = APIRouter(prefix="/admin", tags=["admin"])


class ConfigUpdate(BaseModel):
    p_threshold: float
    k_threshold: int
    batch_size: int


def _get_config_path():
    """Get the actual config file path."""
    if os.path.exists(CONFIG_PATH):
        return CONFIG_PATH
    if os.path.exists("config/config.yaml"):
        return "config/config.yaml"
    if os.path.exists("../config/config.yaml"):
        return "../config/config.yaml"
    raise FileNotFoundError("config.yaml not found")


def _load_config():
    """Load current config from yaml."""
    try:
        path = _get_config_path()
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}


def _save_config(config: dict):
    """Save config back to yaml."""
    try:
        path = _get_config_path()
        with open(path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Config saved to {path}")
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        raise


@router.get("/config")
async def get_config(user: dict = Depends(check_role(["admin"]))):
    """Get current matching configuration."""
    config = _load_config()
    matching = config.get("matching", {})
    return {
        "p_threshold": matching.get("p_threshold", 0.50),
        "k_threshold": matching.get("k_threshold", 10),
        "batch_size": matching.get("batch_size", 3),
    }


@router.put("/config")
async def update_config(
    update: ConfigUpdate,
    user: dict = Depends(check_role(["admin"]))
):
    """Update matching configuration. Admin only."""
    # Validate inputs
    if not (0 <= update.p_threshold <= 1):
        raise HTTPException(status_code=400, detail="p_threshold must be between 0 and 1")
    if update.k_threshold < 1:
        raise HTTPException(status_code=400, detail="k_threshold must be >= 1")
    if update.batch_size < 1:
        raise HTTPException(status_code=400, detail="batch_size must be >= 1")

    config = _load_config()
    if "matching" not in config:
        config["matching"] = {}

    config["matching"]["p_threshold"] = update.p_threshold
    config["matching"]["k_threshold"] = update.k_threshold
    config["matching"]["batch_size"] = update.batch_size

    _save_config(config)

    return {
        "status": "success",
        "message": "Configuration updated",
        "updated": {
            "p_threshold": update.p_threshold,
            "k_threshold": update.k_threshold,
            "batch_size": update.batch_size,
        }
    }
