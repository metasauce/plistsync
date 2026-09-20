"""Search command factory and its terminal interaction.

Services with a library expose ``plistsync <service> search``.
"""

from __future__ import annotations

import re
from inspect import Signature
from typing import TYPE_CHECKING, Annotated

import typer

from plistsync.core.collection import IDLookup, InfoLookup
from plistsync.core.ids import ISRC
from plistsync.logger import log

from .utils import CLIParameters

if TYPE_CHECKING:
    from plistsync.core import Track, TrackID, TrackInfo
    from plistsync.services import Service


def search_typer_factory(service: Service):
    search_app = typer.Typer(
        name="search",
        help="Search the service.",
        pretty_exceptions_show_locals=False,
        no_args_is_help=True,
    )

    if library_cls := service.library():
        library = library_cls()
    else:
        return search_app

    # ---------------------------- Playlist Search --------------------------- #

    @search_app.command(name="playlist")
    def search_playlist(
        query: Annotated[
            str,
            typer.Argument(
                help="Generic query.",
            ),
        ],
    ):
        try:
            pattern = re.compile(query)
        except re.error as exc:
            raise typer.BadParameter(f"Invalid regular expression: {exc}") from exc

        for p in library.playlists:
            if pattern.search(p.name) or (
                p.description is not None and pattern.search(p.description)
            ):
                typer.echo(f"{p!r}")

    # ----------------------------- Track Search ----------------------------- #

    supports_info = isinstance(library, InfoLookup)
    supports_ids = isinstance(library, IDLookup)
    if not supports_info and not supports_ids:
        return search_app

    params = CLIParameters()

    if supports_ids:
        params.add_argument("arg", f"{service.name} track ID or URL.")
        params.add_option("id", f"ID: {service.name} track ID or URL.")
        params.add_option("isrc", "ID: International Standard Recording Code.")

    if supports_info:
        params.add_option("title", "Metadata: Track title.")
        params.add_option("artist", "Metadata: First (main) artist.")
        params.add_option("album", "Metadata: Album of the track.")

    params.add_option(
        "max_results",
        "Maximum number of tracks to return.",
        annotation=int,
        default=5,
        param_decls=("--max-results", "-n"),
        min=1,
    )

    def search_track(**kwargs: str | None):
        """Search for a track using IDs or metadata.

        Results for IDs take precedence.
        """
        title = kwargs.get("title")
        artist = kwargs.get("artist")
        album = kwargs.get("album")
        isrc = kwargs.get("isrc")
        id = kwargs.get("id") or kwargs.get("arg")
        max_results = int(kwargs.get("max_results", 3) or 3)

        # ID-based search takes precedence, but metadata can fill the remainder.
        ids: list[TrackID] = []
        if isrc is not None:
            try:
                ids.append(ISRC.parse(isrc))
            except ValueError as exc:
                raise typer.BadParameter(str(exc), param_hint="--isrc") from exc
        if id is not None:
            for track_id_cls in service.track_ids():
                try:
                    ids.append(track_id_cls.parse(id))
                    break
                except ValueError:
                    continue
            else:
                raise typer.BadParameter(
                    f"Invalid track ID for {service.name}: {id!r}",
                    param_hint="--id",
                )

        tracks: list[Track] = []
        if ids:
            log.debug(f"Look up track by IDs: {ids!r}")
            _id_track = library.find_by_ids(ids)  # type: ignore[attr-defined]
            if _id_track is not None:
                tracks.append(_id_track)

        # Metadata based search
        if (
            any(v is not None for v in (title, artist, album))
            and len(tracks) < max_results
        ):
            info: TrackInfo = {}
            if title is not None:
                info["title"] = title
            if artist is not None:
                info["artists"] = [artist]
            if album is not None:
                info["albums"] = [album]

            log.debug(f"Look up track by metadata: {info!r}")
            _meta_tracks = library.find_by_info(info)  # type: ignore[attr-defined]
            for _id_track in _meta_tracks:
                tracks.append(_id_track)
                if len(tracks) == max_results:
                    break

        for _id_track in tracks:
            typer.echo(f"{_id_track.ids!r} {_id_track!r}")

    search_track.__signature__ = params.signature
    search_app.command(name="track", no_args_is_help=True)(search_track)

    return search_app
