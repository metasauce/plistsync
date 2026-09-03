"""Cli entry point."""

import importlib
import logging
from typing import TYPE_CHECKING

import typer
from eyconf.cli import create_config_cli
from rich.logging import RichHandler

from plistsync.services import ServiceLoader

from .config import Config
from .errors import DependencyError
from .logger import basic_logging_handler, init_logging, log

if TYPE_CHECKING:
    from .config import LoggingConfig

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


# register_auth(cli)
cli.add_typer(create_config_cli(Config, preload_services=True), name="config")


def logging_callback(verbose: int | None) -> None:
    verbose = verbose or 0
    try:
        # Temporary handler so eyconf / third-party logs emitted during
        # Config() construction are captured with a decent format.
        # init_logging() below will replace this with the configured handler.
        logging.basicConfig(
            level=logging.WARNING,
            handlers=[basic_logging_handler()],
            force=True,
        )
        config: LoggingConfig | None = (
            Config().data.logging if Config.get_file().exists() else None
        )

    except Exception as e:
        log.debug("Failed to load config: %s", e)
        config = None

    init_logging(config, verbose)

    # Adjust format
    root_logger = logging.getLogger()

    if verbose >= 3:
        # set third-party libraries to debug level if verbose >= 3
        root_logger.setLevel(logging.DEBUG)
        log.debug(
            "Adjusted root logger level to %s", logging.getLevelName(root_logger.level)
        )

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


def version_callback(value: bool) -> None:
    if not value:
        return None

    from importlib.metadata import version

    ver = version("plistsync")
    services = [service for service in ServiceLoader.all().keys()]

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
