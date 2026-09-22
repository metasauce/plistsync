"""Config command group."""

from eyconf.cli import create_config_cli

from plistsync.cli.config import Config

config_app = create_config_cli(Config)
