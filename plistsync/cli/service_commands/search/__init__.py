"""Track and playlist search commands for a service library."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from .playlist import register_playlist_search_command
from .track import register_track_search_command

if TYPE_CHECKING:
    from plistsync.core import Library


def search_command_factory(library_cls: type[Library]) -> typer.Typer:
    """Build the ``search`` command group for a library."""
    app = typer.Typer(
        name="search",
        help="Search for tracks or playlists in the service library.",
        no_args_is_help=True,
    )

    # Library Gate: Capability checks happen during registration.
    # Thus, commands that check library capa need the class, to not rely on an instance
    register_playlist_search_command(app)
    register_track_search_command(app, library_cls)

    return app


__all__ = ["search_command_factory"]
