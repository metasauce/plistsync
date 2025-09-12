from __future__ import annotations

import asyncio
from typing import AsyncGenerator, List

import requests
from requests.structures import CaseInsensitiveDict
from requests_oauth2client import ExpiredAccessToken
from tqdm.asyncio import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from plistsync.config.yaml import Config
from plistsync.utils import chunk_list
from plistsync.utils.bearer_token import (
    BearerToken,
)

from ...logger import log
from .token import refresh_tidal_token, requires_tidal_token
from .track import TidalTrack

# ---------------------------------------------------------------------------- #
#             High level functions to interact with the Tidal API.             #
# ---------------------------------------------------------------------------- #


async def get_user_playlists_relationships(user_id: str | None = None) -> List[dict]:
    """Get all playlists of the current user.

    Each item only contains the id and type of the playlist.

    .. code-block:: json

        [
            {
                "id": "34872366-1131-43d8-b261-6e9c9cc9386e",
                "type": "playlists",
                "meta": {
                    "addedAt": "2024-07-31T16:36:28.532Z"
                }
            },
            ...
        ]

    BROKEN
    """

    playlists: list[dict] = []

    # We get the ids first and than fetch the full data for each playlist
    # Not sure if we need an iter here
    # You need like 200 playlists to hit the pagination limit I guess
    async for json_res in iter_tidal_get_req(
        f"/userCollections/{user_id}/relationships/playlists"
    ):
        playlists.extend(json_res.get("data", []))

    return playlists


async def get_playlist(playlist_id: str) -> dict:
    """Get the full playlist data of a playlist by its id.

    Parameters
    ----------
    playlist_id : str | None, optional
        The id of the playlist to fetch.
    """

    playlists, items = await tidal_get_req_paged(
        f"/playlists", params={"include": "items", "filter[id]": [playlist_id]}
    )

    pl = playlists[0]
    items_data = pl.get("relationships", {}).get("items", {}).get("data", [])

    ids_in_items = [item.get("id") for item in items]
    missing_items = [
        item for item in items_data if item.get("id") not in ids_in_items
    ]
    pl["missing_items"] = missing_items

    if len(missing_items) > 0:
        pl_name = pl.get("attributes", {}).get("name", " ")
        log.warning(
            f"Missing {len(missing_items)} items in playlist {pl_name} '{pl['id']}'"
        )

    # merge meta fields from playlist into items, so we have the addedAt
    meta_in_idata = {item["id"]: item.get("meta", {}) for item in items_data}
    for item in items:
        if item["id"] in meta_in_idata:
            item["meta"] = meta_in_idata[item["id"]]

    pl["items"] = items

    return pl


async def get_user_playlists(
    user_id: str | None = None, resolve_items: bool = True
) -> list[dict]:
    """Get the full playlist data of all playlists of the current user.

    If user_id is None, the current user's playlists are fetched. Use resolve_items to
    fetch the items of each playlist as well. Depending on the number of
    playlist resolving the items can take quite some time.

    Parameters
    ----------
    user_id : str | None, optional
        The user id of the user to fetch the playlists for. If None, the current user's
        playlists are fetched, by default None.
    resolve_items : bool, optional
        Whether to resolve the items of each playlist as well, by default True.

    Returns
    -------
    list[dict]
        A list of playlist data dicts.
    """

    if not user_id:
        user_data = await tidal_get_req("/users/me")
        user_id = user_data["data"]["id"]

    data, playlists = await tidal_get_req_paged(
        f"/userCollections/{user_id}/relationships/playlists",
        params={"include": "playlists"},
    )

    if len(data) != len(playlists):
        log.warning(
            f"Expected {len(data)} included playlists but received {
                len(playlists)
            } playlists. Strange stuff!"
        )

    if resolve_items:
        with logging_redirect_tqdm():
            for pl in tqdm(playlists, desc="Getting playlist items", unit="playlist"):
                items: list[dict] = []
                items_data, items = await tidal_get_req_paged(
                    pl["relationships"]["items"]["links"]["self"],
                    params={"include": "items"},
                )


                ids_in_items = [item.get("id") for item in items]
                missing_items = [
                    item for item in items_data if item.get("id") not in ids_in_items
                ]
                pl["missing_items"] = missing_items

                if len(missing_items) > 0:
                    pl_name = pl.get("attributes", {}).get("name", " ")
                    log.warning(
                        f"Missing {len(missing_items)} items in playlist {pl_name} '{pl['id']}'"
                    )

                # merge meta fields from playlist into items, so we have the addedAt
                meta_in_idata = {item["id"]: item.get("meta", {}) for item in items_data}
                for item in items:
                    if item["id"] in meta_in_idata:
                        item["meta"] = meta_in_idata[item["id"]]
                pl["items"] = items

    # Included data is returned in same order (no sorting necessary)
    # Also doesnt matter for this function
    return playlists


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

    res = await __tidal_get_req(path, token, **kwargs)
    return res.json()


@requires_tidal_token
async def tidal_get_req_paged(
    path: str, token: BearerToken, **kwargs
) -> tuple[list[dict], list[dict]]:
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
    tuple[list[dict], list[dict]]
        A tuple containing two lists:
        - The first list contains the 'data' items from the response.
        - The second list contains the 'included' items from the response.
    """

    data: list[dict] = []
    included: list[dict] = []

    next_: str | None = path
    while next_:
        res = await __tidal_get_req(next_, token, **kwargs)

        res_json = res.json()
        data.extend(res_json.get("data", []))
        included.extend(res_json.get("included", []))

        # Get next page (if available)
        next_ = res.json().get("links", {}).get("next")

    return data, included


async def __tidal_get_req(path: str, token: BearerToken, **kwargs) -> requests.Response:
    # Ensure the path starts with a '/'
    if not path.startswith("/"):
        path = "/" + path

    # Perform the GET request
    try:
        res = requests.get(TIDAL_BASE_URL + path, auth=token, **kwargs)
        log.debug(f"GET {TIDAL_BASE_URL + path} {res.status_code}")
    except ExpiredAccessToken:
        refresh_tidal_token(token)
        return await __tidal_get_req(path, token, **kwargs)

    # Handle rate limiting
    if res.status_code == 429:
        await handle_rate_limit(res.headers)
        return await __tidal_get_req(path, token, **kwargs)

    # Handle token expiration
    if res.status_code == 401:
        log.info("Tidal token expired, refreshing...")
        refresh_tidal_token(token)
        return await __tidal_get_req(path, token, **kwargs)

    # Handle other errors
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
