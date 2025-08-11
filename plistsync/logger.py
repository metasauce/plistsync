import logging

from plistsync.config import Config

log = logging.getLogger("plistsync")

# Get logging level from configuration or default to INFO
DEFAULT_LOG_LEVEL = "INFO"
log.setLevel(Config().logging_level.upper() or DEFAULT_LOG_LEVEL)

# Set all other loggers to warning level by default
logging.basicConfig(level=logging.WARNING)


def overwrite_log_level(level: str) -> None:
    """Overwrite the log level of the logger."""
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")
    log.setLevel(numeric_level)
    logging.basicConfig(level=numeric_level)
    log.debug(f"Log level set to {level}")
