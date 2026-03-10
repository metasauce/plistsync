"""Export a single Plex playlist to M3U format, with optional path rewriting."""

from pathlib import Path
from typing import Annotated

import typer

from plistsync.core.rewrite import PathRewrite
from plistsync.logger import log
from plistsync.services.plex import PlexLibrarySectionCollection


def main(
    playlist_name: Annotated[
        str,
        typer.Argument(help="Name of the Plex playlist to export"),
    ],
    output_path: Annotated[
        Path,
        typer.Argument(help="Output M3U file path (e.g. ./playlist.m3u)"),
    ],
    plex_section_name: Annotated[
        str, typer.Option(help="Name of the Plex section (e.g. 'Music')")
    ] = "Music",
    plex_path_base: Annotated[
        str | None,
        typer.Option(
            help="Base path used in Plex (e.g. '/media/music' or 'C:\\Users\\Music')"
        ),
    ] = None,
    m3u_path_base: Annotated[
        str | None,
        typer.Option(
            help="Base path to use in output M3U (e.g. '/Volumes/music' or 'D:\\Music')"
        ),
    ] = None,
    extm3u: Annotated[
        bool,
        typer.Option(
            help="Add comments according to EXTM3U Format (not supported by Traktor)"
        ),
    ] = False,
):
    # Validate and build path rewrite
    if sum([bool(plex_path_base), bool(m3u_path_base)]) == 1:
        raise typer.BadParameter(
            "Both 'plex_path_base' and 'm3u_path_base' must be provided together."
        )

    if plex_path_base is None or m3u_path_base is None:
        path_rewrite = PathRewrite.from_str("", "")
    else:
        path_rewrite = PathRewrite.from_str(plex_path_base, m3u_path_base)

    # Load Plex library and playlist
    plex_library = PlexLibrarySectionCollection(plex_section_name)
    playlist = plex_library.get_playlist(name=playlist_name)

    if playlist is None:
        raise ValueError(f"Plex playlist '{playlist_name}' not found.")

    # Build M3U content
    m3u = ""
    if extm3u:
        m3u += "#EXTM3U\n"
        m3u += "#PLAYLIST:" + playlist.name + "\n"

    num_m3u_tracks = 0
    for track in playlist.tracks:
        if not track.path:
            log.warning(f"Track '{track.title}' has no file path — skipping.")
            continue
        m3u += str(path_rewrite.apply(track.path)) + '\n'
        num_m3u_tracks += 1

    # Write M3U file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(m3u, encoding="utf-8")

    log.info(
        f"Exported '{playlist.name}' → {output_path} with {num_m3u_tracks} tracks"
    )


main.__doc__ = __doc__  # set help text from module docstring
if __name__ == "__main__":
    typer.run(main)
