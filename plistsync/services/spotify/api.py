import asyncio
from collections import Counter
from typing import Any, Sequence

import requests
from requests.structures import CaseInsensitiveDict
from requests_oauth2client import ExpiredAccessToken
from tqdm.asyncio import tqdm

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
    return await spotify_req(f"/tracks/{spotify_id}", method="GET")


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
        json_res = await spotify_req(f"/tracks?ids={ids_param}")
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
    json_res = await spotify_req(f"/search?q=isrc%3A{isrc}&type=track")
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
    plist = await spotify_req(f"/playlists/{playlist_id}", method="GET")

    # Resolve all tracks (pagination)
    tracks_obj = plist.get("tracks", {})
    if next_page := tracks_obj.get("next"):
        all_items = tracks_obj.get("items", [])
        while next_page:
            tracks = await spotify_req(next_page)
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
        json_res = await spotify_req(next_page)
        tracks.extend(json_res.get("tracks", {}).get("items", []))
        next_page = json_res.get("tracks", {}).get("next", None)
    return tracks[:max]


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
        json_res = await spotify_req(next_page)
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


async def reorder_playlist_tracks(
    playlist_id: str,
    range_start: int,
    range_length: int,
    insert_before: int,
    snapshot_id: str | None = None,
) -> None:
    """Either reorder items in a playlist.

    Parameters
    ----------
    playlist_id : str
        The Spotify ID of the playlist.
    snapshot_id : str
        The snapshot ID of the playlist.
    range_start : int
        The position of the first item to be reordered.
    range_length : int
        The number of items to be reordered.
    insert_before : int
        The position where the items should be inserted.

    Returns
    -------
    str
        The new snapshot ID of the playlist after reordering.
    """
    data: dict = {
        "range_start": range_start,
        "range_length": range_length,
        "insert_before": insert_before,
    }

    if snapshot_id is not None:
        data["snapshot_id"] = snapshot_id

    data = await spotify_req(
        f"/playlists/{playlist_id}/tracks",
        method="PUT",
        json=data,
    )
    return data["snapshot_id"]


async def replace_playlist_tracks(
    playlist_id: str,
    track_uris: list[str],
) -> str:
    """Replace *all* tracks in a playlist.

    Parameters
    ----------
    playlist_id : str
        The Spotify ID of the playlist.
    track_uris : list[str]
        A list of Spotify track URIs to set as the new tracks of the playlist.

    Returns
    -------
    str
        The new snapshot ID of the playlist after replacing tracks.
    """
    data = {"uris": track_uris}
    data = await spotify_req(
        f"/playlists/{playlist_id}/tracks",
        method="PUT",
        json=data,
    )
    return data["snapshot_id"]


async def add_playlist_tracks(
    playlist_id: str,
    track_uris: list[str],
    position: int | None = None,
    snapshot_id: str | None = None,
) -> str:
    """Add tracks to a playlist.

    Parameters
    ----------
    playlist_id : str
        The Spotify ID of the playlist.
    track_uris : list[str]
        A list of Spotify track URIs to add to the playlist.
    position : int | None, optional
        The position to insert the tracks at, by default None (append to end).
    snapshot_id : str | None, optional
        The snapshot ID of the playlist, by default None.

    Returns
    -------
    str
        The new snapshot ID of the playlist after adding tracks.
    """
    if len(track_uris) == 0:
        raise ValueError("No track URIs provided to add to playlist")

    data = {}
    for uris in chunk_list(track_uris, 100):
        body: dict[str, Any] = {"uris": uris}
        if position is not None:
            body["position"] = position
        if snapshot_id is not None:
            body["snapshot_id"] = snapshot_id

        data = await spotify_req(
            f"/playlists/{playlist_id}/tracks",
            method="POST",
            json=body,
        )
        position = (position or 0) + len(uris) if position is not None else None

    return data["snapshot_id"]


async def remove_playlist_tracks(
    playlist_id: str,
    remove_uris: list[str],
    positions: list[int],
    snapshot_id: str | None = None,
    plist_data: dict | None = None,
) -> str:
    """Remove tracks from a playlist at specific positions.

    This is quite annoying as spotify does not allow to remove a specific
    track and will remove all instances of it in a playlist...
    To work around we check that there is no other occurence of the track

    see [here](https://community.spotify.com/t5/Spotify-for-Developers/Positions-field-in-JSON-body-is-ignored-when-removing-tracks/m-p/6055483/highlight/true#M13828)
    """
    if len(remove_uris) != len(positions):
        raise ValueError("track_uris and positions must have the same length")

    if plist_data is None:
        plist_data = await get_playlist(playlist_id)

    # Get current playlist tracks
    playlist_tracks = plist_data.get("tracks", {}).get("items", [])
    playlist_uris = [item.get("track", {}).get("uri") for item in playlist_tracks]

    counter_remove = Counter(remove_uris)
    counter_playlist = Counter(playlist_uris)

    # Check if we are removing all instances of a track
    tracks_to_reinsert = {}
    for uri, count in counter_remove.items():
        if counter_playlist[uri] > count:
            tracks_to_reinsert[uri] = counter_playlist[uri] - count
    if not tracks_to_reinsert:
        # Simple case, we can just remove the tracks
        return await _remove_playlist_tracks(
            playlist_id, remove_uris, snapshot_id=snapshot_id
        )

    reinserts: list[tuple[int, str]] = []
    for pos, uri in enumerate(playlist_uris):
        if tracks_to_reinsert.get(uri, 0) > 0 and pos not in positions:
            reinserts.append((pos, uri))
            tracks_to_reinsert[uri] -= 1

    # For each remove before the position substract one from the position
    # to reinsrert at the correct place
    # TODO: This can be optimized but im too lazy right now
    for i, (pos, uri) in enumerate(reinserts):
        n_removed = 0
        for p in positions:
            if p < pos:
                n_removed += 1
        reinserts[i] = (pos - n_removed, uri)

    log.debug(f"Reinserting {len(reinserts)} tracks after removal")

    # Remove all
    snapshot_id = await _remove_playlist_tracks(
        playlist_id, remove_uris, snapshot_id=snapshot_id
    )

    # Group consecutive reinserts
    reinserts_grouped: list[tuple[int, list[str]]] = []
    prev_pos = None
    for pos, uri in reinserts:
        if prev_pos is not None and pos == prev_pos + 1:
            reinserts_grouped[-1][1].append(uri)
        else:
            reinserts_grouped.append((pos, [uri]))
        prev_pos = pos

    for pos, uris in reinserts_grouped:
        log.debug(f"Reinserting {len(uris)} tracks at position {pos}")
        snapshot_id = await add_playlist_tracks(
            playlist_id,
            uris,
            position=pos,
            snapshot_id=snapshot_id,
        )

    return snapshot_id


