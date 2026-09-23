"""``search track`` command."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from plistsync.cli.context import (
    ServiceCommandContext,  # noqa: TC001 (typer resolves it at runtime)
)
from plistsync.cli.options import without_param
from plistsync.cli.parsing import parse_track_id
from plistsync.cli.visualization import render_tracks, stdout_console
from plistsync.core.collection import IDLookup, InfoLookup
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
            typer.Argument(help="Track identifier. One of id, uri, url or isrc."),
        ] = None,
        track_ids: Annotated[
            list[str] | None,
            typer.Option(
                "--id",
                help="Track identifier. One of id, uri, url or isrc. Can be "
                "given multiple times and will try to find one matching track "
                "given the identifiers.",
            ),
        ] = None,
        # Metadata
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
        service_name = ctx.obj.name
        library = ctx.obj.library

        if library is None:
            raise HowTheForkDidYouEndUpHereError(
                f"Service {service_name!r} provides no library, but the "
                "'search track' command was invoked."
            )

        ids: list[TrackID] = []
        for value in [arg, *(track_ids or [])]:
            if value is None:
                continue
            track_id = parse_track_id(value, ctx.obj.service)
            if track_id is None:
                raise typer.BadParameter(
                    f"Invalid track ID for {service_name}: {value!r}",
                    param_hint="--id",
                )
            ids.append(track_id)

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

        stdout_console().print(render_tracks(tracks, title=f"{service_name} tracks"))

    if not supports_ids:
        without_param(search_track, "arg")
        without_param(search_track, "track_ids")
    if not supports_info:
        without_param(search_track, "title")
        without_param(search_track, "artist")
        without_param(search_track, "album")

    app.command(name="track", no_args_is_help=True)(search_track)
