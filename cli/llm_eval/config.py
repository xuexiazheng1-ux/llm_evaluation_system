"""
Configuration management for CLI
"""
import os
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".llm-eval"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "server_url": "http://localhost:8000",
    "api_key": None,
    "default_timeout": 60,
}


def ensure_config_dir():
    """Ensure config directory exists"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    """Load configuration from file"""
    ensure_config_dir()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """Save configuration to file"""
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_config_value(key, default=None):
    """Get a specific config value"""
    config = load_config()
    return config.get(key, default)


def set_config_value(key, value):
    """Set a specific config value"""
    config = load_config()
    config[key] = value
    save_config(config)


def get_api_base_url():
    """Get API base URL"""
    config = load_config()
    return config.get("server_url", "http://localhost:8000")


def get_headers():
    """Get request headers"""
    config = load_config()
    headers = {"Content-Type": "application/json"}
    if config.get("api_key"):
        headers["Authorization"] = f"Bearer {config['api_key']}"
    return headers
