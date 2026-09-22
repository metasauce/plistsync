"""Playlist management commands for a service.

Each command lives in its own module; this package only wires them together
into a :class:`typer.Typer` command group.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from plistsync.cli.service_commands.search.playlist import (
    register_playlist_search_command,
)

from .create import register_create_command
from .list import register_list_command
from .remove import register_remove_command
from .show import register_show_command
from .update import register_update_command

if TYPE_CHECKING:
    from plistsync.core import Library


def playlist_command_factory(library_cls: type[Library]) -> typer.Typer:
    """Build the ``playlist`` command group for a library."""
    app = typer.Typer(
        name="playlist",
        help="Manage playlists in the service library.",
        no_args_is_help=True,
    )

    # Library Gate: Capability checks happen during registration.
    # Thus, commands that check library capa need the class, to not rely on an instance
    register_list_command(app)
    register_create_command(app, library_cls)
    register_remove_command(app)
    register_update_command(app, library_cls)
    register_show_command(app)

    # Alias: `playlist search` is the same as `search playlist`
    register_playlist_search_command(app, command_name="search")

    return app
