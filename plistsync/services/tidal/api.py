from __future__ import annotations

import asyncio

import requests
from requests.structures import CaseInsensitiveDict
from requests_oauth2client import ExpiredAccessToken
from tqdm.asyncio import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from plistsync.config import Config
from plistsync.utils import chunk_list
from plistsync.utils.bearer_token import (
    BearerToken,
)

from ...logger import log
from .token import refresh_tidal_token, requires_tidal_token

LookupDict = dict[tuple[str, str], dict]


# ---------------------------------------------------------------------------- #
#             High level functions to interact with the Tidal API.             #
# ---------------------------------------------------------------------------- #
MAX_FILTER_SIZE = 20  # Tidal limits 20 elements per request


async def _get_tracks(params: dict) -> tuple[list[dict], LookupDict]:
    """Fetch multiple tracks by their tidal ids or isrcs.

    filter[id] and filter[isrc] are mutually exclusive. The api will not return
    an error tho...

    Parameters
    ----------
    params : dict
        The parameters to pass to the tidal API. Should contain either
        "filter[id]" or "filter[isrc]" with a list of ids or is
        respectively.

    """
    country_code = Config().tidal.country_code

    data, included, _ = await tidal_get_req_paged(
        f"/tracks",
        params={
            **params,
            "include": ["albums", "artists"],
            "countryCode": country_code,
        },
    )
    return data, included


async def get_tracks(tidal_ids: list[str]) -> list[tuple[dict, LookupDict]]:
    """Fetch multiple tracks by their tidal ids.

    Parameters
    ----------
    tidal_ids : list[str]
        A list of tidal track ids to fetch.

    Returns
    -------
    list[dict]
        A list of track data dicts. Order is not guaranteed to be the same as the input
        list.
    """

    tracks: list[dict] = []
    included: LookupDict = {}
    if not tidal_ids:
        return []

    for chunk in chunk_list(tidal_ids, MAX_FILTER_SIZE):
        params = {"filter[id]": chunk}
        chunk_tracks, chunk_included = await _get_tracks(params)
        tracks.extend(chunk_tracks)
        included.update(chunk_included)

    if len(tracks) != len(tidal_ids):
        log.debug(
            f"Expected {len(tidal_ids)} tracks but received {len(tracks)} tracks as result from tidal batch lookup."
        )

    included_by_track: list[LookupDict] = []
    for track in tracks:
        track_lookup = {("tracks", track["id"]): track}
        for type, rel in track.get("relationships", {}).items():
            for item in rel.get("data", []):
                if lookup_data := included.get((type, item["id"])):
                    track_lookup[(type, item["id"])] = lookup_data
                else:
                    log.debug(
                        f"Related item of type '{type}' with id '{item['id']}' not found in included data of tracks batch lookup."
                    )
        included_by_track.append(track_lookup)

    return list(zip(tracks, included_by_track))


async def get_tracks_by_isrc(isrcs: list[str]) -> list[tuple[dict, LookupDict]]:
    """Fetch multiple tracks by their isrcs.

    Parameters
    ----------
    isrcs : list[str]
        A list of isrcs to fetch.

    Returns
    -------
    list[dict]
        A list of track data dicts. Order is not guaranteed to be the same as the input
        list.
    """

    tracks: list[dict] = []
    included: LookupDict = {}
    if not isrcs:
        return []

    for chunk in chunk_list(isrcs, MAX_FILTER_SIZE):
        params = {"filter[isrc]": chunk}
        chunk_tracks, chunk_included = await _get_tracks(params)
        tracks.extend(chunk_tracks)
        included.update(chunk_included)

    if len(tracks) != len(isrcs):
        log.debug(
            f"Expected {len(isrcs)} tracks but received {len(tracks)} tracks as result from tidal batch lookup."
        )

    included_by_track: list[LookupDict] = []
    for track in tracks:
        track_lookup = {("tracks", track["id"]): track}
        for type, rel in track.get("relationships", {}).items():
            for item in rel.get("data", []):
                if lookup_data := included.get((type, item["id"])):
                    track_lookup[(type, item["id"])] = lookup_data
                else:
                    log.debug(
                        f"Related item of type '{type}' with id '{item['id']}' not found in included data of tracks batch lookup."
                    )
        included_by_track.append(track_lookup)

    return list(zip(tracks, included_by_track))


async def get_playlist(playlist_id: str) -> tuple[dict, LookupDict]:
    """Get the full playlist data of a playlist by its id.

    Parameters
    ----------
    playlist_id : str | None, optional
        The id of the playlist to fetch.
    """

    playlists, included, _ = await tidal_get_req_paged(
        f"/playlists",
        params={
            "filter[id]": [playlist_id],
            # Tracks need albums and artists to be useful
            "include": ["items", "items.albums", "items.artists"],
        },
    )
    if len(playlists) != 1:
        raise ValueError(f"Playlist with id {playlist_id} not found")

    return playlists[0], included


