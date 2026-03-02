import logging
import os
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


class TestLoggingConfig:
    def test_level_logging_config_defaults(self):
        logging_config = logger._logging_config(None)
        assert logging_config.enabled
        assert logging_config.level == "INFO"
        assert logging_config.handler == "rich"

    @pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING"])
    def test_level_from_config_with_config(self, level):
        config = MagicMock()
        config.data.logging.level = level
        logging_config = logger._logging_config(config)
        assert logging_config.level == level

    def test_env_variable(self):
        os.environ["PLSYNC_LOGGING"] = "false"
        logging_config = logger._logging_config(None)
        assert not logging_config.enabled

        del os.environ["PLSYNC_LOGGING"]


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
        logger.init_logging()
        assert logger.log.getEffectiveLevel() == logging.INFO

    @pytest.mark.parametrize("handler_type", ["basic", "rich"])
    def test_init_logging_with_handler(self, handler_type):
        config = MagicMock()
        config.data.logging.handler = handler_type
        logger.init_logging(config=config)
        assert logging.root.handlers

    def test_init_logging_debug_log(self, monkeypatch):
        config = MagicMock()
        config.data.logging.handler = "basic"
        monkeypatch.setattr(
            logger.log, "isEnabledFor", lambda level: level == logging.DEBUG
        )
        monkeypatch.setattr(logger.log, "debug", MagicMock())
        logger.init_logging(config=config)
        assert logger.log.debug.called  # type: ignore

    def test_disabled(self, monkeypatch):
        mock = MagicMock()
        monkeypatch.setattr(logger, "set_log_level", mock)

        config = MagicMock()
        config.data.logging.enabled = False

        logger.init_logging(config=config)

        assert not mock.called  # type: ignore
