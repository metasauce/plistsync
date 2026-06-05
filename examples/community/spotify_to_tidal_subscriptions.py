"""Clone a few Drum and Bass Playlists from Spotify to Tidal.

These playlists are regular updated by awesome curators, but I dont pay Spotify premium.
So I am running this script once a week, to stay updated on Tidal.

Two Options:
- Get the the tracklist into Tidal (clone)
- Accumulate into larger playlists to get everything covered over the whole year (sink)

Currently does not reorder tracks, just checks we include everything thats available
on Tidal.
"""

import html
import re
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table, box

from plistsync.logger import log
from plistsync.services.spotify import SpotifyLibrary
from plistsync.services.tidal import (
    TidalLibrary,
    TidalPlaylistTrack,
)

spotify_library = SpotifyLibrary()
tidal_library = TidalLibrary()

# Updated from spotify to tidal, with deletions and reordering
# https://www.reddit.com/r/DnB/comments/1c7al1q/what_are_the_best_spotify_playlists_for_new_dnb/
lists_to_clone = {
    "https://open.spotify.com/playlist/3HSccBIzwpC5QOaUtifSqQ":  #
    "H2L New DnB",
    #
    "https://open.spotify.com/playlist/4AOoXhcCyDS26rrnPccDwi":  #
    "1MoreThing The Freshest GUESTlist!",
    #
    "https://open.spotify.com/playlist/4yfYTwDYPXn9GuhZxeEg53":  #
    "Lennart Hoffmann Brand New DnB 🦀",
    #
    "https://open.spotify.com/playlist/7MGauBXssMrJ7JMa2RTp2w":  #
    "Sub Focus DnB Selects",
    #
    "https://open.spotify.com/playlist/0wl7MGZyYsdWfZRhUdNenj":  #
    "Lenzman Soulful DnB Essentials",
    #
    "https://open.spotify.com/playlist/1coTr2tQFEfsrX6PFNumay":  #
    "LQ Fresh DnB Picks",
    #
    "https://open.spotify.com/playlist/6OYoyDsHzOoH8vJETyprlk":  #
    "Emily Makis DnB Vocals That Bang",
    #
    "https://open.spotify.com/playlist/0Zarq4BVkFkZOWkmqsfrjA":  #
    "UKF DnB Top 100",
    #
}

# Only insertions. I use these to collect by year
lists_to_sink = {
    "https://open.spotify.com/playlist/0Zarq4BVkFkZOWkmqsfrjA":  #
    f"UKF DnB Top 100 {datetime.now().year}",
}


def main():
    log.info(f"Will clone {len(lists_to_clone)} playlists")
    for spotify_url, tidal_target_name in lists_to_clone.items():
        transfer_playlist(spotify_url, tidal_target_name)

    log.info(f"Will sink {len(lists_to_sink)} playlists")
    for spotify_url, tidal_target_name in lists_to_sink.items():
        transfer_playlist(spotify_url, tidal_target_name, insert_only=True)


def transfer_playlist(
    spotify_url: str,
    tidal_target_name: str,
    insert_only: bool = False,
):
    pass

    log.info(f"Transferring {spotify_url}")
    spotify_plist = spotify_library.get_playlist_or_raise(url=spotify_url)
    log.info(f"Found {len(spotify_plist)} tracks in source: {spotify_plist.name}")

    tidal_plist = tidal_library.get_playlist(name=tidal_target_name)
    if tidal_plist is None:
        log.debug(f"Creating new plist on tidal: {tidal_target_name}")
        tidal_plist = tidal_library.create_playlist(
            name=tidal_target_name,
        )

    log.info(
        f"Target playlist '{tidal_target_name}' currently has {len(tidal_plist)} tracks"
    )
    tidal_description = html.unescape(
        re.sub(r"<[^>]+>", "", spotify_plist.description or "")
    )
    with tidal_plist.edit():
        tidal_plist.name = tidal_target_name
        tidal_plist.description = (
            f"{tidal_description}"
            f"\n\n| Last synced with ❤️ using plistsync on "
            f"{datetime.today().strftime('%Y-%m-%d')}"
            f"\n\n| Original playlist: {spotify_url}"
        )

    # for now, the comparison is mostly isrc based
    tidal_isrcs = [t.isrc for t in tidal_plist.tracks if t.isrc is not None]
    spotify_isrcs = [t.isrc for t in spotify_plist.tracks if t.isrc is not None]

    if not insert_only:
        log.info("Removing old tracks from Tidal playlist")
        with tidal_plist.edit():
            for t in reversed(tidal_plist.tracks):
                if t.isrc not in spotify_isrcs:
                    tidal_plist.tracks.remove(t)
        log.info(f"Tidal playlist now has {len(tidal_plist.tracks)} tracks")

    log.info("Finding tracks to add on Tidal")
    ids_to_lookup = [
        t.global_ids for t in spotify_plist.tracks if t.isrc not in tidal_isrcs
    ]
    missing_tracks = [
        TidalPlaylistTrack(t)
        for t in tidal_library.find_many_by_global_ids(ids_to_lookup)
        if t is not None
    ]

    log.info(f"Adding {len(missing_tracks)} tracks to Tidal")
    with tidal_plist.edit():
        tidal_plist.tracks.extend(missing_tracks)
    log.info(f"Tidal playlist now has {len(tidal_plist.tracks)} tracks")

    # log what we have synced
    console = Console()
    table = Table(box=box.MINIMAL_DOUBLE_HEAD)
    table.add_column("Artist", style="cyan")
    table.add_column("Title", style="cyan")
    table.add_column("Spotify ID", style="green")
    table.add_column("ISRC", style="magenta")
    table.add_column("Tidal ID", style="white")

    for spotify_track in spotify_plist.tracks:
        row = [
            spotify_track.artists[0],
            spotify_track.name,
            spotify_track.id,
            spotify_track.isrc,
        ]
        try:
            tidal_track = [
                t for t in tidal_plist.tracks if t.isrc == spotify_track.isrc
            ][0]
            row.append(tidal_track.id)
        except IndexError:
            row.append("[red]Not found[/red]")

        table.add_row(*row)

    # print instead of log, since logging adds whitespace
    console.print(table)


main.__doc__ = __doc__  # use module docstring as help
if __name__ == "__main__":
    typer.run(main)
