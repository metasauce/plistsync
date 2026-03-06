from __future__ import annotations

from collections import Counter
from time import sleep
from typing import TYPE_CHECKING, Any, ClassVar, Literal, overload

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
    PlaylistTracks,
    PlaylistTracksBase,
    SpotifyApiPlaylistTrack,
)

if TYPE_CHECKING:
    from .api_types import (
        SpotifyApiPlaylistResponseFull,
        SpotifyApiPlaylistResponseSimplified,
        SpotifyApiTrackResponse,
    )


class SpotifyApiSession(requests.Session):
    """A requests Session configured for Spotify.

    Automatically attaches the auth token and refreshes
    it as needed. Use for making multiple requests to the API.
    """

    token: BearerToken
    server_url: ClassVar[str] = "https://api.spotify.com/v1"

    def __init__(self):
        super().__init__()
        self.headers["Accept"] = "application/json"
        self.token = get_bearer_token("spotify")

    def _refresh_token(self) -> None:
        """Validate the spotify token by making a test request.

        According to API docs, one should use the /api/v2/user endpoint
        to validate tokens.
        """
        log.debug("Refreshing expired Spotify token...")
        spotify_config = Config().spotify
        res = requests.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "refresh_token",
                "client_id": spotify_config.client_id,
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
        self.token.save(Config.get_dir() / "spotify_token.json")

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
        """Request with Spotify token.

        Slightly different from the normal request, this will raise the status code!
        """
        if self.token.is_expired:
            self._refresh_token()

        # Prepend spotify API base URL if not a full URL
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


class SpotifyApi:
    """A spotify API client."""

    session: SpotifyApiSession

    playlist: PlaylistApi
    track: TrackApi
    user: UserApi

    def __init__(self):
        self.session = SpotifyApiSession()
        self.playlist = PlaylistApi(self.session, self)
        self.user = UserApi(self.session, self)
        self.track = TrackApi(self.session)


