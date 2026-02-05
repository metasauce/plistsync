import shutil
from datetime import datetime
from pathlib import Path

from plistsync.logger import log
from plistsync.services.plex.collection import (
    PlexLibrarySectionCollection,
    PlexPlaylistCollection,
)
from plistsync.services.traktor.collection import NMLPlaylistCollection

# ---------------------------------- Options --------------------------------- #
playlists = [
    "playlist1",
    "playlist2",
    "playlist3",
]
plex_section_name = "Music"
path_rewrite = "/media/music/clean:/Volumes/music/clean"
nml_path = Path("./traktor_collection.nml")


def main(
    playlists: list[str],
    nml_path: Path,
    path_rewrite: str | None = None,
):
    plex_library = PlexLibrarySectionCollection(
        plex_section_name,
    )
    for playlist_id_or_name in playlists:
        log.info(f"\nProcessing playlist: {playlist_id_or_name}")
        pl_plex = PlexPlaylistCollection(
            library_collection=plex_library,
            playlist_name_id_or_data=playlist_id_or_name,
        )

        # make a backup of the nml file
        nml_backup = nml_path.with_suffix(
            f".{datetime.now().strftime('%Y%m%d-%H%M%S')}.bak"
        )
        shutil.copyfile(nml_path, nml_backup)

        pl_nml = NMLPlaylistCollection(nml_path, pl_plex.name, True)

        if path_rewrite:
            old, new = path_rewrite.split(":")
        else:
            old = new = ""

        for track in pl_plex:
            try:
                p = track.path
            except Exception:
                log.error(f"Track {track} does not have a valid path.")
                continue
            path_to_upsert = str(p).replace(
                old,
                new,
            )
            pl_nml.insert(Path(path_to_upsert))

        pl_nml.commit()

        print(f"Tracks in playlist {pl_plex.name}:")
        for t in pl_nml:
            print(t)


if __name__ == "__main__":
    main(
        playlists=["Set Liquide"],
        nml_path=nml_path,
        path_rewrite=path_rewrite,
    )
