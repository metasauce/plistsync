import os
import re
from datetime import datetime
from pathlib import Path
from pprint import pprint

import typer

# --------------------------------- App Setup -------------------------------- #
plex_cli = typer.Typer(rich_markup_mode="rich", help="Interact with plex")


@plex_cli.command()
def playlist_as_m3u(
    playlist_id: str = typer.Argument(help="The ID or title of the Plex playlist."),
    outpath: str = typer.Option(
        "playlist.m3u",
        "-o",
        "--outpath",
        help="The output path for the M3U file. Default: playlist.m3u",
    ),
    path_rewrite: str = typer.Option(
        None,
        "-rw",
        "--path-rewrite",
        help="Rewrite paths in the M3U file. Format: old_path:new_path",
    ),
):
    from plistsync.services.plex.collection import PlexPlaylistCollection

    pl = PlexPlaylistCollection(
        playlist_id,
        # Might be useful for actual trying to match tracks
        # path_rewrite=PathRewrite(
        #     old="/media/music/clean/", new="/Volumes/music/clean/"
        # ),
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

    with open(outpath, "w", encoding="utf-8") as f:
        # Note: Traktor Pro 4 does not understand the headers
        # and imports them as tracks xD
        # f.write("# EXTM3U\n")
        # f.write("# PLAYLIST: " + pl.name + "\n")
        f.write(m3u)
