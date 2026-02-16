# ------------------------------------------------------------------------------ #
# @Author:        F. Paul Spitzner
# @Created:       2025-08-17 09:48:49
# @Last Modified: 2025-08-17 12:59:55
# -------------------------------------------------

"""
Bidirectional sync between Plex and Traktor playlists.

Only adds missing tracks, does not remove or reorder.
Matching takes place via file paths.

TODO: Rewrite
- Library collections should have a .playlists property.
- Commiting: I like the Traktor way of doing things first, and then committing.
But in Plex, inserts are currently one http request per track.
Eventually we should unify this, and check if there is an
`insert_multiple` endpoint.
(there should be, via web-frontend you can do it).
- Traktor: check files and volumes found in lib
    Alternativ: write track entries with file path checks.
"""

from pathlib import Path

from plistsync.core.rewrite import PathRewrite
from plistsync.logger import log
from plistsync.services.plex.collection import (
    PlexLibrarySectionCollection,
)
from plistsync.services.traktor.collection import NMLCollection, NMLPlaylistCollection

# ---------------------------------- Options --------------------------------- #

playlist_name = "_plistsync"
traktor_nml_path = Path("/Users/paul/Music/Traktor/collection.nml")
plex_section_name = "Music"
path_rewrite = PathRewrite(Path("/media/music/clean"), Path("/Traktor/clean"))


def main():
    # Load Plex library and playlist
    plex_library = PlexLibrarySectionCollection(
        plex_section_name,
    )
    plex_playlist = plex_library.get_playlist(name=playlist_name)
    assert plex_playlist is not None, "Playlist not found"

    # Load Traktor collection and playlist
    traktor_collection = NMLCollection(traktor_nml_path)
    traktor_playlist = NMLPlaylistCollection(
        traktor_collection,
        playlist_name,
        create=True,
    )

    # --- Add missing tracks from Plex to Traktor --- #
    # Rewrite paths from plex to match traktor paths
    plex_paths = set(
        path_rewrite.apply(track.path) for track in plex_playlist.tracks if track.path
    )
    traktor_paths = set(track.path for track in traktor_playlist.tracks)

    missing_in_traktor = plex_paths - traktor_paths
    log.info(
        f"Adding {len(missing_in_traktor)} tracks from Plex to Traktor playlist..."
    )
    for path in missing_in_traktor:
        traktor_playlist.insert(path)

    # --- Add missing tracks from Traktor to Plex --- #
    missing_in_plex = traktor_paths - plex_paths
    log.info(f"Adding {len(missing_in_plex)} tracks from Traktor to Plex playlist...")
    with plex_playlist.remote_edit():
        for path in missing_in_plex:
            try:
                # FIXME!
                plex_playlist.tracks.append(path_rewrite.invert.apply(path))  # type:ignore
            except Exception as e:
                log.warning(f"Could not add {path} to Plex playlist: {e}")

    # Commit changes to Traktor NML file
    traktor_playlist.commit()
    log.info("Sync complete.")


if __name__ == "__main__":
    main()
