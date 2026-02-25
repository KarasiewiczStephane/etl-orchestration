"""Tests for structured logging setup."""

import logging
from pathlib import Path
from unittest.mock import patch

from src.utils.logger import setup_logging


class TestSetupLogging:
    """Tests for the setup_logging function."""

    def test_returns_logger(self) -> None:
        """Returns a Logger instance."""
        logger = setup_logging("test_returns")
        assert isinstance(logger, logging.Logger)

    def test_logger_name(self) -> None:
        """Logger has the specified name."""
        logger = setup_logging("my_module")
        assert logger.name == "my_module"

    def test_default_level_from_config(self) -> None:
        """Logger level defaults to config value."""
        logger = setup_logging("test_level")
        assert logger.level == logging.INFO

    def test_override_level(self) -> None:
        """Explicit level parameter overrides config."""
        logger = setup_logging("test_override", level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_has_console_handler(self) -> None:
        """Logger has at least one StreamHandler."""
        logger = setup_logging("test_handler")
        handler_types = [type(h) for h in logger.handlers]
        assert logging.StreamHandler in handler_types

    def test_file_handler_created(self, tmp_path: Path) -> None:
        """File handler is created when log file is configured."""
        log_file = str(tmp_path / "test.log")
        mock_config = {
            "logging": {
                "level": "INFO",
                "format": "%(message)s",
                "file": log_file,
            }
        }
        with patch("src.utils.logger.load_config", return_value=mock_config):
            logger = setup_logging("test_file_handler")
            handler_types = [type(h) for h in logger.handlers]
            assert logging.FileHandler in handler_types

    def test_no_duplicate_handlers(self) -> None:
        """Calling setup_logging twice does not duplicate handlers."""
        name = "test_no_dup"
        logger1 = setup_logging(name)
        count1 = len(logger1.handlers)
        logger2 = setup_logging(name)
        assert len(logger2.handlers) == count1

    def test_fallback_on_missing_config(self) -> None:
        """Logger works even if config file is missing."""
        with patch(
            "src.utils.logger.load_config", side_effect=FileNotFoundError("missing")
        ):
            logger = setup_logging("test_fallback")
            assert isinstance(logger, logging.Logger)
            assert logger.level == logging.INFO
