"""Cli entry point."""

import importlib
import logging

import typer
from eyconf.cli import create_config_cli
from rich.logging import RichHandler

from .config import Config
from .errors import DependencyError
from .logger import log, set_log_level

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
def logging_setup(
    verbose: int = typer.Option(
        -1, "--verbose", "-v", count=True, help="Increase verbosity."
    ),
) -> None:
    level_mapping: dict[int, int] = {
        1: logging.INFO,
        2: logging.DEBUG,
        3: logging.DEBUG,  # debug incl. other modules with extended formatting
    }
    level = level_mapping.get(verbose)
    if level is None:
        return

    # Only adjust levels; logging handlers were already configured at import time.
    set_log_level(level)
    if verbose >= 3:
        logging.getLogger().setLevel(level)  # enable other modules too

    # Adjust format
    root_logger = logging.getLogger()

    # FIXME: Can be upgraded to getHandlerByName once we
    # drop 3.11
    handler = next(
        (
            h
            for h in root_logger.handlers
            if isinstance(h, RichHandler)
            and (getattr(h, "name", None) in (None, "", "rich"))
        ),
        None,
    )
    if handler is None:
        return

    if verbose >= 2:
        handler._log_render.show_path = True
        handler.tracebacks_show_locals = True
    else:
        from rich.traceback import install

        install(show_locals=False, extra_lines=0)

    if verbose >= 3:
        handler.setFormatter(logging.Formatter("%(name)-12s %(message)s"))

    log.debug("Adjusted log level to %s", logging.getLevelName(level))


if __name__ == "__main__":
    cli()
