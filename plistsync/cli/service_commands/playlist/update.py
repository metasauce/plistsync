"""``playlist update`` command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer
from rich.markup import escape

from plistsync.cli.context import (
    ServiceCommandContext,  # noqa: TC001 (typer resolves it at runtime)
)
from plistsync.cli.options import (
    AddTrackOption,  # noqa: TC001 (typer resolves it at runtime)
    YesOption,  # noqa: TC001 (typer resolves it at runtime)
    without_param,
)
from plistsync.cli.parsing import (
    autocompletion_playlist,
    parse_playlist,
    parse_track_id,
)
from plistsync.cli.visualization import confirm_or_abort, stdout_console, to_rich
from plistsync.core.collection import IDLookup
from plistsync.core.diff import list_diff
from plistsync.errors import HowTheForkDidYouEndUpHereError
from plistsync.logger import log

if TYPE_CHECKING:
    from plistsync.core import Library, ServicePlaylist, Track, TrackID
    from plistsync.services import Service


def resolve_remove(
    value: str, playlist: ServicePlaylist, service: Service
) -> tuple[Track, int]:
    """Resolve a track to remove from a playlist, given a string identifier.

    Returns a tuple of the track to remove and its index in the playlist.
    """
    # Index parsing (bare integers are interpreted as zero-based playlist indexes)
    if value.isdecimal():
        index = int(value)

        if not 0 <= index < len(playlist.tracks):
            raise typer.BadParameter(
                f"playlist index out of range: {index}",
                param_hint="--remove",
            )

        return playlist.tracks[index], index

    # Track id parsing
    if track_id := parse_track_id(value, service):
        for idx, track in enumerate(playlist.tracks):
            if track_id in track.ids:
                return track, idx

        raise typer.BadParameter(
            f"track {track_id.serial!r} not found in playlist",
            param_hint="--remove",
        )

    raise typer.BadParameter(
        f"track {value!r} is not present in playlist {playlist.name!r}",
        param_hint="--remove",
    )


def _autocompletion_playlist(ctx: ServiceCommandContext, incomplete: str) -> list[str]:
    library = ctx.obj.library
    if library is None:
        return []

    return autocompletion_playlist(incomplete, library)


def register_update_command(app: typer.Typer, library_cls: type[Library]) -> None:
    """Register the ``update`` command on the playlist command group.

    The ``--add`` option is only offered if the library supports
    :class:`~plistsync.core.collection.IDLookup`.
    """

    def update(
        ctx: ServiceCommandContext,
        playlist: str = typer.Argument(
            ...,
            help="Playlist to update (name, serial, URL or URI).",
            autocompletion=_autocompletion_playlist,
        ),
        add: AddTrackOption = None,
        remove: Annotated[
            list[str] | None,
            typer.Option(
                "--remove",
                "-r",
                help="Track to remove: playlist index, URI, or URL. "
                "Bare integers are interpreted as zero-based playlist indexes. "
                "Can be specified multiple times. "
                "The first matching playlist track is removed for each identifier.",
            ),
        ] = None,
        yes: YesOption = False,
    ) -> None:
        """Add and/or remove tracks of a playlist."""
        service_name = ctx.obj.name
        library = ctx.obj.library

        if library is None:
            raise HowTheForkDidYouEndUpHereError(
                f"Service {service_name!r} provides no library, but the 'update'"
                "command was invoked."
            )

        console = stdout_console()
        service_playlist = parse_playlist(playlist, library)
        if service_playlist is None:
            raise typer.BadParameter(f"No playlist found matching {playlist!r}.")

        snapshot = service_playlist.get_snapshot()

        # Check if removes exist in pl (just iter here should be small number)
        to_remove = [
            resolve_remove(r, service_playlist, ctx.obj.service) for r in remove or []
        ]
        # Sort by index descending so we can remove by index without invalidating
        # the next index
        to_remove.sort(key=lambda x: x[1], reverse=True)
        for _, index in to_remove:
            service_playlist.tracks.pop(index)

        # Add tracks
        to_add: list[TrackID] = []
        for track_id_str in add or []:
            if track_id := parse_track_id(track_id_str, ctx.obj.service):
                to_add.append(track_id)
            else:
                log.warning(
                    f"Could not parse track identifier {track_id_str!r}. Skipping."
                )
        if to_add:
            if not isinstance(service_playlist.library, IDLookup):
                # Unreachable via the CLI: register_update_command removes --add
                # for libraries without IDLookup.
                raise HowTheForkDidYouEndUpHereError(
                    f"{ctx.obj.service.name} does not support adding tracks "
                    "by track identifier."
                )
            for track, track_id in zip(
                service_playlist.library.find_many_by_ids([[id] for id in to_add]),
                to_add,
            ):
                if track is None:
                    log.warning(
                        f"Could not find track {track_id.serial!r} in library. "
                        "Skipping."
                    )
                else:
                    service_playlist.tracks.append(track)

        confirm_or_abort(
            console,
            f"Updating playlist [bold]{escape(repr(service_playlist.name))}[/bold] "
            f"(id: [cyan]{service_playlist.id.serial}[/cyan]).",
            to_rich(
                list_diff(
                    snapshot.tracks, service_playlist.tracks, key_func=lambda t: t
                )
            ),
            yes=yes,
            default=False,
        )

        # Commit changes
        service_playlist.update()

    if not issubclass(library_cls, IDLookup):
        without_param(update, "add")

    app.command(name="update")(update)
