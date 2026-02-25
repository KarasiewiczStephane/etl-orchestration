"""Configuration loader for YAML-based project settings.

Provides centralized access to all configuration files including
project settings, source definitions, and quality rules.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_path(config_path: str | Path) -> Path:
    """Resolve a config path relative to project root.

    Args:
        config_path: Path to config file, absolute or relative to project root.

    Returns:
        Resolved absolute path.
    """
    path = Path(config_path)
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    return path


def load_yaml(config_path: str | Path) -> dict[str, Any]:
    """Load and parse a YAML configuration file.

    Args:
        config_path: Path to the YAML file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.
    """
    resolved = _resolve_path(config_path)
    if not resolved.exists():
        raise FileNotFoundError(f"Config file not found: {resolved}")

    logger.info("Loading config from %s", resolved)
    with open(resolved) as f:
        return yaml.safe_load(f)


def load_config() -> dict[str, Any]:
    """Load the main project configuration.

    Returns:
        Project configuration dictionary.
    """
    return load_yaml("configs/config.yaml")


def load_source_config() -> dict[str, Any]:
    """Load source definitions configuration.

    Returns:
        Source definitions dictionary.
    """
    return load_yaml("configs/sources.yaml")


def load_quality_rules() -> dict[str, Any]:
    """Load data quality rules configuration.

    Returns:
        Quality rules dictionary.
    """
    return load_yaml("configs/quality_rules.yaml")


def get_project_root() -> Path:
    """Return the project root directory.

    Returns:
        Path to the project root.
    """
    return _PROJECT_ROOT
