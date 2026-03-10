"""
Bidirectional sync between Plex and Traktor playlists.

Only adds missing tracks, does not remove or reorder.
Matching takes place via file paths.

The Path rewrite assumes your plex is remote and traktor is local.
"""

from pathlib import Path
from typing import Annotated

import typer

from plistsync.core.rewrite import PathRewrite
from plistsync.logger import log
from plistsync.services.plex import PlexPlaylistCollection
from plistsync.services.plex.library import (
    PlexLibrarySectionCollection,
)
from plistsync.services.traktor import (
    NMLLibraryCollection,
    NMLPlaylistCollection,
    NMLPlaylistTrack,
)


def main(
    traktor_nml_path: Annotated[
        Path,
        typer.Argument(
            help="Locations for your traktor `collection.nml file",
            exists=True,
            file_okay=True,
        ),
    ],
    playlist_name: Annotated[
        str, typer.Argument(help="Name for the playlist to synchronize")
    ],
    plex_section_name: Annotated[
        str,
        typer.Option(help="Name of the plex section that holds the playlist"),
    ] = "Music",
    plex_path_base: Annotated[
        str | None,
        typer.Option(
            help="File locations in plex, will be replaced with 'path_base_traktor'"
        ),
    ] = None,
    traktor_path_base: Annotated[
        str | None,
        typer.Option(
            help="File locations in traktor, provide together with 'path_base_traktor'"
        ),
    ] = None,
):
    # Check arguments, and create path rewrite
    if sum([bool(plex_path_base), bool(traktor_path_base)]) == 1:
        raise ValueError(
            "Can only use 'plex_path_base' and 'traktor_path_base' together."
        )
    elif plex_path_base is None or traktor_path_base is None:
        path_rewrite = PathRewrite.from_str("/", "/")  # dummy
    else:
        path_rewrite = PathRewrite.from_str(plex_path_base, traktor_path_base)

    # Get libraries
    plex_library = PlexLibrarySectionCollection(plex_section_name)
    traktor_library = NMLLibraryCollection(traktor_nml_path)

    # Get playlists
    plex_playlist = plex_library.get_playlist(name=playlist_name)
    traktor_playlist = traktor_library.get_playlist(name=playlist_name)

    # Or create them if missing
    if plex_playlist is None:
        if typer.prompt(
            f"No plex playlist '{playlist_name}' found. Should we create it?",
            type=bool,
            default=True,
        ):
            plex_playlist = PlexPlaylistCollection(plex_library, playlist_name)
            plex_playlist.remote_upsert()
        else:
            raise typer.Exit(-1)

    if traktor_playlist is None:
        if typer.prompt(
            f"No traktor playlist '{playlist_name}' found. Should we create it?",
            type=bool,
            default=True,
        ):
            traktor_playlist = NMLPlaylistCollection(traktor_library, playlist_name)
            traktor_playlist.remote_upsert()
        else:
            raise typer.Exit(-1)

    # Compare Tracks via File path
    plex_paths = set(
        # Plex playlists do not support duplicates, so sets are fine.
        path_rewrite.apply(track.path)  # plex files might be on a different disk
        for track in plex_playlist.tracks
        if track.path  # for historic reasons, plex tracks might not always have a path
    )
    traktor_paths = set(track.path for track in traktor_playlist.tracks)

    # File paths are now local (like traktor) for both services
    missing_in_traktor = plex_paths - traktor_paths
    missing_in_plex = traktor_paths - plex_paths

    # Plex to traktor
    log.info(
        f"Adding {len(missing_in_traktor)} tracks from Plex to Traktor playlist..."
    )
    with traktor_playlist.remote_edit():
        for p in missing_in_traktor:
            # For traktor, PlaylistTracks are essentially only file paths, so
            # we do not need a lookup.
            traktor_playlist.tracks.append(NMLPlaylistTrack.from_path(p))

    # Commit changes to Traktor NML file
    traktor_library.write()

    # Traktor to plex
    log.info(f"Adding {len(missing_in_plex)} tracks from Traktor to Plex playlist...")
    with plex_playlist.remote_edit():
        for p in missing_in_plex:
            p_for_plex = path_rewrite.invert.apply(p)
            plex_track = plex_library.find_by_local_ids({"file_path": p_for_plex})
            if plex_track is None:
                log.warning(f"Could not find track in plex: {str(p_for_plex)}")
            else:
                plex_playlist.tracks.append(plex_track)

    log.info("Sync complete.")


main.__doc__ = __doc__  # use module docstring as help
if __name__ == "__main__":
    typer.run(main)
