"""Cli entry point."""

import typer
from eyconf.cli import create_config_cli

from .config import Config
from .logger import log, overwrite_log_level
from .services.tidal.authenticate import tidal_cli

cli = typer.Typer(
    rich_markup_mode="rich",
    help="Command line tool for [bold italic]plistsync[/bold italic].",
    pretty_exceptions_show_locals=False,
)

cli.add_typer(tidal_cli, name="tidal")
cli.add_typer(create_config_cli(Config), name="config")


@cli.command()
def echo(
    message: str = typer.Argument(
        "Hello, World!", help="The message to echo back to the user."
    ),
):
    """Echo a message back to the user."""
    log.debug(f"Echoing message: {message}")
    typer.echo(message)


# Add global verbose option
@cli.callback()
def select_verbose(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output."),
):
    if verbose:
        overwrite_log_level("DEBUG")


if __name__ == "__main__":
    cli()
