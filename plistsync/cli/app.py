"""Root typer application with lazy service command groups."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated

import typer
from rich.logging import RichHandler
from typer.core import TyperGroup
from typer.main import get_group

from plistsync.config import Config
from plistsync.logger import basic_logging_handler, init_logging, log
from plistsync.services import ServiceLoader

from .commands.config import config_app
from .commands.sync import sync_app
from .service_commands import cli_service_factory

if TYPE_CHECKING:
    from collections.abc import Iterable

    import click

    from plistsync.config import LoggingConfig


class ServiceGroup(TyperGroup):
    """Service command group that imports the service on first access.

    Instances are built from entry point names only, so listing services in
    the help is cheap. Importing the service module is deferred until one of
    its commands (or its help) is requested.
    """

    _loaded: bool = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        service = ServiceLoader.get(self.name or "")
        if service is None:
            return

        # Attach the service app's commands to this placeholder once loaded.
        service_app = get_group(cli_service_factory(service))
        self.commands.update(service_app.commands)

    def list_commands(self, ctx: click.Context) -> list[str]:
        self._load()
        return super().list_commands(ctx)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        self._load()
        return super().get_command(ctx, cmd_name)


class LazyServiceGroup(TyperGroup):
    """Root command group that discovers service groups on demand.

    This allows the CLI to be imported without importing all service modules,
    this keeps our cli fast and avoids importing service modules just to check if they
    exist, which is slow.
    """

    def _register_services(self, names: Iterable[str]) -> None:
        for name in names:
            if name in self.commands:
                continue
            self.add_command(
                ServiceGroup(
                    name=name,
                    help=f"Commands for the {name} service.",
                    no_args_is_help=True,
                )
            )

    def list_commands(self, ctx: click.Context) -> list[str]:
        """Register all available services (for help and completion)."""
        self._register_services(ServiceLoader.list_all())
        return super().list_commands(ctx)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        """Register the requested service placeholder, or all for suggestions."""
        names = ServiceLoader.list_all()
        if cmd_name in names:
            self._register_services([cmd_name])
        elif cmd_name not in self.commands:
            # Unknown command: register service names so typos can be suggested.
            self._register_services(names)
        return super().get_command(ctx, cmd_name)


app = typer.Typer(
    rich_markup_mode="rich",
    help="Command line tool for [bold italic]plistsync[/bold italic].",
    pretty_exceptions_show_locals=False,
    no_args_is_help=True,
    cls=LazyServiceGroup,
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
    services = ServiceLoader.list_all()

    svc_str = ", ".join(services) if services else "none"
    typer.echo(f"plistsync: {ver}  ({svc_str})")
    raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    verbose: Annotated[
        int | None,
        typer.Option(
            "--verbose",
            "-v",
            count=True,
            callback=logging_callback,
            help="Increase verbosity.",
        ),
    ] = None,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            callback=version_callback,
            help="Currently installed version.",
        ),
    ] = None,
) -> None:
    """Global callback — handles --verbose and --version flags."""


app.add_typer(config_app, name="config")
app.add_typer(sync_app)
