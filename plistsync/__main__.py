"""Cli entry point."""

import importlib

import typer
from eyconf.cli import create_config_cli

from .config import Config
from .errors import DependencyError
from .logger import log, overwrite_log_level

cli = typer.Typer(
    rich_markup_mode="rich",
    help="Command line tool for [bold italic]plistsync[/bold italic].",
    pretty_exceptions_show_locals=False,
)


def register_apps(cli: typer.Typer):
    """Register subcommands.

    To allow partial dependencies we only register cli if the import is sucessfull.
    """

    imports_ = {
        "plistsync.services.plex.authenticate": "plex_cli",
        "plistsync.services.spotify.authenticate": "spotify_cli",
        "plistsync.services.tidal.authenticate": "tidal_cli",
    }

    for module_name, obj_name in imports_.items():
        try:
            module = importlib.import_module(module_name)
            cli.add_typer(getattr(module, obj_name), name=obj_name.replace("_cli", ""))
        except DependencyError:
            # TODO: register subcommand (should not be shown in help)
            # prints message how to install service
            log.debug(
                f"Skipping '{module_name}.{obj_name}' due to missing dependencies."
            )


register_apps(cli)
cli.add_typer(create_config_cli(Config), name="config")


# Add global verbose option
@cli.callback()
def select_verbose(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output."),
):
    if verbose:
        overwrite_log_level("DEBUG")


if __name__ == "__main__":
    cli()
