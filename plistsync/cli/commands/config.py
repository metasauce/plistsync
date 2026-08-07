"""Config command group."""

from eyconf.cli import create_config_cli

from plistsync.config import Config

config_app = create_config_cli(Config)
