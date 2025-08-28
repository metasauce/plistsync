from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests

from plistsync.config.yaml import Config, PlexConfig
from plistsync.logger import log

from .api_types import PlexApiPlaylistResponse, PlexApiTrackResponse


def plex_config() -> PlexConfig:
    if c := Config().plex:
        return c

    raise ValueError(
        "Plex configuration not found. Please check your configuration file."
    )


def request(route: str, **kwargs) -> Any:
    """Make a request to the plex server.

    Uses plex server details from environment variables.

    Parameters
    ----------
    route (str): The route to request.

    Returns
    -------
    dict: The response from the plex server.
    """

    baseurl = plex_config().server_url
    token = plex_config().auth_token

    method = kwargs.pop("method", "get").lower()

    kwargs["params"] = kwargs.get("params", {})
    kwargs["params"]["X-Plex-Token"] = token

    kwargs["headers"] = kwargs.get("headers", {})
    kwargs["headers"]["Accept"] = "application/json"

    res = requests.request(method, f"{baseurl}{route}", **kwargs)
    res.raise_for_status()
    return res.json()


def resolve_playlist_id(playlist_name_or_id: str | int) -> int:
    """Resolve a playlist ID from a name or return the ID if already numeric."""
    try:
        playlist_id = int(playlist_name_or_id)
        res = request(f"/playlists/{playlist_id}")
        for playlist in res["MediaContainer"].get("Metadata", []):
            if (int(playlist.get("ratingKey")) == playlist_id) and (
                playlist.get("type") == "playlist"
            ):
                log.debug(
                    f"Resolved section {playlist_id} with title '{playlist.get('title')}'."
                )
                return playlist_id
        raise ValueError()
    except ValueError:
        # playlist_id is a name, not a number; look up the ID
        for playlist in fetch_playlists():
            if playlist.get("title") == playlist_name_or_id and (
                playlist.get("type") == "playlist"
            ):
                return int(playlist["ratingKey"])
    raise ValueError(f"Playlist '{playlist_name_or_id}' not found.")


def resolve_section_id(section_name_or_id: str | int) -> int:
    """
    Resolve a Plex library section by name (or id) to get its id.

    Note on ids and rating keys (strings vs ints):
    - Plex uses ratingKey as a unique identifier for items, which is a string.
    - However, some endpoints like `/library/sections/5` give you the id of the section as `'librarySectionID': 5` so we are quite sure that they are always integers.
    """
    try:
        section_id = int(section_name_or_id)
        # Check if section_id exists and is a valid section
        res = request("/library/sections")
        for section in res["MediaContainer"].get("Directory", []):
            if int(section.get("key")) == section_id:
                log.debug(
                    f"Resolved section {section_id} with title '{section.get('title')}'."
                )
                return section_id
        raise ValueError()
    except ValueError:
        res = request("/library/sections")
        for section in res["MediaContainer"].get("Directory", []):
            if section.get("title") == section_name_or_id:
                section_id = int(section.get("key"))
                log.debug(
                    f"Resolved section {section_id} with title '{section.get('title')}'."
                )
                return section_id
    raise ValueError(f"Library '{section_name_or_id}' not found.")


def fetch_section_root_path(section_id: str | int) -> list[Path]:
    """Fetch the root path of a Plex library section by its ID.

    Parameters
    ----------
    section_id : str | int
        The ID of the Plex library section to fetch.
    """
    root_paths = []
    res = request("/library/sections")
    for section in res["MediaContainer"].get("Directory", []):
        if int(section.get("key")) == int(section_id):
            locations = section.get("Location", [{}])
            for l in locations:
                if "path" in l:
                    root_paths.append(Path(l.get("path")))

    return root_paths


def fetch_playlist(playlist_id: str | int) -> PlexApiPlaylistResponse:
    """Fetch a Plex playlist by its ID.

    Parameters
    ----------
    playlist_id : str
        The ID of the Plex playlist to fetch.
    """

    response = request(f"/playlists/{playlist_id}")

    playlist_data = response["MediaContainer"].get("Metadata", [])
    if len(playlist_data) == 0:
        raise ValueError(f"Playlist with ID '{playlist_id}' not found.")
    for pd in playlist_data:
        # Not sure why this endpoint returns non-playlist items, but it happens.
        if pd.get("type") != "playlist":
            raise ValueError(
                f"ID '{playlist_id}' has type '{pd.get('type')}', not 'playlist'."
            )

    if len(playlist_data) > 1:
        log.error(
            f"Multiple playlists found for ID '{playlist_id}'. Returning the first one."
        )

    return playlist_data[0]


