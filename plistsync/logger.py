import logging
import os

from plistsync.config import Config, LoggingConfig

log = logging.getLogger("plistsync")


def _logging_config(config: Config | None) -> LoggingConfig:
    """Parse logging config values."""
    logging_config = LoggingConfig() if config is None else config.data.logging

    # Allow to disable with env variable
    env_enabled: str | None = os.getenv("PLSYNC_LOGGING")
    if env_enabled is not None:
        logging_config.enabled = env_enabled.lower() in ("true", "1", "t")

    return logging_config


def _parse_log_level(level: str | int) -> int:
    if isinstance(level, int):
        return level
    return logging.getLevelNamesMapping().get(level.upper(), logging.INFO)


def set_log_level(level: str | int) -> None:
    """Overwrite the log level of the plistsync logger (does not configure root)."""
    log.setLevel(_parse_log_level(level))


def init_logging(
    config: Config | None = None,
    level_overwrite: str | int | None = None,
) -> None:
    """Initialize plistsync logging from config. Call from CLI/app, not at import."""
    logging_config = _logging_config(config)
    if not logging_config.enabled:
        return

    # set level of log from config or use overwrite
    set_log_level(logging_config.level if level_overwrite is None else level_overwrite)

    # setup handler(s) from config
    handlers: list[logging.Handler] | None = None
    match logging_config.handler:
        case "rich":
            handlers = [rich_logging_handler()]
        case "basic":
            handlers = [basic_logging_handler()]

    if handlers is not None:
        logging.basicConfig(handlers=handlers, force=True)

    if log.isEnabledFor(logging.DEBUG):
        log.debug(
            "Initialized logging: handler=%s, level=%s",
            logging_config.handler,
            logging.getLevelName(log.getEffectiveLevel()),
        )


def basic_logging_handler(
    fmt: str | None = None,
) -> logging.Handler:
    """Setup logging using stdlib.

    Parameters
    ----------
    fmt: str, optional
        Format string for the log messages. Defaults to "time levelname name message"
    level: str, optional
        Overwrite log level (e.g., "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
        If not given will use the config value.
    """  # noqa: D401
    fmt = fmt or "%(asctime)s %(levelname)s %(name)s: %(message)s"

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    handler.name = "basic"
    return handler


def rich_logging_handler(
    fmt: str | None = None,
) -> logging.Handler:
    """Setup logging using rich.

    Registers a rich logging handler for beautiful log messages.

    Parameters
    ----------
    fmt: str, optional
        Format string for the log messages. Defaults to "time levelname name message"
    level: str, optional
        Overwrite log level (e.g., "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
        If not given will use the config value.
    """  # noqa: D401
    from rich.console import Console
    from rich.highlighter import NullHighlighter
    from rich.logging import RichHandler

    fmt = fmt or "%(message)s"
    handler = RichHandler(
        console=Console(),
        markup=False,
        tracebacks_max_frames=1,
        tracebacks_show_locals=False,
        show_path=False,
        show_level=True,
        show_time=True,
        highlighter=NullHighlighter(),
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.name = "rich"
    return handler


init_logging(Config() if Config.exists() else None)
