from __future__ import annotations

from typing import Any

import requests

from plistsync.config.yaml import Config, PlexConfig
from plistsync.logger import log
from plistsync.services.plex.track import PlexTrack


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

    kwargs["params"] = kwargs.get("params", {})
    kwargs["params"]["X-Plex-Token"] = token

    kwargs["headers"] = kwargs.get("headers", {})
    kwargs["headers"]["Accept"] = "application/json"

    res = requests.get(f"{baseurl}{route}", **kwargs)
    res.raise_for_status()
    return res.json()


from functools import wraps


def playlist_id_or_name(func):
    """Convert a playlist name to its ID.

    If the provided `playlist_id` is not numeric.
    Assumes the wrapped function has a `playlist_id` parameter.
    """

    @wraps(func)
    def wrapper(playlist_id: str | int, *args, **kwargs):
        playlist_id = resolve_playlist_id(playlist_id)

        return func(playlist_id, *args, **kwargs)

    return wrapper


def resolve_playlist_id(playlist_id: str | int) -> int:
    """Resolve a playlist ID from a name or return the ID if already numeric."""
    try:
        return int(playlist_id)  # Check if playlist_id is numeric
    except ValueError:
        # playlist_id is a name, not a number; look up the ID
        data = fetch_playlists()
        for playlist in data.get("Metadata", []):
            if playlist.get("title") == playlist_id:
                return playlist.get("ratingKey")
    raise ValueError(f"Playlist '{playlist_id}' not found.")


@playlist_id_or_name
def fetch_playlist(playlist_id: str | int) -> dict[str, Any]:
    """Fetch a Plex playlist by its ID.

    Parameters
    ----------
    playlist_id : str
        The ID of the Plex playlist to fetch.
    """

    response = request(f"/playlists/{playlist_id}")

    return response["MediaContainer"]


@playlist_id_or_name
def fetch_playlist_items(playlist_id: str | int) -> dict[str, Any]:
    """Fetch itemsa Plex playlist by its ID."""

    response = request(f"/playlists/{playlist_id}/items")
    return response["MediaContainer"]


def fetch_playlists() -> dict[str, Any]:
    """Fetch a Plex playlist by its ID.

    Parameters
    ----------
    playlist_id : str
        The ID of the Plex playlist to fetch.
    """

    response = request(f"/playlists/")
    return response["MediaContainer"]


def fetch_track(track_id: str | int) -> dict[str, Any]:
    """Fetch a Plex track by its ID.

    Parameters
    ----------
    track_id : str
        The ID of the Plex track to fetch.
    """

    response = request(f"/library/metadata/{track_id}")
    return response["MediaContainer"]
