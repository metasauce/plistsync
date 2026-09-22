"""``search track`` command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from plistsync.cli.context import (
    ServiceCommandContext,  # noqa: TC001 (typer resolves it at runtime)
)
from plistsync.cli.options import without_param
from plistsync.core.collection import IDLookup, InfoLookup
from plistsync.core.ids import ISRC
from plistsync.errors import HowTheForkDidYouEndUpHereError
from plistsync.logger import log

if TYPE_CHECKING:
    from plistsync.core import Library, Track, TrackID, TrackInfo


def register_track_search_command(app: typer.Typer, library_cls: type[Library]) -> None:
    """Register the ``track`` search command with capability-based options."""
    supports_ids = issubclass(library_cls, IDLookup)
    supports_info = issubclass(library_cls, InfoLookup)

    def search_track(
        ctx: ServiceCommandContext,
        arg: Annotated[
            str | None,
            typer.Argument(help="Service track ID or URL."),
        ] = None,
        track_id: Annotated[
            str | None,
            typer.Option("--id", help="ID: service track ID or URL."),
        ] = None,
        isrc: Annotated[
            str | None,
            typer.Option(
                "--isrc",
                help="ID: International Standard Recording Code.",
            ),
        ] = None,
        title: Annotated[
            str | None,
            typer.Option(help="Metadata: Track title."),
        ] = None,
        artist: Annotated[
            str | None,
            typer.Option(help="Metadata: First (main) artist."),
        ] = None,
        album: Annotated[
            str | None,
            typer.Option(help="Metadata: Album of the track."),
        ] = None,
        max_results: Annotated[
            int,
            typer.Option(
                "--max-results",
                "-n",
                min=1,
                help="Maximum number of tracks to return.",
            ),
        ] = 5,
    ) -> None:
        """Search for a track using IDs or metadata.

        Results for IDs take precedence.
        """
        library = ctx.obj.library
        if library is None:
            raise HowTheForkDidYouEndUpHereError(
                f"Service {ctx.obj.name!r} provides no library, but the "
                "'search track' command was invoked."
            )

        ids: list[TrackID] = []
        if isrc is not None:
            try:
                ids.append(ISRC.parse(isrc))
            except ValueError as exc:
                raise typer.BadParameter(str(exc), param_hint="--isrc") from exc

        id_value = track_id or arg
        if id_value is not None:
            for track_id_cls in ctx.obj.service.track_ids():
                try:
                    ids.append(track_id_cls.parse(id_value))
                    break
                except ValueError:
                    continue
            else:
                raise typer.BadParameter(
                    f"Invalid track ID for {ctx.obj.name}: {id_value!r}",
                    param_hint="--id",
                )

        tracks: list[Track] = []
        if ids:
            log.debug(f"Looking up track by IDs: {ids!r}")
            id_track = library.find_by_ids(ids)  # type: ignore[attr-defined]
            if id_track is not None:
                tracks.append(id_track)

        if (
            any(value is not None for value in (title, artist, album))
            and len(tracks) < max_results
        ):
            info: TrackInfo = {}
            if title is not None:
                info["title"] = title
            if artist is not None:
                info["artists"] = [artist]
            if album is not None:
                info["albums"] = [album]

            log.debug(f"Looking up track by metadata: {info!r}")
            metadata_tracks = library.find_by_info(info)  # type: ignore[attr-defined]
            for track in metadata_tracks:
                tracks.append(track)
                if len(tracks) == max_results:
                    break

        for track in tracks:
            typer.echo(f"{track.ids!r} {track!r}")

    if not supports_ids:
        without_param(search_track, "arg")
        without_param(search_track, "track_id")
        without_param(search_track, "isrc")
    if not supports_info:
        without_param(search_track, "title")
        without_param(search_track, "artist")
        without_param(search_track, "album")

    app.command(name="track", no_args_is_help=True)(search_track)
