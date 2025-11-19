"""Plistsync configuration management using YAML files.

We use the `eyconf` library to handle configuration loading and validation.
For more information see `EYConf <https://github.com/semohr/eyconf>`_.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Optional

from eyconf import EYConf
from eyconf.validation import ConfigurationError
from typing_extensions import Literal

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
    server_url: str = field(default="http://localhost:32400")


@dataclass
class TidalConfig(OptionalService):
    client_id: str = field(default="XhEgdcjkjfqTqw1y")
    client_secret: str | None = None


@dataclass
class SpotifyConfig(OptionalService):
    client_id: str = field(default="3b408bca2c3344dfa1cda1c7fa9adde4")
    client_secret: str | None = None


@dataclass
class ServicesConfig:
    beets: BeetsConfig = field(default_factory=BeetsConfig)
    plex: PlexConfig = field(default_factory=PlexConfig)
    tidal: TidalConfig = field(default_factory=TidalConfig)
    spotify: SpotifyConfig = field(default_factory=SpotifyConfig)


@dataclass
class LoggingConfig:
    level: Annotated[
        Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        "Logging level can be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL",
        "For production we recommend INFO or higher",
    ] = field(default="INFO")


@dataclass
class ConfigSchema:
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    services: Annotated[
        ServicesConfig,
        "Optional services:",
        "plistsync works without any of the services but using",
        "some of them will improve matching tremendously",
        "See the setup guide for more information!",
    ] = field(default_factory=ServicesConfig)

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
        super().__init__(ConfigSchema)

    @property
    def logging_level(self) -> str:
        return getattr(self._data.logging, "level", "INFO")

    @staticmethod
    def get_dir() -> Path:
        """Get the path to the config directory."""
        c_dir = Path(os.getenv("PSYNC_CONFIG_DIR", "./config"))
        os.makedirs(c_dir, exist_ok=True)
        return c_dir.resolve()

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
    def redirect_port(self) -> int:
        return self.data.redirect_port


__all__ = [
    "Config",
]
