"""Plistsync configuration management using YAML files.

We use the `eyconf` library to handle configuration loading and validation.
For more information see `EYConf <https://github.com/semohr/eyconf>`_.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eyconf import EYConf
from eyconf.validation import ConfigurationError

# ---------------------------------------------------------------------------- #
#                                 Config schema                                #
# ---------------------------------------------------------------------------- #


@dataclass
class OptionalService:
    enabled: bool


@dataclass
class BeetsConfig(OptionalService):
    database: str


@dataclass
class PlexConfig(OptionalService):
    server_url: str
    auth_token: str
    machine_id: str


@dataclass
class TidalConfig(OptionalService):
    client_id: str
    redirect_port: int
    client_secret: Optional[str] = None
    country_code: Optional[str] = "DE"


@dataclass
class SpotifyConfig(OptionalService):
    client_id: str
    redirect_port: int
    client_secret: Optional[str] = None


@dataclass
class LoggingConfig:
    level: str = field(default="INFO")


@dataclass
class ConfigSchema:
    logging: Optional[LoggingConfig] = field(default_factory=LoggingConfig)

    beets: Optional[BeetsConfig] = None
    plex: Optional[PlexConfig] = None
    tidal: Optional[TidalConfig] = None
    spotify: Optional[SpotifyConfig] = None


# ---------------------------------------------------------------------------- #
#                                 Default yaml                                 #
# ---------------------------------------------------------------------------- #


default = """
# Logging level can be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
# For production we recommend INFO or higher
logging:
    level: INFO


# Optional services:
# The sync should work without these services but using some
# of them will improve matching tremendously
# See the setup guide for more information!
beets:
    enabled: false
    database: ./config/beets/beets.db
plex:
    enabled: false
    server_url: http://localhost:32400
    auth_token: place_your_token_here
    # TODO: automate machine id like tidal.
    machine_id: 'curl -X GET "http://localhost:32400/identity/?X-Plex-Token=your_auth_token"'
tidal:
    enabled: false
    client_id: XhEgdcjkjfqTqw1y
    redirect_port: 5001
spotify:
    enabled: false
    client_id: 3b408bca2c3344dfa1cda1c7fa9adde4
    redirect_port: 5001
"""


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

    def default_yaml(self) -> str:
        """Get the default YAML configuration."""
        return default

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
        if not self.data.plex or not self.data.plex.enabled:
            raise ConfigurationError(
                "'plex' is not enabled or missing in the configuration."
            )
        return self.data.plex

    @property
    def beets(self) -> BeetsConfig:
        if not self.data.beets or not self.data.beets.enabled:
            raise ConfigurationError(
                "'beets' is not enabled or missing in the configuration."
            )
        return self.data.beets

    @property
    def tidal(self) -> TidalConfig:
        if not self.data.tidal or not self.data.tidal.enabled:
            raise ConfigurationError(
                "'tidal' is not enabled or missing in the configuration."
            )
        return self.data.tidal

    @property
    def spotify(self) -> SpotifyConfig:
        if not self.data.spotify or not self.data.spotify.enabled:
            raise ConfigurationError(
                "'spotify' is not enabled or missing in the configuration."
            )
        return self.data.spotify


__all__ = [
    "Config",
]