async def get_user_playlists(
    user_id: str | None = None,
    include_items: bool = True,
) -> list[tuple[dict, LookupDict]]:
    """Get the full playlist data of all playlists of the current user.

    If user_id is None, the current user's playlists are fetched. Use include_items to
    fetch the items of each playlist as well. Depending on the number of
    playlist resolving the items can take quite some time.

    Parameters
    ----------
    user_id : str | None, optional
        The user id of the user to fetch the playlists for. If None, the current user's
        playlists are fetched, by default None.
    include_items : bool, optional
        Whether to include the items of each playlist as well, by default True.

    Returns
    -------
    tuple[list[dict], list[LookupDict]]
        A tuple containing:
        - A list of playlist data dicts.
        - A list of lookup dicts of included items for each playlist, keyed by (type, id).

    """

    if not user_id:
        user_data = await tidal_get_req("/users/me")
        user_id = user_data["data"]["id"]

    _, playlists, _ = await tidal_get_req_paged(
        f"/userCollections/{user_id}/relationships/playlists",
        params={"include": ["playlists"]},
    )

    # Include only supports one layer, so we need to fetch the items of each playlist
    # separately if we want them. This can take quite some time depending on the number
    # of playlists.
    if not include_items:
        return list((pl, {}) for pl in playlists.values())

    pl_data = []
    pl_lookup = []
    with logging_redirect_tqdm():
        for i, pl in enumerate(
            tqdm(
                playlists.values(),
                desc="Fetching playlist items",
                unit="playlists",
                leave=False,
            )
        ):
            dat, inc = await get_playlist(pl["id"])
            pl_data.append(dat)
            pl_lookup.append(inc)

    if len(pl_data) != len(playlists):
        log.warning(
            f"Expected {len(pl_data)} included playlists but received {
                len(playlists)
            } playlists. Strange stuff!"
        )

    return list(zip(pl_data, pl_lookup))


@requires_tidal_token
async def create_playlist(
    name: str, token: BearerToken, description: str = ""
) -> tuple[dict, LookupDict]:
    """Create a new playlist in the current user's library.

    Parameters
    ----------
    name : str
        The name of the playlist to create.
    description : str, optional
        The description of the playlist, by default "".

    Returns
    -------
    dict
        The created playlist data.
    """

    country_code = Config().tidal.country_code

    # Perform the GET request
    res = await __tidal_req(
        method="POST",
        path="/playlists",
        token=token,
        json={
            "data": {
                "attributes": {
                    "name": name,
                    "description": description,
                },
                "type": "playlists",
            }
        },
        params={"countryCode": country_code},
    )
    dat = res.json()
    return dat["data"], include_to_lookup_list(dat.get("included", []))


@requires_tidal_token
async def add_tracks_to_playlist(
    playlist_id: str,
    track_ids: list[str],
    token: BearerToken,
    position_before: str | None = None,
) -> None:
    """Add tracks to a playlist.

    Parameters
    ----------
    playlist_id : str
        The id of the playlist to add tracks to.
    track_ids : list[str]
        A list of track ids to add to the playlist.
    position_before : str | None, optional
        The id of the track to insert the new tracks before. If None, the tracks are added
        to the end of the playlist, by default None.

    Returns
    -------
    None
    """

    country_code = Config().tidal.country_code

    if not track_ids:
        return

    for chunk in chunk_list(track_ids, MAX_FILTER_SIZE):
        body: dict = {
            "data": [
                {
                    "id": track_id,
                    "type": "tracks",
                }
                for track_id in chunk
            ]
        }
        if position_before:
            body["positionBefore"] = position_before

        # Does not return anything useful
        await __tidal_req(
            method="POST",
            path=f"/playlists/{playlist_id}/relationships/items",
            token=token,
            json=body,
            params={"countryCode": country_code},
        )


# ---------------------------------------------------------------------------- #
#                               REQUEST handling                               #
# ---------------------------------------------------------------------------- #


TIDAL_BASE_URL = "https://openapi.tidal.com/v2"


@requires_tidal_token
async def tidal_get_req(path: str, token: BearerToken, **kwargs) -> dict:
    """
    Perform a GET request to the Tidal API.

    This function handles rate limiting by waiting if the rate limit is exceeded.

    Parameters
    ----------
    path : str
        The API endpoint path. If it does not start with '/', it will be prefixed with '/'.
    token : BearerToken
        The authentication token to use for the request.
    **kwargs : dict
        Additional keyword arguments to pass to the `requests.get` method.


    Returns
    -------
    dict
        The JSON response from the API.
    """

    res = await __tidal_req("GET", path, token, **kwargs)
    return res.json()


