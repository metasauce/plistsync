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


class TestLevelFromConfig:
    def test_level_from_config_none_returns_info(self):
        assert logger._level_from_config(None) == logging.INFO

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING"])
    def test_level_from_config_with_config(self, level):
        config = MagicMock()
        config.logging_level = level
        assert logger._level_from_config(config) == logging.getLevelNamesMapping().get(
            level
        )


class TestSetLogLevel:
    def test_set_log_level_string(self):
        initial_level = logger.log.getEffectiveLevel()
        logger.set_log_level("DEBUG")
        assert logger.log.getEffectiveLevel() == logging.DEBUG
        logger.set_log_level(initial_level)

    def test_set_log_level_integer(self):
        initial_level = logger.log.getEffectiveLevel()
        logger.set_log_level(logging.WARNING)
        assert logger.log.getEffectiveLevel() == logging.WARNING
        logger.set_log_level(initial_level)


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
    def test_init_logging_no_config_no_overwrite(self, monkeypatch):
        monkeypatch.setattr("plistsync.logger.Config.exists", lambda: False)
        monkeypatch.setattr(
            "plistsync.logger._level_from_config", lambda c: logging.INFO
        )
        logger.init_logging()
        assert logger.log.getEffectiveLevel() == logging.INFO

    @pytest.mark.parametrize("handler_type", ["basic", "rich"])
    def test_init_logging_with_handler(self, handler_type, monkeypatch):
        config = MagicMock()
        config.data.logging.handler = handler_type
        monkeypatch.setattr(
            "plistsync.logger._level_from_config", lambda c: logging.INFO
        )
        logger.init_logging(config=config)
        assert logging.root.handlers

    def test_init_logging_debug_log(self, monkeypatch):
        config = MagicMock()
        config.data.logging.handler = "basic"
        monkeypatch.setattr(
            "plistsync.logger._level_from_config", lambda c: logging.DEBUG
        )
        monkeypatch.setattr(
            logger.log, "isEnabledFor", lambda level: level == logging.DEBUG
        )
        monkeypatch.setattr(logger.log, "debug", MagicMock())
        logger.init_logging(config=config)
        assert logger.log.debug.called  # type: ignore
