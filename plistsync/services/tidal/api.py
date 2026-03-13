from __future__ import annotations

from time import sleep
from typing import Any, ClassVar, Literal, cast

import requests
from requests.structures import CaseInsensitiveDict
from requests_oauth2client import ExpiredAccessToken

from plistsync.config import Config
from plistsync.logger import log
from plistsync.utils import chunk_list
from plistsync.utils.auth.bearer_token import (
    BearerToken,
    InvalidTokenError,
    get_bearer_token,
)

from .api_types import (
    MultiRelationshipDataDocument,
    MultiResourceDataDocument,
    PlaylistDocument,
    PlaylistIncludedResource,
    PlaylistListDocument,
    PlaylistResource,
    PlaylistsItemsResourceIdentifier,
    RelationshipResource,
    T_Included,
    TrackDocument,
    TrackIncludedResource,
    TrackListDocument,
    TrackResource,
    UserDocument,
    UserResource,
)

# It is more performant to have a lookup here instead of a list
# for included resources (type,id) -> resource
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
        res = super().request(
            "POST",
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
            log.debug("Request: %s", url)
            res = super().request(
                method,
                url,
                *args,
                **kwargs,
            )
            res.raise_for_status()
            return res
        except ExpiredAccessToken:
            # Avoid leaking via ExpiredAccessToken by extra try with raise from None
            try:
                self._refresh_token()
                return self.request(method, url, *args, **kwargs)
            except Exception as e:
                raise e from None
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
        a["links"] = b.get("links", {})

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
        doc: MultiResourceDataDocument[RelationshipResource[dict, dict], Any],
    ) -> MultiResourceDataDocument[RelationshipResource[dict, dict], Any]:
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
                rel = inc_item.get("relationships", {}).get(key, {})
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
    playlist: TidalPlaylistApi
    user: TidalUserApi

    def __init__(self):
        self.session = TidalApiSession()
        self.tracks = TidalTrackApi(self.session)
        self.playlist = TidalPlaylistApi(self.session)
        self.user = TidalUserApi(self.session)


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

        params: dict[str, str | list[str]] = {}
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
        isrc_to_index = {isrc: i for i, isrc in enumerate(isrcs)}
        tracks: list[TrackResource] = []
        lookup: LookupDict[TrackIncludedResource] = {}

        # Tidal does only support 20 filters at onece!
        for chunk in chunk_list(isrcs, MAX_FILTER_SIZE):
            tracks_doc = self._get_many(
                isrcs=chunk,
                include=include or ["albums", "artists"],
                country_code=country_code,
            )
            tracks.extend(tracks_doc["data"])
            lookup.update(include_to_lookup(tracks_doc.get("included", [])))

        # Same order for tracks as inserted
        tracks_sorted = sorted(
            tracks, key=lambda track: isrc_to_index[track["attributes"]["isrc"]]
        )

        # Handle missing tracks (Tidal might not return all)
        result: list[TrackResource | None] = [None] * len(isrcs)
        for track in tracks_sorted:
            result[isrc_to_index[track["attributes"]["isrc"]]] = track

        return result, lookup


