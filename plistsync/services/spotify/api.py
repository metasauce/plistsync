import asyncio

import requests
from requests.structures import CaseInsensitiveDict
from requests_oauth2client import ExpiredAccessToken

from plistsync.logger import log
from plistsync.services.tidal.token import BearerToken
from plistsync.utils import chunk_list

from .token import refresh_spotify_token, requires_spotify_token

# ---------------------------------------------------------------------------- #
#            High level functions to interact with the Spotify API.            #
# ---------------------------------------------------------------------------- #


async def get_track(
    spotify_id: str,
) -> dict:
    """Get a single track by its Spotify ID.

    Parameters
    ----------
    spotify_id : str
        The Spotify ID of the track.

    Returns
    -------
    dict
        The track data from the Spotify API.
    """
    return await spotify_get_req(f"/tracks/{spotify_id}")


async def get_tracks(
    spotify_ids: list[str],
) -> list[dict]:
    """Get multiple tracks by their Spotify IDs.

    Parameters
    ----------
    spotify_ids : list[str]
        A list of Spotify track IDs.

    Returns
    -------
    list[dict]
        A list of track data from the Spotify API.
    """
    if len(spotify_ids) == 0:
        return []

    tracks: list[dict] = []
    for ids in chunk_list(spotify_ids, 50):
        ids_param = ",".join(ids)
        json_res = await spotify_get_req(f"/tracks?ids={ids_param}")
        tracks.extend(json_res.get("tracks", []))

    return tracks


async def get_track_by_isrc(
    isrc: str,
) -> dict:
    """Get a single track by its ISRC code.

    Parameters
    ----------
    isrc : str
        The ISRC code of the track.

    Returns
    -------
    dict | None
        The track data from the Spotify API, or None if not found.
    """
    json_res = await spotify_get_req(f"/search?q=isrc%3A{isrc}&type=track")
    tracks = json_res.get("tracks", {}).get("items", [])
    if len(tracks) == 0:
        raise ValueError(f"No track found with ISRC {isrc}")
    return tracks[0]


async def get_playlist(playlist_id: str) -> dict:
    """Get a playlist by its Spotify ID.

    Parameters
    ----------
    playlist_id : str
        The Spotify ID of the playlist.

    Returns
    -------
    dict
        The playlist data from the Spotify API.
    """
    plist = await spotify_get_req(f"/playlists/{playlist_id}")

    # Resolve all tracks (pagination)
    tracks_obj = plist.get("tracks", {})
    if next_page := tracks_obj.get("next"):
        all_items = tracks_obj.get("items", [])
        while next_page:
            tracks = await spotify_get_req(next_page)
            all_items.extend(tracks.get("items", []))
            next_page = tracks.get("next")
        tracks_obj["items"] = all_items
        tracks_obj["next"] = None

    plist["tracks"] = tracks_obj

    return plist


async def search_tracks(query: str, max: int = 100) -> list[dict]:
    """Search for tracks by a query string.

    Parameters
    ----------
    query : str
        The search query.
    limit : int, optional
        The maximum number of results to return, by default 20.

    Returns
    -------
    list[dict]
        A list of track data from the Spotify API.
    """
    next_page = f"/search?type=track&q={query}&limit=50"
    tracks: list[dict] = []
    while next_page and len(tracks) < max:
        json_res = await spotify_get_req(next_page)
        tracks.extend(json_res.get("tracks", {}).get("items", []))
        next_page = json_res.get("tracks", {}).get("next", None)
    return tracks[:max]


from tqdm.asyncio import tqdm


async def get_user_playlists_simplified() -> list[dict]:
    """Get the current user's playlists.

        This returns a simplified version of the playlists, without resolving all tracks.

    Returns
    -------
    list[dict]
        A list of playlist data from the Spotify API.
    """
    next_page = "/me/playlists?limit=50"
    simplified_playlists: list[dict] = []
    while next_page:
        json_res = await spotify_get_req(next_page)
        simplified_playlists.extend(json_res.get("items", []))
        next_page = json_res.get("next", None)
    return simplified_playlists


async def get_user_playlists_full() -> list[dict]:
    """Get the current user's playlists.

    Returns
    -------
    list[dict]
        A list of playlist data from the Spotify API.
    """
    simplified_playlists: list[dict] = []

    with tqdm(
        desc="Fetching user playlists", unit=" playlist", dynamic_ncols=True
    ) as pbar:
        simplified_playlists = await get_user_playlists_simplified()
        pbar.total = len(simplified_playlists)

        # Now resolve each playlist's details
        playlists_details = []
        for plist in simplified_playlists:
            playlist_data = await get_playlist(plist["id"])
            playlists_details.append(playlist_data)
            pbar.update(1)

        pbar.total = pbar.n

    return playlists_details


# ---------------------------------------------------------------------------- #
#                               REQUEST handling                               #
# ---------------------------------------------------------------------------- #


SPOTIFY_BASE_URL = "https://api.spotify.com/v1"


@requires_spotify_token
async def spotify_get_req(
    path: str,
    token: BearerToken,
    **kwargs,
) -> dict:
    """Perform a GET request to the Spotify API.

    This function will handle rate limiting and token expiration.

    Parameters
    ----------
    path : str
        The API endpoint path (e.g., "/me/playlists").
    token : BearerToken
        The BearerToken instance for authentication.
    **kwargs
        Additional arguments to pass to `requests.get`.

    Returns
    -------
    dict
        The JSON response from the API.
    """
    res = await __spotify_get_req(path, token, **kwargs)
    res_json = res.json()
    return res_json


async def __spotify_get_req(
    path: str, token: BearerToken, **kwargs
) -> requests.Response:
    # Ensure the path starts with a '/'
    path = path.replace(SPOTIFY_BASE_URL, "")

    if not path.startswith("/"):
        path = "/" + path

    # Perform the GET request
    try:
        res = requests.get(SPOTIFY_BASE_URL + path, auth=token, **kwargs)
        log.debug(f"GET {SPOTIFY_BASE_URL + path} {res.status_code}")
    except ExpiredAccessToken:
        refresh_spotify_token(token)
        return await __spotify_get_req(path, token, **kwargs)

    # Handle rate limiting
    if res.status_code == 429:
        await handle_rate_limit(res.headers)
        return await __spotify_get_req(path, token, **kwargs)

    # Handle token expiration
    if res.status_code == 401:
        refresh_spotify_token(token)
        return await __spotify_get_req(path, token, **kwargs)

    # Handle other errors
    res.raise_for_status()

    return res


async def handle_rate_limit(headers: CaseInsensitiveDict) -> None:
    remaining = int(headers.get("Retry-After", 0))
    if remaining > 0:
        log.warning(f"Rate limit exceeded. Retrying after {remaining} seconds.")
        await asyncio.sleep(remaining)
    else:
        raise Exception(
            "Rate limit handling failed: Retry-After header is missing or invalid"
        )
    return
