import shutil
from datetime import datetime
from pathlib import Path

from plistsync.core.rewrite import PathRewrite
from plistsync.logger import log
from plistsync.services.plex.library import PlexLibrarySectionCollection
from plistsync.services.traktor import (
    NMLLibraryCollection,
    NMLPlaylistCollection,
    NMLPlaylistTrack,
)

# ---------------------------------- Options --------------------------------- #
playlists = [
    "playlist1",
    "playlist2",
    "playlist3",
]
plex_section_name = "Music"
path_rewrite = PathRewrite.from_str(
    "/media/music/clean",
    "/Volumes/music/clean",
)
nml_path = Path("./traktor_collection.nml")


def main(
    playlists: list[str],
    nml_path: Path,
    path_rewrite: PathRewrite | None = None,
):
    plex_library = PlexLibrarySectionCollection(
        plex_section_name,
    )
    traktor_library = NMLLibraryCollection(nml_path)
    # make a backup of the nml file just in case
    nml_backup = nml_path.with_suffix(
        f".{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
    )
    shutil.copyfile(nml_path, nml_backup)

    for pl_name in playlists:
        log.info(f"\nProcessing playlist: {pl_name}")
        pl_plex = plex_library.get_playlist(name=pl_name)
        assert pl_plex is not None, "Playlist not found"

        # Get or create playlist in traktor
        traktor_playlist = traktor_library.get_playlist(name=pl_plex.name)
        if traktor_playlist is None:
            traktor_playlist = NMLPlaylistCollection(
                traktor_library,
                pl_plex.name,
            )
            traktor_playlist.remote_upsert()

        with traktor_playlist.remote_edit():
            for track in pl_plex.tracks:
                try:
                    p = track.path
                except Exception:
                    log.error(f"Track {track} does not have a valid path.")
                    continue

                if not p:
                    continue

                if path_rewrite:
                    p = path_rewrite.apply(p)

                if p:
                    traktor_playlist.tracks.append(
                        NMLPlaylistTrack.from_path(p),
                    )
    traktor_library.write()


if __name__ == "__main__":
    main(
        playlists=["Set Liquide"],
        nml_path=nml_path,
        path_rewrite=path_rewrite,
    )