@requires_tidal_token
async def tidal_get_req_paged(
    path: str, token: BearerToken, params: dict = {}, **kwargs
) -> tuple[list[dict], LookupDict, dict]:
    """
    Perform a GET request to the Tidal API.

    This will resolve pagination in the root level of the response.
    This function handles rate limiting by waiting if the rate limit is exceeded.

    Parameters
    ----------
    path : str
        The API endpoint path. If it does not start with '/', it will be prefixed with '/'.
    token : BearerToken
        The authentication token to use for the request.
    **kwargs : dict
        Additional keyword arguments to pass to the `requests.get` method.

    Returns
    -------
    tuple[list[dict], dict, dict]
        A tuple containing:
        - A list of data items from the paged response.
        - A lookup dictionary of included items, keyed by (type, id).
        - The last links object from the paged response.
    """

    data: list[dict] = []
    included: LookupDict = {}
    links = {"next": path}

    while links.get("next"):
        res = await __tidal_req(
            method="GET", path=links["next"], token=token, params=params, **kwargs
        )
        res_json = res.json()
        data.extend(res_json.get("data", []))
        included.update(include_to_lookup_list(res_json.get("included", [])))
        links = res_json.get("links", {})

    # If params are included we also want to resolve their pagination
    # normally they are single words "albums" but can also be nested "items.albums"
    # ["data"][int]["relationships"][<word>]["links"]["next"]
    # Tidal does only every return two layers of includes...
    layer_1_keys = set()
    layer_2_keys = set()
    for p in params.get("include", []):
        split = p.split(".")
        layer_1_keys.add(split[0])
        if len(split) > 1:
            layer_2_keys.add(split[1])
        if len(split) > 2:
            log.warning(
                f"Include parameter '{p}' has more than two layers, which is not supported by tidal API."
            )

    for key in layer_1_keys:
        for item in data:
            item_links = item.get("relationships", {}).get(key, {}).get("links", {})
            if item_links.get("next"):
                item_data, item_included, item_link = await tidal_get_req_paged(
                    item_links.get("next"),
                    token=token,
                    params={"include": params.get("include", [])},
                )

                if item_data:
                    item["relationships"][key]["data"].extend(item_data)

                item["relationships"][key]["links"] = item_link
                included.update(item_included)

    for key in layer_2_keys:
        # We only resolve layer 2 if data is included and has next
        for inc in included.values():
            rel = inc.get("relationships", {}).get(key, {})
            next_url = rel.get("links", {}).get("next")
            if next_url and rel.get("data") is not None:
                inc_data, inc_included, inc_link = await tidal_get_req_paged(
                    next_url,
                    token=token,
                    params={"include": params.get("include", [])},
                )

                if inc_data:
                    inc["relationships"][key]["data"].extend(inc_data)
                inc["relationships"][key]["links"] = inc_link
                included.update(inc_included)

    return data, included, links


async def __tidal_req(
    method: str, path: str, token: BearerToken, **kwargs
) -> requests.Response:
    # Ensure the path starts with a '/'
    if not path.startswith("/"):
        path = "/" + path

    # Perform the GET request
    try:
        res = requests.request(method, TIDAL_BASE_URL + path, auth=token, **kwargs)
        log.debug(f"{method} {TIDAL_BASE_URL + path} {res.status_code}")
    except ExpiredAccessToken:
        refresh_tidal_token(token)
        return await __tidal_req(method, path, token, **kwargs)

    # Handle rate limiting
    if res.status_code == 429:
        await handle_rate_limit(res.headers)
        return await __tidal_req(method, path, token, **kwargs)

    # Handle token expiration
    if res.status_code == 401:
        log.info("Tidal token expired, refreshing...")
        refresh_tidal_token(token)
        return await __tidal_req(method, path, token, **kwargs)

    # Handle other errors
    if not res.ok:
        log.error(f"Tidal API request failed: {res.status_code} {res.text}")

    res.raise_for_status()

    return res


async def handle_rate_limit(headers: CaseInsensitiveDict):
    """Handle tidal rate limit.

    Extract rate limit headers and await the time until the rate limit is reset.
    """

    remaining = int(headers.get("Retry-After", 0))

    if remaining > 0:
        log.info(f"Tidal rate limit exceeded: Waiting {remaining} seconds")
        await asyncio.sleep(remaining)
    else:
        raise Exception(
            "Rate limit handling failed: Retry-After header is missing or invalid"
        )

    return


def include_to_lookup_list(included: list[dict]) -> LookupDict:
    """Convert a list of included items to a lookup dict.

    The key is a tuple of (type, id) and the value is the item dict.
    """
    return {(item["type"], item["id"]): item for item in included}
