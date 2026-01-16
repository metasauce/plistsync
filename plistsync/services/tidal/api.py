from __future__ import annotations

from time import sleep
from typing import TYPE_CHECKING, Any, ClassVar, Sequence, cast, overload

import requests
from requests.structures import CaseInsensitiveDict
from requests_oauth2client import ExpiredAccessToken
from tqdm.asyncio import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from plistsync.config import Config
from plistsync.utils import chunk_list
from plistsync.utils.bearer_token import (
    BearerToken,
    InvalidTokenError,
    get_bearer_token,
)

from ...logger import log
from .token import requires_tidal_token

if TYPE_CHECKING:
    from .api_types import (
        MultiRelationshipDataDocument,
        MultiResourceDataDocument,
        RelatinionshipResource,
        T_Included,
        TrackDocument,
        TrackIncludedResource,
        TrackListDocument,
        TrackResource,
    )

    LookupDict = dict[tuple[str, str], T_Included]


# ---------------------------------------------------------------------------- #
#             High level functions to interact with the Tidal API.             #
# ---------------------------------------------------------------------------- #
MAX_FILTER_SIZE = 20  # Tidal limits 20 elements per request


class TidalApiSession(requests.Session):
    """A request Session configured for Tidal.

    Automatically attaches the auth token and refreshes
    it as needed. Use for making multiple requests to the API.
    """

    token: BearerToken
    server_url: ClassVar[str] = "https://openapi.tidal.com/v2"

    def __init__(self):
        super().__init__()
        self.token = get_bearer_token("tidal")

    def _refresh_token(self) -> None:
        """Refresh the Tidal token.

        This function will refresh the Tidal token using the refresh token.
        It will update the token in place.
        """
        log.debug("Refreshing expired Tidal token...")
        tidal_config = Config().tidal
        res = self.post(
            "https://auth.tidal.com/v1/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": tidal_config.client_id,
                "refresh_token": self.token.as_dict()["refresh_token"],
            },
        )
        try:
            res.raise_for_status()
        except requests.HTTPError as e:
            log.error(res.text, stack_info=False)
            raise InvalidTokenError(self.token) from e

        token_data = res.json()
        self.token.update(token_data)
        self.token.save(Config.get_dir() / "tidal_token.json")

    def _handle_rate_limit(self, headers: CaseInsensitiveDict) -> None:
        remaining = int(headers.get("Retry-After", 0))
        if remaining > 0:
            log.warning(f"Rate limit exceeded. Retrying after {remaining} seconds.")
            sleep(remaining)
        else:
            raise Exception(
                "Rate limit handling failed: Retry-After header is missing or invalid"
            )
        return

    def request(
        self, method: str | bytes, url: str | bytes, *args, **kwargs
    ) -> requests.Response:
        """Request with auth token.

        Slightly different from the normal request, this will raise the status code!
        """
        if self.token.is_expired:
            self._refresh_token()

        # Prepend API base URL if not a full URL
        if isinstance(url, str) and not url.startswith("http"):
            url = self.server_url + url

        # Always use our Spotify token for authentication
        kwargs["auth"] = self.token

        # Calling requests again can in theory
        # create a infinite recursion but
        # should not happen in practice (fingers crossed)
        # we can add some max retry logic if this ever
        # is an issue
        try:
            res = super().request(
                method,
                url,
                *args,
                **kwargs,
            )
            res.raise_for_status()
            return res
        except ExpiredAccessToken:
            self._refresh_token()
            return self.request(method, url, *args, **kwargs)
        except requests.HTTPError as e:
            # Handle rate limiting
            if e.response.status_code == 429:
                self._handle_rate_limit(e.response.headers)
                return self.request(method, url, *args, **kwargs)

            # Handle token expiration
            if e.response.status_code == 401:
                self._refresh_token()
                return self.request(method, url, *args, **kwargs)
            raise e

    def get_paginated(
        self,
        url: str,
        include: list[str] | None = None,
        params: dict | None = None,
        **kwargs,
    ) -> MultiResourceDataDocument:
        """
        Perform a GET request to the Tidal API with pagination resolution.

        This handles both top-level pagination and nested relationship pagination.

        Returns
        -------
            tuple: (data_items, included_lookup, last_links)
        """
        include = include or []
        params = params or {}

        doc: MultiResourceDataDocument = {
            "data": [],
            "included": [],
            "links": {"next": url},
        }

        while next := doc.get("links", {}).get("next"):
            res = self.request(
                method="GET",
                url=next,
                params={**params, "include": include},
                **kwargs,
            )
            page_doc: MultiResourceDataDocument = res.json()
            doc = self._merge_multiresource_pagination(doc, page_doc)

        # Resolve nested pageinated relatinships
        doc = self._resolve_nested_pagination(include, doc)
        # Dedupe include
        doc["included"] = list(include_to_lookup(doc.get("included", [])).values())
        return doc

    def _merge_multiresource_pagination(
        self,
        a: MultiResourceDataDocument,
        b: MultiResourceDataDocument,
    ) -> MultiResourceDataDocument:
        """
        Merge of b into a, following JSON:API spec rules.

        - Appends data arrays
        - Deduplicates included by (type,id)
        - Updates links (b overrides a)
        - Merges meta objects
        """
        a["included"] = a.get("included", [])
        a["links"] = a.get("links", {})

        # Append data (primary resources)
        a["data"].extend(b["data"])

        # Merge included with deduplication
        seen = {(item["type"], item["id"]) for item in a["included"]}
        for item in b.get("included", []):
            key = (item["type"], item["id"])
            if key not in seen:
                seen.add(key)
                a["included"].append(item)

        # Update pagination links (final state wins)
        if "links" in b:
            a["links"].update(b["links"])

        # Merge meta (deep merge if needed)
        if "meta" in b:
            if "meta" not in a:
                a["meta"] = b["meta"]
            else:
                a["meta"].update(b["meta"])

        return a

    def _resolve_nested_pagination(
        self,
        include: list[str],
        doc: MultiResourceDataDocument[RelatinionshipResource, Any],
    ) -> MultiResourceDataDocument[RelatinionshipResource, Any]:
        """
        Recursively resolve pagination for nested relationships.

        Modifies data and included in-place.
        """
        # Parse include parameters for layers
        layer_1_keys: set[str] = set()
        layer_2_keys: set[str] = set()

        for param in include:
            split = param.split(".")
            layer_1_keys.add(split[0])
            if len(split) > 1:
                layer_2_keys.add(split[1])
            if len(split) > 2:
                log.warning(
                    f"Include parameter '{param}' has more than two layers, "
                    "which is not supported by tidal API."
                )

        if "included" not in doc:
            doc["included"] = []

        # Layer 1: Primary data relationships
        for key in layer_1_keys:
            for item in doc["data"]:
                rel: MultiRelationshipDataDocument = item.get("relationships", {}).get(
                    key, {}
                )
                if next_url := rel.get("links", {}).get("next"):
                    rel_doc = self.get_paginated(next_url, include)

                    # Extend relationship.data identifiers
                    if "data" not in rel:
                        rel["data"] = []
                    rel["data"].extend(rel_doc["data"])
                    rel["links"].update(rel_doc.get("links", {}))

                    # Included values are collected on root level
                    doc["included"].extend(rel_doc.get("included", []))

        # Resolve layer 2 relationships (on included items)
        for key in layer_2_keys:
            for inc_item in doc["included"]:
                rel: MultiRelationshipDataDocument = inc_item.get(
                    "relationships", {}
                ).get(key, {})
                if next_url := rel.get("links", {}).get("next"):
                    rel_doc = self.get_paginated(next_url, include)

                    # Extend relationship.data identifiers
                    if "data" not in rel:
                        rel["data"] = []
                    rel["data"].extend(rel_doc["data"])
                    rel["links"].update(rel_doc.get("links", {}))

                    # Included values are collected on root level
                    doc["included"].extend(rel_doc.get("included", []))

        return doc


