import logging
from unittest.mock import MagicMock

import pytest

from plistsync import logger


class TestParseLogLevel:
    @pytest.mark.parametrize(
        ("level", "expected"),
        [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
            ("debug", logging.DEBUG),
            ("info", logging.INFO),
            ("Debug", logging.DEBUG),
            ("InFo", logging.INFO),
            ("INVALID", logging.INFO),
            (logging.DEBUG, logging.DEBUG),
            (logging.INFO, logging.INFO),
            (25, 25),
        ],
    )
    def test_parse_log_level(self, level, expected):
        assert logger._parse_log_level(level) == expected


class TestBasicLoggingHandler:
    def test_basic_handler_default_format(self):
        handler = logger.basic_logging_handler()
        assert handler.name == "basic"
        assert isinstance(handler, logging.StreamHandler)

    def test_basic_handler_custom_format(self):
        fmt = "%(levelname)s - %(message)s"
        handler = logger.basic_logging_handler(fmt=fmt)
        assert handler.name == "basic"
        assert handler.formatter is not None
        assert handler.formatter._fmt == fmt


class TestRichLoggingHandler:
    def test_rich_handler_creates_handler(self):
        handler = logger.rich_logging_handler()
        assert handler.name == "rich"
        assert isinstance(handler, logging.Handler)


class TestInitLogging:
    def test_init_logging_no_config_no_overwrite(self):
        logger.init_logging()
        assert logger.log.getEffectiveLevel() == logging.INFO

    @pytest.mark.parametrize("handler_type", ["basic", "rich"])
    def test_init_logging_with_handler(self, handler_type):
        from plistsync.config import LoggingConfig

        logger.log.handlers.clear()
        config = LoggingConfig(handler=handler_type)
        logger.init_logging(config=config)
        assert logging.root.handlers

    def test_init_logging_debug_log(self, monkeypatch):
        from plistsync.config import LoggingConfig

        config = LoggingConfig(handler="basic")
        monkeypatch.setattr(
            logger.log, "isEnabledFor", lambda level: level == logging.DEBUG
        )
        monkeypatch.setattr(logger.log, "debug", MagicMock())
        logger.init_logging(config=config)
        assert logger.log.debug.called  # type: ignore

    def test_init_logging_unknown_handler(self):
        """When handler is unknown, no handlers are registered and init succeeds."""
        original_handlers = list(logging.root.handlers)
        config = MagicMock()
        config.handler = "unknown"
        config.level = "INFO"
        logger.init_logging(config=config)
        # Root handlers should remain unchanged since no new handler was registered
        assert logging.root.handlers == original_handlers
