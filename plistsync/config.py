"""Plistsync configuration management using YAML files.

We use the `eyconf` library to handle configuration loading and validation.
For more information see `EYConf <https://github.com/semohr/eyconf>`_.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal

from eyconf import EYConf
from eyconf.validation import ConfigurationError
from platformdirs import user_config_dir

# ---------------------------------------------------------------------------- #
#                                 Config schema                                #
# ---------------------------------------------------------------------------- #


@dataclass
class OptionalService:
    enabled: bool = field(default=False)


@dataclass
class BeetsConfig(OptionalService):
    database: str = field(default="./config/beets/beets.db")


@dataclass
class PlexConfig(OptionalService):
    server_url: Annotated[
        str | None,
        "The URL of the Plex server to connect to by default.",
        "E.g. 'http://localhost:32400' or 'https://plex.mydomain.com'",
    ] = field(default=None)

    server_name: Annotated[
        str | None,
        "Instead of the server url, you can specify its name and we look it up online ",
        "via plex.tv. In this case, we try local routes first.",
        "E.g. 'my_plex_server'",
    ] = field(default=None)

    @property
    def app_name(self) -> str:
        return "plistsync-local"

    @property
    def client_identifier(self) -> str:
        # Random generated UUID, we could generate this for each
        # user but it is not strictly necessary and one global
        # id might allow us profiling across installs in the future.
        return "510457cfb15e4bf48d34563d0e4f1de1"

    @property
    def token_path(self) -> Path:
        return Config.get_dir() / "plex_token.json"


@dataclass
class TidalConfig(OptionalService):
    client_id: str = field(default="XhEgdcjkjfqTqw1y")
    client_secret: str | None = None
    country_code: str = field(default="US")


@dataclass
class SpotifyConfig(OptionalService):
    client_id: str = field(default="3b408bca2c3344dfa1cda1c7fa9adde4")
    client_secret: str | None = None


@dataclass
class TraktorConfig(OptionalService):
    backup_before_write: Annotated[
        bool,
        "Create a backup of the libraries nml file before every write.",
    ] = field(default=True)


@dataclass
class ServicesConfig:
    beets: BeetsConfig | None = field(default_factory=lambda: BeetsConfig())
    plex: PlexConfig | None = field(default_factory=lambda: PlexConfig())
    tidal: TidalConfig | None = field(default_factory=lambda: TidalConfig())
    spotify: SpotifyConfig | None = field(default_factory=lambda: SpotifyConfig())
    traktor: TraktorConfig | None = field(default_factory=lambda: TraktorConfig())


@dataclass
class LoggingConfig:
    enabled: Annotated[
        bool,
        "Whether plistsync should configure logging automatically at startup.",
        "Set to False if you want to configure logging yourself (e.g., your "
        "app/CLI/framework already sets handlers/formatters).",
    ] = field(default=True)
    level: Annotated[
        Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "NOTSET"],
        "Log level to set when `enabled=True` (one of: DEBUG, INFO, WARNING, ERROR,"
        "CRITICAL, NOTSET); INFO is recommended for production, DEBUG is useful for "
        "troubleshooting.",
    ] = field(default="INFO")
    handler: Annotated[
        Literal["basic", "rich"],
        "Logging backend to initialize when `enabled=True`: 'basic' uses standard "
        "library logging with plain text output to stderr, while 'rich' uses "
        "RichHandler for nicer console formatting (and richer tracebacks if enabled).",
    ] = field(default="rich")


@dataclass
class ConfigSchema:
    logging: LoggingConfig = field(default_factory=lambda: LoggingConfig())

    services: Annotated[
        ServicesConfig,
        "Optional services:",
        "plistsync works without any of the services but using",
        "some of them will improve matching tremendously",
        "See the setup guide for more information!",
    ] = field(default_factory=lambda: ServicesConfig())

    redirect_port: Annotated[
        int,
        "The port used for authentication callbacks",
    ] = field(default=5001)


# ---------------------------------------------------------------------------- #
#                                 Config class                                 #
# ---------------------------------------------------------------------------- #
# Uses the eyconf library to handle configuration


class Config(EYConf[ConfigSchema]):
    """Plistsync configuration class.

    This class is responsible for loading and validating the configuration.
    For more information see `EYConf <https://github.com/semohr/eyconf>`_.
    """

    def __init__(self):
        from .logger import log

        log.debug(f"Using config dir: {self.get_dir()}")
        super().__init__(ConfigSchema)

    @staticmethod
    def _get_global_config_dir() -> Path:
        """Get OS-specific global config directory."""
        base = Path(user_config_dir("plistsync", appauthor=False))
        return base

    @staticmethod
    def get_dir() -> Path:
        """Get the path to the config directory.

        We check if the following folders exist to
        determine the config directory:

        1. PSYCNC_CONFIG_DIR environment variable
        2. OS-specific global config directory
        """
        if env_dir := os.getenv("PSYNC_CONFIG_DIR"):
            path = Path(env_dir)
        else:
            path = Config._get_global_config_dir()

        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    @staticmethod
    def get_file() -> Path:
        """Get the path to the config file."""
        path = Config.get_dir() / "config.yml"
        return path

    @staticmethod
    def exists() -> bool:
        """Check if the config file exists."""
        return Config.get_file().exists()

    # ---------------------------------------------------------------------------- #
    #                         Services/ Optional Extensions                        #
    # ---------------------------------------------------------------------------- #
    @property
    def plex(self) -> PlexConfig:
        if not self.data.services.plex or not self.data.services.plex.enabled:
            raise ConfigurationError(
                "'plex' is not enabled or missing in the configuration."
            )
        return self.data.services.plex

    @property
    def beets(self) -> BeetsConfig:
        if not self.data.services.beets or not self.data.services.beets.enabled:
            raise ConfigurationError(
                "'beets' is not enabled or missing in the configuration."
            )
        return self.data.services.beets

    @property
    def tidal(self) -> TidalConfig:
        if not self.data.services.tidal or not self.data.services.tidal.enabled:
            raise ConfigurationError(
                "'tidal' is not enabled or missing in the configuration."
            )
        return self.data.services.tidal

    @property
    def spotify(self) -> SpotifyConfig:
        if not self.data.services.spotify or not self.data.services.spotify.enabled:
            raise ConfigurationError(
                "'spotify' is not enabled or missing in the configuration."
            )
        return self.data.services.spotify

    @property
    def traktor(self) -> TraktorConfig:
        if not self.data.services.traktor or not self.data.services.traktor.enabled:
            raise ConfigurationError(
                "'traktor' is not enabled or missing in the configuration."
            )
        return self.data.services.traktor

    @property
    def redirect_port(self) -> int:
        return self.data.redirect_port


__all__ = [
    "Config",
]