class TidalApi:
    session: TidalApiSession
    tracks: TidalTrackApi

    def __init__(self):
        self.session = TidalApiSession()
        self.tracks = TidalTrackApi(self.session)


class TidalTrackApi:
    session: TidalApiSession

    def __init__(self, session: TidalApiSession):
        self.session = session

    def _get(
        self,
        id: str,
        include: list[str] | None = None,
    ) -> TrackDocument:
        """Raw API call - returns exactly what the server sends."""
        params = {"include": include} if include else None
        return self.session.request(
            "GET",
            f"/tracks/{id}",
            params=params,
        ).json()

    def get(
        self,
        id: str,
        include: list[str] | None = None,
    ) -> tuple[TrackResource, LookupDict[TrackIncludedResource]]:
        """Get single track WITHOUT related resources."""
        track_document = self._get(id, include=include)
        lookup = include_to_lookup(track_document.get("included", []))
        return track_document["data"], lookup

    def _get_many(
        self,
        ids: list[str] | None = None,
        isrcs: list[str] | None = None,
        country_code: str | None = None,
        include: list[str] | None = None,
        owner_ids: list[str] | None = None,
        share_code: str | None = None,
    ) -> TrackListDocument:
        """Fetch tracks resolving pagination and included items.

        Should only ever be called with 20 items as
        tidal does not support more per requests.

        https://tidal-music.github.io/tidal-api-reference/#/tracks/get_tracks
        """
        # The abstraction here is slightly inconsistent and jank

        params = {}
        if include:
            params["include"] = include
        if country_code:
            params["countryCode"] = country_code
        if ids:
            params["filter[id]"] = ids
        if isrcs:
            params["filter[isrc]"] = isrcs
        if owner_ids:
            params["filter[owners.id]"] = owner_ids
        if share_code:
            params["shareCode"] = share_code

        return self.session.get_paginated(
            "/tracks",
            include,
            params=params,
        )

    def get_many(
        self,
        ids: list[str],
        include: list[str] | None = None,
        country_code: str | None = None,
    ) -> tuple[list[TrackResource | None], LookupDict[TrackIncludedResource]]:
        """Fetch multiple tracks by their tidal ids.

        Parameters
        ----------
        ids : list[str]
            A list of tidal track ids to fetch.
        include : list[str] | None
            An optional list of related resources to include in the lookupdict,
            defaults to ["albums","artists"].
        """
        id_to_index = {tid: i for i, tid in enumerate(ids)}
        tracks: list[TrackResource] = []
        lookup: LookupDict[TrackIncludedResource] = {}

        # Tidal does only support 20 filters at onece!
        for chunk in chunk_list(ids, MAX_FILTER_SIZE):
            tracks_doc = self._get_many(
                ids=chunk,
                include=include or ["albums", "artists"],
                country_code=country_code,
            )
            tracks.extend(tracks_doc["data"])
            lookup.update(include_to_lookup(tracks_doc.get("included", [])))

        # Same order for tracks as inserted
        tracks_sorted = sorted(tracks, key=lambda t: id_to_index[t["id"]])

        # Handle missing tracks (Tidal might not return all)
        result: list[TrackResource | None] = [None] * len(ids)
        for track in tracks_sorted:
            result[id_to_index[track["id"]]] = track

        return result, lookup

    def get_many_by_isrc(
        self,
        isrcs: list[str],
        include: list[str] | None = None,
        country_code: str | None = None,
    ):
        """Fetch multiple tracks by their isrcs.

        Parameters
        ----------
        isrcs : list[str]
            A list of track isrcs to fetch.
        include : list[str] | None
            An optional list of related resources to include in the lookupdict,
            defaults to ["albums","artists"].
        """
        # FIXME: It might be possible to dedup this with the function above
        isrc_to_index = {tid: i for i, tid in enumerate(isrcs)}
        tracks: list[TrackResource] = []
        lookup: LookupDict[TrackIncludedResource] = {}

        # Tidal does only support 20 filters at onece!
        for chunk in chunk_list(isrcs, MAX_FILTER_SIZE):
            tracks_doc = self._get_many(
                ids=chunk,
                include=include or ["albums", "artists"],
                country_code=country_code,
            )
            tracks.extend(tracks_doc["data"])
            lookup.update(include_to_lookup(tracks_doc.get("included", [])))

        # Same order for tracks as inserted
        tracks_sorted = sorted(tracks, key=lambda t: isrc_to_index[t["id"]])

        # Handle missing tracks (Tidal might not return all)
        result: list[TrackResource | None] = [None] * len(isrcs)
        for track in tracks_sorted:
            result[isrc_to_index[track["id"]]] = track

        return result, lookup


class TidalPlaylistApi:
    session: TidalApiSession

    def __init__(self, session: TidalApiSession):
        self.session = session


class TidalUserApi:
    session: TidalApiSession

    def __init__(self, session: TidalApiSession):
        self.session = session


async def get_playlist(playlist_id: str) -> tuple[dict, LookupDict]:
    """Get the full playlist data of a playlist by its id.

    Parameters
    ----------
    playlist_id : str | None, optional
        The id of the playlist to fetch.
    """

    playlists, included, _ = await tidal_get_req_paged(
        "/playlists",
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
        - A list of lookup dicts of included items for each playlist,
        keyed by (type, id).

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
            f"Expected {len(pl_data)} included playlists but received"
            f" {len(playlists)} playlists. Strange stuff!"
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
    return dat["data"], include_to_lookup(dat.get("included", []))


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
        The id of the track to insert the new tracks before. If None, the tracks
        are added to the end of the playlist, by default None.

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


def include_to_lookup(included: list[T_Included]) -> LookupDict[T_Included]:
    """Convert a list of included items to a lookup dict.

    The key is a tuple of (type, id) and the value is the item dict.
    """
    return {(item["type"], item["id"]): item for item in included}
