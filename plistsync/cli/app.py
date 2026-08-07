"""Root typer application, its global callback, and shared option callbacks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import typer
from rich.logging import RichHandler

from plistsync.config import Config
from plistsync.logger import basic_logging_handler, init_logging, log
from plistsync.services import ServiceLoader

from .commands.auth import auth_app
from .commands.config import config_app
from .commands.sync import sync_app

if TYPE_CHECKING:
    from plistsync.config import LoggingConfig

app = typer.Typer(
    rich_markup_mode="rich",
    help="Command line tool for [bold italic]plistsync[/bold italic].",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
)


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
    """Print installed version and available services, then exit.

    Parameters
    ----------
    value : bool
        Whether ``--version`` was passed.
    """
    if not value:
        return None

    from importlib.metadata import version

    ver = version("plistsync")
    services = [service for service in ServiceLoader.all().keys()]

    svc_str = ", ".join(services) if services else "none"
    typer.echo(f"plistsync: {ver}  ({svc_str})")
    raise typer.Exit()


@app.callback()
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
) -> None:
    """Global callback — handles --verbose and --version flags."""


app.add_typer(auth_app)
app.add_typer(config_app, name="config")
app.add_typer(sync_app)
