from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plistsync.config import LoggingConfig

log = logging.getLogger("plistsync")


def _parse_log_level(level: str | int) -> int:
    if isinstance(level, int):
        return level
    return logging.getLevelNamesMapping().get(level.upper(), logging.INFO)


def init_logging(
    config: LoggingConfig | None = None,
    log_level_offset: int | None = None,
) -> None:
    """Initialize plistsync logging from config. Call from CLI/app, not at import."""
    from plistsync.config import LoggingConfig

    logging_config = config or LoggingConfig()

    # set level of log from config or use overwrite
    log.setLevel(
        max(10, _parse_log_level(logging_config.level) - (log_level_offset or 0) * 10)
    )

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
