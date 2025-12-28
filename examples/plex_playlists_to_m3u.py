import os
import re
from pathlib import Path

from plistsync.logger import log
from plistsync.services.plex.collection import (
    PlexLibrarySectionCollection,
    PlexPlaylistCollection,
)
from plistsync.services.plex.track import PathRewrite

# ---------------------------------- Options --------------------------------- #
playlists = [
    "playlist1",
    "playlist2",
    "playlist3",
]
plex_section_name = "Music"
output_dir = Path(os.getcwd()).resolve()

path_rewrite = "/media/music/clean:/Volumes/music/clean"


def main(
    playlists: list[str],
    outpath: Path,
    path_rewrite: str | None = None,
):
    # Load Plex library and playlist
    plex_library = PlexLibrarySectionCollection(
        plex_section_name,
    )
    for playlist_id_or_name in playlists:
        log.info(f"\nProcessing playlist: {playlist_id_or_name}")
        pl = PlexPlaylistCollection(
            plex_library,
            playlist_id_or_name,
        )

        if path_rewrite:
            old, new = path_rewrite.split(":")
        else:
            old = new = ""

        m3u = ""
        for track in pl:
            if not str(track.path).startswith(old):
                raise Warning(
                    f"Track {track.path} does not start with the specified rewrite ({old})."
                )
            m3u += (
                str(track.path).replace(
                    old,
                    new,
                )
                + "\n"
            )

        # remove non-safe characters that cannot go into filenames
        safe_pl_name = re.sub(r"[^\w\s-]", "", pl.name).strip().replace(" ", "_")
        outpath = output_dir / f"{safe_pl_name}.m3u"

        with open(outpath, "w", encoding="utf-8") as f:
            # Note: Traktor Pro 4 does not understand the headers
            # and imports them as tracks xD
            # f.write("# EXTM3U\n")
            # f.write("# PLAYLIST: " + pl.name + "\n")
            f.write(m3u)


if __name__ == "__main__":
    main(
        playlists=playlists,
        outpath=output_dir,
        path_rewrite=path_rewrite,
    )
