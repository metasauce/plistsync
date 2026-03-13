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
    no_args_is_help=True,
)


def register_auth(cli: typer.Typer):
    """Register authentication subcommands.

    To allow partial dependencies we only register cli if the import is successful.
    """

    auth_app = typer.Typer(
        name="auth",
        help="Authentication for services.",
        no_args_is_help=True,
    )

    # Register auth su
    imports_ = {
        "plistsync.services.plex.authenticate:auth": "plex",
        "plistsync.services.spotify.authenticate:auth": "spotify",
        "plistsync.services.tidal.authenticate:auth": "tidal",
    }

    for module_str, name in imports_.items():
        module_name, func_name = module_str.split(":")
        try:
            module = importlib.import_module(module_name)
            auth_app.command(name=name)(getattr(module, func_name))
        except DependencyError:
            log.debug(
                f"Skipping '{module_name}.{func_name}' due to missing dependencies."
            )

    cli.add_typer(auth_app)


register_auth(cli)
cli.add_typer(create_config_cli(Config), name="config")


def logging_callback(verbose: int) -> None:
    level_mapping: dict[int, int] = {
        1: logging.INFO,
        2: logging.DEBUG,
        3: logging.DEBUG,  # debug incl. other modules with extended formatting
    }
    level = level_mapping.get(verbose)
    if level is None:
        return None

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
        return None

    if verbose >= 2:
        handler._log_render.show_path = True
        handler.tracebacks_show_locals = True
    else:
        from rich.traceback import install

        install(show_locals=False, extra_lines=0)

    if verbose >= 3:
        handler.setFormatter(logging.Formatter("%(name)-12s %(message)s"))

    log.debug("Adjusted log level to %s", logging.getLevelName(level))


def version_callback(value: bool) -> None:
    if not value:
        return None

    from importlib.metadata import version

    from .services import available_services

    ver = version("plistsync")
    services = [service.name.split(".")[-1] for service in available_services()]

    svc_str = ", ".join(services) if services else "none"
    typer.echo(f"plistsync: {ver}  ({svc_str})")
    raise typer.Exit()


@cli.callback()
def main(
    ctx: typer.Context,
    verbose: int | None = typer.Option(
        None,
        "--verbose",
        "-v",
        count=True,
        callback=logging_callback,
        help="Increase verbosity.",
    ),
    version: bool | None = typer.Option(
        None,
        "--version",
        callback=version_callback,
        help="Currently installed version.",
    ),
):
    pass


if __name__ == "__main__":
    cli()