class PlaylistApi:
    session: SpotifyApiSession

    def __init__(self, session: SpotifyApiSession, api: SpotifyApi):
        self.session = session
        self.api = api

    @overload
    def get(
        self,
        playlist_id: str,
        preload: Literal[True] = ...,
    ) -> SpotifyApiPlaylistResponseFull: ...
    @overload
    def get(
        self,
        playlist_id: str,
        preload: Literal[False],
    ) -> SpotifyApiPlaylistResponseSimplified: ...

    def get(
        self, playlist_id: str, preload: bool = True
    ) -> SpotifyApiPlaylistResponseFull | SpotifyApiPlaylistResponseSimplified:
        """Get a single playlist by its Spotify identifier."""
        plist = self.session.request(
            "GET",
            f"/playlists/{playlist_id}",
        ).json()

        if preload:
            plist["tracks"] = {
                **plist["tracks"],
                "items": self._load_tracks(plist["tracks"]),
                "next": None,
            }
        return plist

    def _load_tracks(
        self,
        data: PlaylistTracksBase,
        force: bool = False,
    ) -> list[SpotifyApiPlaylistTrack]:
        """Resolve the track pagination."""
        all_items: list[SpotifyApiPlaylistTrack] = data.get("items", [])  # type: ignore[assignment]

        next_page = data.get("next")
        if force:
            all_items = []
            next_page = data["href"]

        while next_page:
            tracks: PlaylistTracks = self.session.request(
                "GET",
                next_page,
            ).json()
            all_items.extend(tracks.get("items", []))
            next_page = tracks.get("next")

        return all_items

    def create(
        self,
        name: str,
        description: str,
        public: bool = False,
        collaborative: bool = False,
    ) -> SpotifyApiPlaylistResponseFull:
        """Create a new playlist for the current user.

        Parameters
        ----------
        name : str
            The name of the playlist.
        description : str
            The description of the playlist.
        public : bool, optional
            Whether the playlist is public, by default False.
        collaborative : bool, optional
            Whether the playlist is collaborative, by default False.
        """
        user_data = self.api.user.me()
        user_id = user_data["id"]

        body = {
            "name": name,
            "description": description,
            "public": public,
            "collaborative": collaborative,
        }

        playlist = self.session.request(
            "POST",
            f"/users/{user_id}/playlists",
            json=body,
        ).json()
        return playlist

    def delete(self, playlist_id: str):
        """Delete a playlist from the owners library.

        Note that spotify never really deletes playlists.
        Rather, owners unfollow them (so others can still use them)
        """
        return self.session.request(
            "DELETE",
            "/me/library",
            params={"uris": f"spotify:playlist:{playlist_id}"},
        )

    def update(
        self,
        playlist_id: str,
        name: str | None = None,
        description: str | None = None,
        public: bool | None = None,
        collaborative: bool | None = None,
    ) -> None:
        """Update the details of a playlist.

        Parameters
        ----------
        playlist_id : str
            The Spotify ID of the playlist.
        name : str | None
            The new name of the playlist, by default None (no change).
        description : str | None
            The new description of the playlist, by default None (no change).
        public: bool | None
            The new public status of the playlist, by default None (no change)
        collaborative: bool | None
            If true, the playlist will become collaborative and other users
            will be able to modify the playlist in their Spotify client.
        """
        # Only include not none values
        body: dict[str, str | bool] = {
            k: v
            for k, v in {
                "name": name,
                "description": description,
                "public": public,
                "collaborative": collaborative,
            }.items()
            if v is not None
        }

        self.session.request(
            method="PUT",
            url=f"/playlists/{playlist_id}",
            json=body,
        )

    def reorder_tracks(
        self,
        playlist_id: str,
        range_start: int,
        range_length: int,
        insert_before: int,
        snapshot_id: str | None = None,
    ) -> str:
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
            The new snapshot ID of the playlist after replacing tracks.
        """
        data: dict = {
            "range_start": range_start,
            "range_length": range_length,
            "insert_before": insert_before,
        }

        if snapshot_id is not None:
            data["snapshot_id"] = snapshot_id

        response = self.session.request(
            "PUT",
            f"/playlists/{playlist_id}/tracks",
            json=data,
        )

        return response.json()["snapshot_id"]

    def replace_tracks(self, playlist_id: str, track_uris: list[str]) -> str:
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
        response = self.session.request(
            "PUT",
            f"/playlists/{playlist_id}/tracks",
            json=data,
        )
        return response.json()["snapshot_id"]

    def add_tracks(
        self,
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

            response = self.session.request(
                "POST",
                f"/playlists/{playlist_id}/tracks",
                json=body,
            )
            data = response.json()
            position = (position or 0) + len(uris) if position is not None else None

        return data["snapshot_id"]

    def remove_tracks(
        self,
        playlist_id: str,
        remove_uris: list[str],
        positions: list[int],
        snapshot_id: str | None = None,
        plist_data: SpotifyApiPlaylistResponseFull | None = None,
    ) -> str:
        """Remove tracks from a playlist at specific positions.

        This is quite annoying as spotify does not allow to remove a
        specific track and will remove all instances of it in a
        playlist...
        To work around we check that there is no other occurrence of the track

        see [here](https://community.spotify.com/t5/Spotify-for-Developers/Positions-field-in-JSON-body-is-ignored-when-removing-tracks/m-p/6055483/highlight/true#M13828)

        TODO: check if this is still the case
        """
        if len(remove_uris) != len(positions):
            raise ValueError("track_uris and positions must have the same length")

        if plist_data is None:
            plist_data = self.get(playlist_id)

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
            return self._remove_tracks(
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
        snapshot_id = self._remove_tracks(
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
            snapshot_id = self.add_tracks(
                playlist_id,
                uris,
                position=pos,
                snapshot_id=snapshot_id,
            )

        return snapshot_id

    def _remove_tracks(
        self,
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

            response = self.session.request(
                "DELETE",
                f"/playlists/{playlist_id}/tracks",
                json=body,
            )
            data = response.json()
            snapshot_id = data["snapshot_id"]

        return snapshot_id or ""


class TrackApi:
    def __init__(self, session: SpotifyApiSession):
        self.session = session

    def get(self, spotify_id: str) -> SpotifyApiTrackResponse:
        """Get a single track by its Spotify identifier."""
        res = self.session.request(
            "GET",
            f"/tracks/{spotify_id}",
        )
        return res.json()

    def get_many(self, spotify_ids: list[str]) -> list[SpotifyApiTrackResponse]:
        """Get multiple tracks by their Spotify IDs."""
        tracks: list[SpotifyApiTrackResponse] = []
        for ids in chunk_list(spotify_ids, 50):
            ids_param = ",".join(ids)
            res = self.session.request(
                "GET",
                f"/tracks?ids={ids_param}",
            )
            json_res = res.json()
            tracks.extend(json_res.get("tracks", []))
        return tracks

    def get_by_isrc(self, isrc: str) -> SpotifyApiTrackResponse | None:
        """Get a single track by its ISRC code."""

        json_res = self.session.request(
            "GET",
            f"/search?q=isrc%3A{isrc}&type=track",
        ).json()
        tracks = json_res.get("tracks", {}).get("items", [])
        if len(tracks) == 0:
            return None
        return tracks[0]

    def search(
        self, query: str, max_results: int = 100
    ) -> list[SpotifyApiTrackResponse]:
        """Search for tracks by a query string.

        Parameters
        ----------
        query : str
            The search query. TODO: maybe we want to type this
        max_results : int, optional
            The maximum number of results to return, by default 100.
        """
        next_page = f"/search?type=track&q={query}&limit=50"
        tracks: list[SpotifyApiTrackResponse] = []
        while next_page and len(tracks) < max_results:
            json_res = self.session.request(
                "GET",
                next_page,
            ).json()
            tracks.extend(json_res.get("tracks", {}).get("items", []))
            next_page = json_res.get("tracks", {}).get("next", None)
        return tracks[:max_results]


class UserApi:
    session: SpotifyApiSession
    api: SpotifyApi

    def __init__(self, session: SpotifyApiSession, api: SpotifyApi):
        self.session = session
        self.api = api

    @overload
    def get_playlists(
        self, preload: Literal[True]
    ) -> list[SpotifyApiPlaylistResponseSimplified]: ...
    @overload
    def get_playlists(
        self, preload: Literal[False] = ...
    ) -> list[SpotifyApiPlaylistResponseFull]: ...
    def get_playlists(
        self, preload: bool = False
    ) -> (
        list[SpotifyApiPlaylistResponseSimplified]
        | list[SpotifyApiPlaylistResponseFull]
    ):
        # Migrated from get_user_playlists_simplified() and get_user_playlists_full()
        if not preload:
            return self._get_playlists_simplified()
        else:
            return self._get_playlists_full()

    def me(self) -> dict:
        """Get the current user's profile."""
        return self.session.request(
            "GET",
            "/me",
        ).json()

    def _get_playlists_simplified(self) -> list[SpotifyApiPlaylistResponseSimplified]:
        """Get the current user's playlists without resolving all tracks.

        Returns
        -------
        list[dict]
            A list of simplified playlist data from the Spotify API.
        """
        next_page = "/me/playlists?offset=0&limit=50"
        simplified_playlists: list[SpotifyApiPlaylistResponseSimplified] = []
        while next_page:
            json_res = self.session.request(
                "GET",
                next_page,
            ).json()
            simplified_playlists.extend(json_res.get("items", []))
            next_page = json_res.get("next", None)
        return simplified_playlists

    def _get_playlists_full(self) -> list[SpotifyApiPlaylistResponseFull]:
        """Get the current user's playlists with full details.

        Returns
        -------
        list[dict]
            A list of playlist data from the Spotify API.
        """
        simplified_playlists = self._get_playlists_simplified()
        # Now resolve each playlist's details
        playlists_details = []
        for plist in simplified_playlists:
            playlist_data = self.api.playlist.get(plist["id"])
            playlists_details.append(playlist_data)

        return playlists_details


def extract_spotify_playlist_id(url_or_uri: str) -> str:
    """Extract the Spotify ID from a playlist URL or URI."""
    # Pattern matches:
    # spotify:playlist:<id>
    # https?://open.spotify.com/playlist/<id>
    # open.spotify.com/playlist/<id> (without protocol)

    import re

    pattern = r"(?:spotify:playlist:|(?:https?://)?open\.spotify\.com/playlist/)([a-zA-Z0-9]+)"
    match = re.search(pattern, url_or_uri)
    if match:
        return match.group(1)
    else:
        raise ValueError(f"Invalid Spotify playlist URL or URI: {url_or_uri}")
