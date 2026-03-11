"""Migrate your playlists from one service to another.

Copies all playlists from one service to another. This
allows to quickly migrate to another music service
provider.
"""

import sys
from typing import Annotated, ClassVar, NamedTuple

import typer

from plistsync.logger import log
from plistsync.services.spotify import SpotifyLibraryCollection
from plistsync.services.spotify.playlist import SpotifyPlaylistCollection
from plistsync.services.spotify.track import SpotifyPlaylistTrack, SpotifyTrack
from plistsync.services.tidal import TidalLibraryCollection
from plistsync.services.tidal.playlist import TidalPlaylistCollection
from plistsync.services.tidal.track import TidalPlaylistTrack, TidalTrack


class SpotifyService:
    name: ClassVar[str] = "spotify"

    def __init__(self) -> None:
        self.library = SpotifyLibraryCollection()

    def new_playlist(self, name: str, description: str | None):
        return SpotifyPlaylistCollection(self.library, name, description)

    def playlist_track(self, track: SpotifyTrack):
        return SpotifyPlaylistTrack(track)


class TidalService:
    name: ClassVar[str] = "tidal"

    def __init__(self) -> None:
        self.library = TidalLibraryCollection()

    def new_playlist(self, name: str, description: str | None):
        return TidalPlaylistCollection(self.library, name, description)

    def playlist_track(self, track: TidalTrack):
        return TidalPlaylistTrack(track)


class MigrationContext(NamedTuple):
    overwrite: bool
    skip_empty: bool


def migrate(
    from_service: SpotifyService | TidalService,
    to_service: SpotifyService | TidalService,
    context: MigrationContext,
):
    # Construct mapping of all playlists
    transfer_mappings: dict[
        SpotifyPlaylistCollection | TidalPlaylistCollection,
        SpotifyPlaylistCollection | TidalPlaylistCollection,
    ] = {}
    existing_playlists_to_service = {pl.name: pl for pl in to_service.library.playlists}
    for from_playlist in from_service.library.playlists:
        # Get or create playlist with user feedback for overwrite
        to_playlist = existing_playlists_to_service.get(from_playlist.name)
        if (
            to_playlist is not None
            and not context.overwrite
            and not typer.prompt(
                f"Found existing {to_playlist.name!r} on {to_service.name!r}."
                "Overwrite?",
                type=bool,
                default=True,
            )
        ):
            log.warning(
                f"Not overwriting {to_playlist.name!r} on {to_service.name!r}. "
                "This will yield two playlists with the same name."
            )
        else:
            to_playlist = to_service.new_playlist(
                from_playlist.name,
                from_playlist.description,
            )
        if context.skip_empty and len(from_playlist) == 0:
            log.info(f"Skipping empty playlist {from_playlist.name!r}.")
            continue
        transfer_mappings[from_playlist] = to_playlist

    # Iterate from_playlist and build to_playlist
    for from_playlist, to_playlist in transfer_mappings.items():
        log.info(
            f"Transferring {from_playlist.name!r} with {len(from_playlist)} tracks."
        )
        matched_tracks = list(
            to_service.library.find_many_by_global_ids(
                t.global_ids for t in from_playlist.tracks
            )
        )
        log.info(
            f"Found {len(list(filter(None, matched_tracks)))} of {len(matched_tracks)} "
            f"tracks on {to_service.name}."
        )
        for from_track, to_track in zip(from_playlist.tracks, matched_tracks):
            if to_track is None:
                log.warning(
                    f"Couldn't find '{from_track.title} - {from_track.primary_artist}' "
                    f"on {to_service.name!r}"
                )
            else:
                to_playlist.tracks.append(
                    to_service.playlist_track(to_track),  # type: ignore[arg-type]
                )


service_mapping: dict[str, type[SpotifyService] | type[TidalService]] = {
    "spotify": SpotifyService,
    "tidal": TidalService,
}


def main(
    from_service: Annotated[
        str,
        typer.Argument(
            help="Source of the playlists, either 'spotify' or 'tidal'",
        ),
    ],
    to_service: Annotated[
        str,
        typer.Argument(
            help="Destination of the playlists, either 'spotify' or 'tidal'.",
        ),
    ],
    overwrite: Annotated[
        bool,
        typer.Option(
            help="Overwrite playlists if found by name in 'to_service'",
        ),
    ] = False,
    skip_empty: Annotated[
        bool,
        typer.Option(
            help="Skip empty playlist in migration.",
        ),
    ] = True,
):
    if not (from_service_ := service_mapping.get(from_service.lower())):
        log.error(
            f"Invalid from_service {from_service!r}."
            f"Pick one of {service_mapping.keys()}"
        )
        sys.exit(1)
    if not (to_service_ := service_mapping.get(to_service.lower())):
        log.error(
            f"Invalid to_service {to_service!r}. "
            f"Pick one of {list(service_mapping.keys())}."
        )
        sys.exit(1)

    if from_service_ == to_service_:
        raise ValueError("from_service and to_service must be different!")

    migrate(
        from_service_(),
        to_service_(),
        MigrationContext(overwrite=overwrite, skip_empty=skip_empty),
    )


main.__doc__ = __doc__  # use module docstring as help
if __name__ == "__main__":
    typer.run(main)
