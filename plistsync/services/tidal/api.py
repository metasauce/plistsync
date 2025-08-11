from __future__ import annotations

import asyncio
from typing import AsyncGenerator, List

import requests
from requests.structures import CaseInsensitiveDict

from ...logger import log
from ...utils import chunk_list
from .token import (
    TidalBearerToken,
    requires_tidal_token,
    requires_tidal_token_generator,
)
from .track import TidalTrack


# ---------------------------------------------------------------------------- #
#             High level functions to interact with the Tidal API.             #
# ---------------------------------------------------------------------------- #
async def get_playlist_data(
    playlist_id: str,
):
    """Pagination is kina weird for the playlists api.

    In theory we can get a playlist including all items (tracks, artists, albums) with the include
    parameter in one request. This returns an 20 items pagination, which is fine but
    there is no way to get the next page at the moment... See https://github.com/orgs/tidal-music/discussions/119

    For now I opted to get the playlist attributes first and than resolve the items manually. This requires
    us to do a 2x the requests but we can get all items. Might be faster in the future __shrug__.
    """

    # Get attributes
    json_res = await tidal_get_req(f"/playlists/{playlist_id}")

    data = json_res.get("data", {})

    # Resolve relationship items
    relationship_items = []
    async for json_res in iter_tidal_get_req(
        f"/playlists/{playlist_id}/relationships/items"
    ):
        # Add items to relationships
        relationship_items.extend(json_res.get("data", []))

    # Get tracks
    tracks = await get_tracks(
        [item["id"] for item in relationship_items if item["type"] == "tracks"]
    )

    return data, tracks


async def get_tracks(track_ids: List[str]):
    tracks: list[TidalTrack] = []

    # Chunk the track ids into 20 ids per request
    # is required by the tidal api!
    for chunk in chunk_list(track_ids, 20):
        params = {
            "filter[id]": ",".join(chunk),
            "include": "albums,artists",
            "countryCode": "DE",
        }
        json_res = await tidal_get_req("/tracks", params=params)

        tracks.extend(
            TidalTrack.from_tracks_response(
                json_res.get("data", []), json_res.get("included", [])
            )
        )

    if len(tracks) != len(track_ids):
        log.warning(
            f"Expected {len(track_ids)} tracks but received {len(tracks)} tracks. We saw that this sometimes happens if you country code is not set correctly. Please check the countryCode parameter in the request!"
        )

    return tracks


# ---------------------------------------------------------------------------- #
#                               REQUEST handling                               #
# ---------------------------------------------------------------------------- #


TIDAL_BASE_URL = "https://openapi.tidal.com/v2"


@requires_tidal_token_generator
async def iter_tidal_get_req(
    path: str, token: TidalBearerToken, **kwargs
) -> AsyncGenerator[dict, None]:
    """
    Perform a GET request to the Tidal API. This can be used for any paginated request.

    This automatically resolve pagination in the root level of the response as a generator.
    This function handles rate limiting by waiting if the rate limit is exceeded.

    Parameters
    ----------
    path : str
        The API endpoint path. If it does not start with '/', it will be prefixed with '/'
    token : BearerToken
        The authentication token to use for the request.
    **kwargs : dict
        Additional keyword arguments to pass to the `requests.get` method.

    Yields
    ------
    dict: The response from the Tidal API as a dictionary.

    Usage
    -----
    ```python
    async for json_res in iter_tidal_get_req("/playlists/me", token):
        print(json_res)
    ```
    """

    while path:
        res = await __tidal_get_req(path, token, **kwargs)

        json_res = res.json()
        yield json_res
        # Get next page (if available)
        path = res.json().get("links", {}).get("next")
    return


@requires_tidal_token
async def tidal_get_req(path: str, token: TidalBearerToken, **kwargs) -> dict:
    """
    Perform a GET request to the Tidal API.

    This will NOT resolve pagination in the root level of the response.
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
    dict: The response from the Tidal API as a dictionary.
    """
    res = await __tidal_get_req(path, token, **kwargs)
    res_json = res.json()

    # Warning if next in links
    if res_json.get("links", {}).get("next"):
        log.warning(
            "Next page available in response. Consider using iter_tidal_get_req for pagination!"
        )

    return res_json


async def __tidal_get_req(
    path: str, token: TidalBearerToken, **kwargs
) -> requests.Response:
    # Ensure the path starts with a '/'
    if not path.startswith("/"):
        path = "/" + path

    # Perform the GET request
    res = requests.get(TIDAL_BASE_URL + path, auth=token, **kwargs)
    log.info(f"GET {TIDAL_BASE_URL + path} {res.status_code}")

    # Handle rate limiting
    if res.status_code == 429:
        await handle_rate_limit(res.headers)
        return await __tidal_get_req(path, token, **kwargs)

    # Handle other errors
    res.raise_for_status()

    return res


async def handle_rate_limit(headers: CaseInsensitiveDict):
    """Handle tidal rate limit.

    Extract rate limit headers and await the time until the rate limit is reset.
    """

    remaining = int(headers.get("X-RateLimit-Remaining", 0))
    burst_capacity = int(headers.get("X-RateLimit-Burst-Capacity", 0))
    replenish_rate = int(headers.get("X-RateLimit-Replenish-Rate", 0))
    requested_tokens = int(headers.get("X-RateLimit-Requested-Tokens", 1))

    log.warning(
        f"Rate limit exceeded: {remaining=}, {burst_capacity=}, {replenish_rate=}, {requested_tokens=}"
    )

    if replenish_rate > 0:
        # Calculate time to wait
        tokens_needed = requested_tokens - remaining
        time_to_wait = (
            tokens_needed / replenish_rate
        ) + 0.5  # Add 0.5 seconds to be sure

        log.info(f"Tidal rate limit exceeded: Waiting {time_to_wait} seconds")
        await asyncio.sleep(time_to_wait)
    else:
        raise Exception("Rate limit handling failed: Replicish rate is 0")

    return