class TidalPlaylistApi:
    session: TidalApiSession
    default_include: ClassVar[list[str]] = []

    def __init__(self, session: TidalApiSession):
        self.session = session

    def _get(
        self,
        id: str,
        include: list[str] | None = None,
    ) -> PlaylistDocument:
        """Fetch playlist resolving pagination and included items."""
        if include is None:
            include = self.default_include

        doc = self._get_many(
            ids=[id],
            include=include,
        )

        if len(doc["data"]) != 1:
            raise ValueError(f"Playlist with id {id} not found")

        return cast(PlaylistDocument, {**doc, "data": doc["data"][0]})

    def get(
        self,
        id: str,
        include: list[str] | None = None,
    ) -> tuple[PlaylistResource, LookupDict[PlaylistIncludedResource]]:
        """Get single track WITHOUT related resources."""
        track_document = self._get(id, include=include)
        lookup = include_to_lookup(track_document.get("included", []))
        return track_document["data"], lookup

    def _get_many(
        self,
        ids: list[str] | None = None,
        owner_ids: list[str] | None = None,
        include: list[str] | None = None,
        country_code: str | None = None,
        sort: str | None = None,
    ) -> PlaylistListDocument:
        params: dict[str, str | list[str]] = {}
        if country_code:
            params["countryCode"] = country_code
        if ids:
            params["filter[id]"] = ids
        if owner_ids:
            params["filter[owners.id]"] = owner_ids
        if sort:
            params["sort"] = sort

        if include is None:
            include = self.default_include

        return self.session.get_paginated(
            "/playlists",
            include,
            params=params,
        )

    def get_many(
        self,
        ids: list[str],
        include: list[str] | None = None,
        country_code: str | None = None,
    ) -> tuple[list[PlaylistResource], LookupDict]:
        """Fetch multiple playlists by their tidal ids.

        Use sparingly! This will take quite a while.

        Parameters
        ----------
        ids : list[str]
            A list of tidal playlist ids to fetch.
        include : list[str] | None
            An optional list of related resources to include in the lookupdict,
            defaults to ["items", "items.albums", "items.artists"].
        """
        playlist_list_document = self._get_many(
            ids=ids,
            include=include,
            country_code=country_code,
        )
        lookup = include_to_lookup(playlist_list_document.get("included", []))
        return playlist_list_document["data"], lookup

    def get_many_by_user(
        self,
        owner_ids: str | list[str],
        include: list[str] | None = None,
        country_code: str | None = None,
    ) -> tuple[list[PlaylistResource], LookupDict]:
        """Fetch playlists by owner."""
        if isinstance(owner_ids, str):
            owner_ids = [owner_ids]
        playlist_list_document = self._get_many(
            owner_ids=owner_ids,
            include=include,
            country_code=country_code,
        )
        lookup = include_to_lookup(playlist_list_document.get("included", []))
        return playlist_list_document["data"], lookup

    def get_items(
        self,
        playlist_id: str,
        include: list[str] | None = None,
    ) -> tuple[list[PlaylistsItemsResourceIdentifier], LookupDict]:
        """Fetch all items of a playlist.

        Parameters
        ----------
        playlist_id : str
            The playlist ID.
        include : list[str] | None
            Include parameters for the items relationship. Defaults to
            ["items", "items.albums", "items.artists"].

        Returns
        -------
        tuple[list[PlaylistsItemsResourceIdentifier], LookupDict]
            List of item identifiers (with meta) and lookup dict for included
            track resources.
        """
        if include is None:
            include = ["items", "items.albums", "items.artists"]
        doc = self.session.get_paginated(
            f"/playlists/{playlist_id}/relationships/items",
            include,
        )
        data = doc.get("data", [])
        included = doc.get("included", [])
        lookup = include_to_lookup(included)
        return data, lookup

    def _create(
        self,
        name: str,
        description: str | None = None,
        access_type: Literal["PUBLIC", "UNLISTED"] = "UNLISTED",
    ) -> PlaylistDocument:
        """Create a new playlist."""
        return self.session.request(
            "POST",
            "/playlists",
            json={
                "data": {
                    "attributes": {
                        "accessType": access_type,
                        "description": description,
                        "name": name,
                    },
                    "type": "playlists",
                },
            },
        ).json()

    def create(
        self,
        name: str,
        description: str | None = None,
        access_type: Literal["PUBLIC", "UNLISTED"] = "UNLISTED",
    ) -> tuple[PlaylistResource, LookupDict]:
        doc = self._create(name, description, access_type)
        return doc["data"], include_to_lookup(doc.get("included", []))

    def delete(self, id: str):
        return self.session.request("DELETE", f"/playlists/{id}")

    def update(
        self,
        id: str,
        name: str | None = None,
        description: str | None = None,
        access_type: str | None = None,
    ) -> requests.Response:
        """Update a playlists information.

        None values indicate no changes.
        """
        params = {}
        if name:
            params["name"] = name
        if description:
            params["description"] = description
        if access_type:
            params["accessType"] = access_type

        return self.session.request(
            "PATCH",
            f"/playlists/{id}",
            json={"data": {"attributes": params, "id": id, "type": "playlists"}},
        )

    def delete_items(
        self, playlist_id: str, item_ids: list[str], item_type: str = "tracks"
    ) -> requests.Response:
        # Build the data array according to the payload structure
        data = []
        for item_id in item_ids:
            data.append(
                {
                    "id": playlist_id,  # The playlist ID
                    "meta": {
                        "itemId": item_id  # The individual item ID to remove
                    },
                    "type": item_type,
                }
            )

        return self.session.request(
            "DELETE",
            f"/playlists/{playlist_id}/relationships/{item_type}",
            json={"data": data},
        )

    def add_items(
        self,
        playlist_id: str,
        ids: list[str],
        item_type: str = "tracks",
        position_before: str | None = None,
    ) -> requests.Response:
        """Add items to a playlist.

        If position before is provided, add items before the given
        item uuid.
        """

        if item_type not in ["tracks", "videos"]:
            raise ValueError('item_type must be either "tracks" or "videos"')

        # Build the data array
        data: list[dict[str, str]] = []
        for item_id in ids:
            item_data = {
                "id": item_id,
                "type": item_type,
            }
            data.append(item_data)

        # Build the payload
        payload: dict[str, Any] = {"data": data}

        # Add meta if position_before is specified
        if position_before:
            payload["meta"] = {"positionBefore": position_before}

        return self.session.request(
            "POST", f"/playlists/{playlist_id}/relationships/items", json=payload
        )

    def reorder_items(
        self,
        playlist_id: str,
        item_ids: list[tuple[str, str]],
        item_type: str = "tracks",
        position_before: str | None = None,
    ) -> requests.Response:
        """Reorder items within a playlist.

        Moves existing items to a new position in the playlist.

        This seems to be broken atm!
        see https://github.com/orgs/tidal-music/discussions/286
        """

        if item_type not in ["tracks", "videos"]:
            raise ValueError('item_type must be either "tracks" or "videos"')

        # Build the data array - note the structure is different from add/delete
        data: list[dict[str, Any]] = []
        for item_id in item_ids:
            item_data = {
                "id": item_id[0],
                "meta": {
                    "itemId": item_id[1]  # The specific item to reorder
                },
                "type": item_type,
            }
            data.append(item_data)

        # Build the payload
        payload: dict[str, Any] = {"data": data}

        # Add meta if position_before is specified
        if position_before:
            payload["meta"] = {"positionBefore": position_before}

        return self.session.request(
            "PATCH",  # Typically PATCH for reorder operations
            f"/playlists/{playlist_id}/relationships/items",
            json=payload,
        )

    def remove_items(
        self,
        playlist_id: str,
        item_ids: list[tuple[str, str]],
        item_type: str = "tracks",
    ):
        if item_type not in ["tracks", "videos"]:
            raise ValueError('item_type must be either "tracks" or "videos"')

        data: list[dict[str, Any]] = []
        for item_id in item_ids:
            item_data = {
                "id": item_id[0],
                "meta": {"itemId": item_id[1]},
                "type": item_type,
            }
            data.append(item_data)

        # Build the payload
        payload: dict[str, Any] = {"data": data}

        return self.session.request(
            "DELETE",
            f"/playlists/{playlist_id}/relationships/items",
            json=payload,
        )


class TidalUserApi:
    session: TidalApiSession

    def __init__(self, session: TidalApiSession):
        self.session = session

    def _me(self) -> UserDocument:
        return self.session.request("GET", "/users/me").json()

    def me(self) -> UserResource:
        return self._me()["data"]


def include_to_lookup(included: list[T_Included]) -> LookupDict[T_Included]:
    """Convert a list of included items to a lookup dict.

    The key is a tuple of (type, id) and the value is the item dict.
    """
    return {(item["type"], item["id"]): item for item in included}


def extract_tidal_playlist_id(url: str) -> str | None:
    """Extract the Tidal playlist ID from a URL."""
    # Example URL formats:
    # https://tidal.com/browse/playlist/{playlist_id}
    # https://tidal.com/playlist/{playlist_id}

    import re

    pattern = r"tidal\.com/(?:browse/)?playlist/([a-zA-Z0-9]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    else:
        log.debug(f"Invalid Tidal playlist URL: {url}")
        return None
