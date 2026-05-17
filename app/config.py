"""
Configuration loader for TDM.
Loads settings from config.yaml and environment variables from .env file.
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")


def _load_yaml_config() -> dict:
    """Load the YAML configuration file."""
    config_path = os.environ.get("TDM_CONFIG_PATH", str(_project_root / "config.yaml"))
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found at {config_path}. "
            f"Create config.yaml or set TDM_CONFIG_PATH to a valid YAML config."
        )

    with open(config_path, "r") as f:
        return yaml.safe_load(f)


# Singleton config dict — loaded once on import
_config: dict = {}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_config() -> dict:
    """Returns the full merged configuration dictionary."""
    global _config
    if not _config:
        _config = _load_yaml_config()
    return _config


def get_llm_config() -> dict:
    """Returns LLM-specific configuration."""
    cfg = get_config()
    llm = cfg.get("llm", {})
    return {
        "provider": llm.get("provider", "openrouter"),
        "model": llm.get("model", "openai/gpt-4o-mini"),
        "temperature": llm.get("temperature", 0.1),
        "max_tokens": llm.get("max_tokens", 16384),
        "base_url": llm.get("base_url", "https://openrouter.ai/api/v1"),
        "api_key": os.environ.get("OPENROUTER_API_KEY", ""),
        "offline_mode": _env_bool("TDM_OFFLINE_MODE", False),
    }


def get_db_config() -> dict:
    """Returns database configuration."""
    cfg = get_config()
    db = cfg.get("database", {})
    return {
        "url": db.get("url", "sqlite:///./test_data.db"),
    }


def get_server_config() -> dict:
    """Returns server configuration."""
    cfg = get_config()
    srv = cfg.get("server", {})
    return {
        "host": srv.get("host", "0.0.0.0"),
        "port": srv.get("port", 8000),
    }


def get_log_config() -> dict:
    """Returns logging configuration."""
    cfg = get_config()
    log = cfg.get("logging", {})
    return {
        "level": log.get("level", "INFO"),
        "format": log.get("format", "console"),
    }