async def _remove_playlist_tracks(
    playlist_id: str,
    track_uris: list[str],
    snapshot_id: str | None = None,
) -> str:
    """Remove tracks from a playlist.

    Parameters
    ----------
    playlist_id : str
        The Spotify ID of the playlist.
    track_uris : list[str]
        A list of Spotify track URIs to remove from the playlist.
    positions : list[int | list[int] | None] | None
        A list of positions for each track URI to remove. If gives must match
        the length of `track_uris`.
    snapshot_id : str | None, optional
        The snapshot ID of the playlist, by default None.

    Returns
    -------
    str
        The new snapshot ID of the playlist after removing tracks.
    """
    if len(track_uris) == 0:
        raise ValueError("No track URIs provided to remove from playlist")

    for data_chunk in chunk_list(track_uris, 100):
        body: dict[str, Any] = {"tracks": []}
        for uri in data_chunk:
            body["tracks"].append({"uri": uri})

        data = await spotify_req(
            f"/playlists/{playlist_id}/tracks",
            method="DELETE",
            json=body,
        )
        snapshot_id = data["snapshot_id"]

    return snapshot_id or ""


async def create_playlist(
    name: str,
    description: str,
    public: bool = False,
    collaborative: bool = False,
    user_id: str | None = None,
) -> dict:
    """Create a new playlist for the current user.

    Parameters
    ----------
    name : str
        The name of the playlist.
    description : str, optional
        The description of the playlist, by default "".
    public : bool, optional
        Whether the playlist is public, by default False.
    collaborative : bool, optional
        Whether the playlist is collaborative, by default False.
    user_id : str | None, optional
        The Spotify user ID to create the playlist for. If None, uses the current user.

    Returns
    -------
    dict
        The created playlist data from the Spotify API.
    """
    if user_id is None:
        user_data = await spotify_req("/me")
        user_id = user_data["id"]

    body = {
        "name": name,
        "description": description,
        "public": public,
        "collaborative": collaborative,
    }

    playlist = await spotify_req(
        f"/users/{user_id}/playlists",
        method="POST",
        json=body,
    )
    return playlist


@requires_spotify_token
async def update_playlist_details(
    playlist_id: str,
    token: BearerToken,
    name: str | None = None,
    description: str | None = None,
) -> None:
    """Update the details of a playlist.

    Parameters
    ----------
    playlist_id : str
        The Spotify ID of the playlist.
    name : str | None, optional
        The new name of the playlist, by default None (no change).
    description : str | None, optional
        The new description of the playlist, by default None (no change).

    Returns
    -------
    None
    """
    body: dict[str, str] = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description

    if len(body) == 0:
        return

    await __spotify_req(
        method="PUT",
        path=f"/playlists/{playlist_id}",
        token=token,
        json=body,
    )
    return


# ---------------------------------------------------------------------------- #
#                               REQUEST handling                               #
# ---------------------------------------------------------------------------- #


SPOTIFY_BASE_URL = "https://api.spotify.com/v1"


@requires_spotify_token
async def spotify_req(
    path: str,
    token: BearerToken,
    method: str = "GET",
    **kwargs,
) -> None:
    """Perform a request to the Spotify API.

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
    None on success else an exception is raised.
    """
    res = await __spotify_req(method, path, token, **kwargs)
    return res.json()


async def __spotify_req(
    method: str, path: str, token: BearerToken, **kwargs
) -> requests.Response:
    # Ensure the path starts with a '/'
    path = path.replace(SPOTIFY_BASE_URL, "")

    if not path.startswith("/"):
        path = "/" + path

    # Perform the GET request
    try:
        res = requests.request(method, SPOTIFY_BASE_URL + path, auth=token, **kwargs)
        log.debug(f"{method} {SPOTIFY_BASE_URL + path} {res.status_code}")
    except ExpiredAccessToken:
        refresh_spotify_token(token)
        return await __spotify_req(method, path, token, **kwargs)

    # Handle rate limiting
    if res.status_code == 429:
        await handle_rate_limit(res.headers)
        return await __spotify_req(method, path, token, **kwargs)

    # Handle token expiration
    if res.status_code == 401:
        refresh_spotify_token(token)
        return await __spotify_req(method, path, token, **kwargs)

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
