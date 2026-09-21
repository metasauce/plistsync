"""Playlist management commands for a service.

Each command lives in its own module; this package only wires them together
into a :class:`typer.Typer` command group.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from .create import register_create_command
from .list import register_list_command
from .remove import register_remove_command
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

    register_list_command(app)
    register_create_command(app, library_cls)
    register_remove_command(app)
    register_update_command(app, library_cls)

    return app
