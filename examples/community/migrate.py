"""Migrate your playlists from one service to another.

Copies all playlists from one service to another. This
allows to quickly migrate to another music service
provider.
"""

import sys
from typing import Annotated, NamedTuple

import typer

from plistsync.core import Library, Matches, ServicePlaylist, Track
from plistsync.logger import log
from plistsync.services.spotify import SpotifyLibrary
from plistsync.services.tidal import TidalLibrary


class MigrationContext(NamedTuple):
    overwrite: bool
    skip_empty: bool


def migrate_playlist(
    from_playlist: ServicePlaylist,
    to_playlist: ServicePlaylist,
    to_library: Library,
):
    """Migrate a single playlist from one service to another.

    Needs to_library to match tracks in the given library.
    This will overwrite all existing tracks in the destination playlist.
    """
    log.info(f"Transferring {from_playlist.name!r} with {len(from_playlist)} tracks.")

    log.debug(f"Matching tracks on {to_library.name!r}...")
    matches: list[Matches[Track]] = [
        to_library.match(t)  # TODO: Multi match would be nice
        for t in from_playlist.tracks
    ]
    log.debug("Finished matching track.")

    for match in matches:
        if match.best_match is None:
            log.warning(
                f"Couldn't find '{match.truth.title} "
                f"- {match.truth.primary_artist}' "
                f"on {to_library.name!r}"
            )

    with to_playlist.edit():
        to_playlist.tracks = [
            match.best_match for match in matches if match.best_match is not None
        ]

    log.info(f"Successfully migrated {from_playlist.name!r}.")


def migrate_library(
    from_library: Library,
    to_library: Library,
    context: MigrationContext,
):
    # Construct mapping of all playlists
    existing_playlists_to_service = {pl.name: pl for pl in to_library.playlists}

    # TODO: It would be nice to have a playlist picker here
    for from_playlist in from_library.playlists:
        to_playlist = existing_playlists_to_service.get(from_playlist.name)

        if not isinstance(from_playlist, ServicePlaylist):
            raise NotImplementedError(
                "Migration not supported for {from_library.name!r} playlists. "
            )

        if context.skip_empty and len(from_playlist) == 0:
            log.info(f"Skipping empty playlist {from_playlist.name!r}.")
            continue

        if (
            to_playlist is not None
            and not context.overwrite
            and not typer.prompt(
                f"Found existing {to_playlist.name!r} on {to_library.name!r}."
                "Overwrite?",
                type=bool,
                default=True,
            )
        ):
            log.warning(
                f"Not overwriting {to_playlist.name!r} on {to_library.name!r}. "
                "This will yield two playlists with the same name."
            )
            to_playlist = to_library.create_playlist(
                from_playlist.name,
                from_playlist.description,
            )
        else:
            to_playlist = to_library.create_playlist(
                from_playlist.name,
                from_playlist.description,
            )

        if not isinstance(to_playlist, ServicePlaylist):
            raise NotImplementedError(
                "Migration not supported for {to_playlist.name!r} playlists. "
            )

        migrate_playlist(
            from_playlist,
            to_playlist,
            to_library,
        )


service_mapping: dict[str, type[SpotifyLibrary] | type[TidalLibrary]] = {
    "spotify": SpotifyLibrary,
    "tidal": TidalLibrary,
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
    if not (from_library := service_mapping.get(from_service.lower())):
        log.error(
            f"Invalid from_service {from_service!r}."
            f"Pick one of {service_mapping.keys()}"
        )
        sys.exit(1)
    if not (to_library := service_mapping.get(to_service.lower())):
        log.error(
            f"Invalid to_service {to_service!r}. "
            f"Pick one of {list(service_mapping.keys())}."
        )
        sys.exit(1)

    if from_library == to_library:
        raise ValueError("from_service and to_service must be different!")

    migrate_library(
        from_library(),
        to_library(),
        MigrationContext(overwrite=overwrite, skip_empty=skip_empty),
    )


main.__doc__ = __doc__  # use module docstring as help
if __name__ == "__main__":
    typer.run(main)
