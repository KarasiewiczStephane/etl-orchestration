"""Structured logging setup for the ETL pipeline.

Configures Python's logging module with consistent formatting
across all pipeline components.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from src.utils.config import load_config


def setup_logging(
    name: Optional[str] = None,
    level: Optional[str] = None,
) -> logging.Logger:
    """Configure and return a logger instance.

    Reads defaults from configs/config.yaml and creates a logger
    with both console and optional file handlers.

    Args:
        name: Logger name. Uses root logger if None.
        level: Override log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        Configured logger instance.
    """
    try:
        config = load_config()
        log_config = config.get("logging", {})
    except FileNotFoundError:
        log_config = {}

    log_level = level or log_config.get("level", "INFO")
    log_format = log_config.get(
        "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    log_file = log_config.get("file")

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if not logger.handlers:
        formatter = logging.Formatter(log_format)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_path)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

    return logger