def fetch_playlist_items(playlist_id: str | int) -> list[PlexApiTrackResponse]:
    """Fetch itemsa Plex playlist by its ID."""

    response = request(f"/playlists/{playlist_id}/items")
    return response["MediaContainer"].get("Metadata", [])


def fetch_playlists() -> list[PlexApiPlaylistResponse]:
    """Fetch all plex playlists."""

    response = request(f"/playlists/")
    return response["MediaContainer"]["Metadata"]


def fetch_tracks_by_id(
    track_id: str | int, cache: list[PlexApiTrackResponse] | None = None
) -> list[PlexApiTrackResponse]:
    """Fetch a Plex track by its ID.

    Parameters
    ----------
    track_id : str
        The ID of the Plex track to fetch.
    cache : list[PlexApiTrackResponse] | None
        Optional cache of previously fetched tracks to speed up lookups.
        TODO: benchmark, for me the lookup by id was pretty snappy, felt no difference.
    """

    if cache is None or len(cache) == 0:
        response = request(f"/library/metadata/{track_id}")
        return response["MediaContainer"].get("Metadata", [])

    # search cache instead
    found_tracks = []
    for track in cache:
        found_key = track.get("ratingKey")
        # ratingKeys are strings, but in my lib seem to always be ints.
        # maybe better use strings?
        if found_key is not None and str(found_key) == str(track_id):
            found_tracks.append(track)

    return found_tracks


def fetch_tracks_by_path(
    file_path: Path | str,
    section_id: int,
    cache: list[PlexApiTrackResponse] | None = None,
) -> list[PlexApiTrackResponse]:
    """
    Fetch a track from Plex by its file path, within a given library.

    Takes about 5 seconds on my library - we will need to cache this.

    Parameters
    ----------
    file_path : str
        The full file path to search for.
    section_id : int
        The id of the Plex library section to search. See `get_section_id`.
    cache : list[PlexApiTrackResponse] | None
        Optional cache of previously fetched tracks to speed up lookups.
        TODO: benchmark, but here its worth it - this is a search, much slower than id based.

    Returns
    -------
    dict: The track metadata, or None if not found.
    """
    file_path = Path(file_path).resolve()
    encoded_path = quote(str(file_path))

    if cache is None or len(cache) == 0:
        response = request(
            f"/library/sections/{section_id}/all",
            params={"type": 10, "filename": encoded_path},
        )
        return response["MediaContainer"].get("Metadata", [])

    # search cache instead
    found_tracks = []
    for track in cache:
        found_path = track.get("Media", [{}])[0].get("Part", [{}])[0].get("file")
        if found_path is not None and str(file_path) == str(Path(found_path).resolve()):
            found_tracks.append(track)

    return found_tracks


def fetch_tracks(
    section_id: str | int, page_size: int = 5000
) -> Iterable[PlexApiTrackResponse]:
    """
    Fetch all tracks in a Plex library section, paginated.

    Parameters
    ----------
    section_id : str | int
        The name or id of the Plex library (section).
    page_size : int
        Number of tracks to fetch per request (default: 1000).

    Returns
    -------
    list[dict]: List of track metadata dicts.
    """

    start = 0
    total_size = 0
    num_fetched = 0
    while True:
        response = request(
            f"/library/sections/{section_id}/all",
            params={
                "type": 10,
                "X-Plex-Container-Start": start,
                "X-Plex-Container-Size": page_size,
            },
        )
        tracks = response["MediaContainer"].get("Metadata", [])
        if len(tracks) < page_size:
            break
        num_fetched += len(tracks)
        start += page_size

        # log some progress
        total_size = response["MediaContainer"].get("totalSize", 0)
        if total_size != 0:
            log.debug(
                f"Fetched {num_fetched} of {total_size} tracks from section {section_id}."
            )

        yield from tracks

    return


def insert_track_into_playlist_by_id(
    track_id: str | int,
    playlist_id: str | int,
):
    """Insert a track into a Plex playlist by its ID.

    Parameters
    ----------
    track_id : str | int
        The ID of the track to insert.
    playlist_id : str | int
        The ID of the playlist to insert the track into.

    Note
    ----
    - The currently used endpoint does not add duplicates.
      Calling twice with the same track_id will not add the track again.
    """
    log.debug(f"Inserting track {track_id} into playlist {playlist_id}.")

    machine_id = plex_config().machine_id

    response = request(
        f"/playlists/{playlist_id}/items",
        method="PUT",
        params={
            "uri": f"server://{machine_id}/com.plexapp.plugins.library"
            + f"/library/metadata/{track_id}"
        },
    )

    return response
