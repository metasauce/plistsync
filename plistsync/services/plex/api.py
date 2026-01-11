from __future__ import annotations

import json
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import cache, cached_property
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from plistsync.config import Config, ConfigurationError, PlexConfig
from plistsync.logger import log

from .api_types import (
    PlexApiConnection,
    PlexApiPlaylistResponse,
    PlexApiResourcesResponse,
    PlexApiTrackResponse,
    PlexMediaTypes,
    PlexServerIdentity,
)


def _read_token(path: Path) -> str:
    if not path.exists():
        raise ConfigurationError(
            f"Plex token file not found at {path}! "
            "Please run `plistsync plex auth` to authenticate."
        )
    with open(path) as f:
        data = json.load(f)
    token = data.get("X-Plex-Token")
    if token is None:
        raise ConfigurationError(
            "Plex token not found! Please run `plistsync plex auth` to authenticate."
        )
    return token


class PlexApiSession(requests.Session):
    """A requests Session configured for Plex API requests.

    Automatically attaches the Plex auth token and refreshes
    it as needed. Use for making multiple requests to the Plex API.
    """

    token_valid: bool
    server_url: str

    def __init__(
        self,
        product: str,
        client_identifier: str,
        token: str,
        server_url: str,
    ) -> None:
        """Initialize the PlexApiSession."""
        super().__init__()
        self.token_valid = False
        self.headers["Accept"] = "application/json"
        self.headers["X-Plex-Client-Identifier"] = client_identifier
        self.headers["X-Plex-Product"] = product
        self.headers["X-Plex-Token"] = token
        self.server_url = server_url

    def _validate_token(self) -> None:
        """Validate the Plex token by making a test request.

        According to Plex API docs, one should use the /api/v2/user endpoint
        to validate tokens.
        """
        try:
            response = super().request("GET", f"{self.server_url}/api/v2/user")
            if response.status_code == 401:
                raise ConfigurationError(
                    "Plex token not valid anymore! "
                    "Run `plistsync plex auth` to refresh it."
                )
            self.token_valid = True
        except requests.exceptions.RequestException as e:
            raise ConfigurationError(
                f"Plex token validation failed due to network error: {str(e)}"
            ) from e

    def request(self, *args, **kwargs) -> requests.Response:
        """Override request to add Plex auth token and headers."""
        # On the first request, check that the token is valid
        if not self.token_valid:
            self._validate_token()

        try:
            return super().request(*args, **kwargs)
        except requests.exceptions.RequestException as e:
            raise ConfigurationError(
                f"Plex API request failed due to network error: {str(e)}"
            ) from e


class PlexApi:
    """A Plex API client.

    Currently relies on:
    - a specific Plex server URL for library lookups
    - plex.tv for authentication.

    In the future, we might extend this to use plex.tv for both, but for that we need to
    figure out how to forward requests (needed info via .resources).
    """

    playlist: PlaylistApi
    track: TrackApi
    converts: ConvertsApi

    def __init__(
        self,
        server_url: str | None = None,
        server_name: str | None = None,
    ) -> None:
        self.plex_config: PlexConfig = Config().plex

        def _resolve_server_name(server_name):
            # we need a temporary session for plex.tv, but later want one that uses the
            # local server name
            log.info(
                f"Looking up server ip for '{server_name}', this might take a bit. "
                "To speed this up, use a server_url in stead of server_name."
            )
            temp_session = PlexApiSession(
                self.plex_config.app_name,
                self.plex_config.client_identifier,
                _read_token(self.plex_config.token_path),
                "https://plex.tv",
            )
            conns = self.get_server_connections_for_name(temp_session, server_name)
            return self.get_valid_connection(temp_session, conns).get("uri", "")

        # priority of server url sources:
        if server_url:
            pass
        elif server_name:
            server_url = _resolve_server_name(server_name)
        elif self.plex_config.server_url:
            server_url = self.plex_config.server_url
        elif self.plex_config.server_name:
            server_url = _resolve_server_name(self.plex_config.server_name)
        else:
            raise ValueError(
                "Specify either server_url or server_name (in your config or as kwarg)."
            )

        # create permanent session for remaining requests
        self.session = PlexApiSession(
            self.plex_config.app_name,
            self.plex_config.client_identifier,
            _read_token(self.plex_config.token_path),
            server_url,
        )
        self.playlist = PlaylistApi(self.session)
        self.track = TrackApi(self.session)
        self.converts = ConvertsApi(self.session, self)

    def resources(self) -> list[PlexApiResourcesResponse]:
        """Get Plex resources.

        This endpoint returns a list of all available Plex resources, this
        includes servers, clients, etc.

        Remark: Special endpoint only accessible via https://plex.tv, not
        via the local server URL.
        """
        return self._resources(self.session)

    @staticmethod
    def _resources(session: PlexApiSession) -> list[PlexApiResourcesResponse]:
        """We split this out to get the resources without requireing a local server."""
        response = session.request("GET", "https://plex.tv/api/v2/resources")
        response.raise_for_status()
        return response.json()

    @staticmethod
    def get_server_connections_for_name(
        session: PlexApiSession, server_name: str
    ) -> list[PlexApiConnection]:
        resources = PlexApi._resources(session)
        servers = [res for res in resources if "server" in res.get("provides", "")]
        matches = [res for res in servers if res.get("name") == server_name]
        if len(matches) < 1:
            raise ValueError(
                f"Could not find Server with name '{server_name}' "
                f"Found servers: {[res.get('name') for res in servers]}"
            )
        if len(matches) > 1:
            log.warning(f"Found {len(matches)} servers for {server_name}, using first.")

        # TODO: Currently we can only access _owned_ servers, but in principle
        # also those of friends should work - they are listed in resources.
        if not matches[0].get("owned"):
            raise NotImplementedError("We can only access your own servers for now.")

        connections = matches[0].get("connections", [])
        log.debug(
            f"Found {len(connections)} connections for server_name '{server_name}'"
        )

        return connections

    @staticmethod
    def get_valid_connection(
        session: PlexApiSession,
        connections: list[PlexApiConnection],
        timeout: int = 3,
    ) -> PlexApiConnection:
        """
        Check which uris can be reached.

        Prefer local over remote ones.
        """

        def ping(conn: PlexApiConnection):
            try:
                response = session.head(conn.get("uri", ""), timeout=timeout)
                return conn, response.status_code
            except Exception:
                return conn, None

        working_connections = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_conn = [executor.submit(ping, conn) for conn in connections]
            for future in as_completed(future_to_conn):
                conn, status_code = future.result()
                if status_code:
                    log.debug(
                        f"Connection {conn.get('uri')} got status code {status_code}"
                    )
                else:
                    log.debug(f"Connection {conn.get('uri')} timed out")

                if status_code == 200:
                    working_connections.append(conn)
                    if conn.get("local"):
                        return conn

        if len(working_connections) > 0:
            return working_connections[0]
        else:
            raise ValueError("No valid connection found")

    def sections(self) -> Any:
        """Get Plex library sections."""
        response = self.session.request(
            "GET", f"{self.session.server_url}/library/sections"
        )
        response.raise_for_status()
        return response.json()

    def section(self, section_id: str | int) -> Any:
        """Get a specific Plex library section by ID."""
        response = self.session.request(
            "GET", f"{self.session.server_url}/library/sections/{section_id}"
        )
        response.raise_for_status()
        return response.json()

    @cache
    def identity(self) -> PlexServerIdentity:
        """Get Plex server identity."""
        response = self.session.request("GET", f"{self.session.server_url}/identity")
        response.raise_for_status()
        return response.json()["MediaContainer"]

    @cached_property
    def machine_id(self) -> str:
        """Get this servers unique machineIdentifier.

        Needed for many playlist-related requests.
        Matches the clientIdentifier found in `resources`,
        which is available via the public plex.tv route (no local server needed).
        """
        response = self.identity()
        return response["machineIdentifier"]


class PlaylistApi:
    """Playlist-specific Plex API client."""

    def __init__(self, session: PlexApiSession) -> None:
        self.session = session

    def fetch_playlists(self) -> list[PlexApiPlaylistResponse]:
        """Get all playlists."""
        response = self.session.request("GET", f"{self.session.server_url}/playlists")
        response.raise_for_status()
        return response.json()["MediaContainer"]["Metadata"]

    def fetch_playlist(self, playlist_id: str | int) -> PlexApiPlaylistResponse:
        """Get a specific playlist by ID."""

        response = self.session.request(
            "GET", f"{self.session.server_url}/playlists/{playlist_id}"
        )
        response.raise_for_status()
        playlist_data = response.json()["MediaContainer"].get("Metadata", [])
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
                f"Multiple playlists found for ID '{playlist_id}'. "
                "Returning the first one."
            )

        return playlist_data[0]

    def fetch_playlist_items(
        self, playlist_id: str | int
    ) -> list[PlexApiTrackResponse]:
        """Get items in a specific playlist by ID."""

        response = self.session.request(
            "GET", f"{self.session.server_url}/playlists/{playlist_id}/items"
        )
        response.raise_for_status()
        return response.json()["MediaContainer"].get("Metadata", [])

    def create_playlist(self, title: str, items: list[str]) -> Any:
        """Create a new playlist."""
        data = {"title": title, "items": items}
        response = self.session.request(
            "POST", f"{self.session.server_url}/playlists", json=data
        )
        response.raise_for_status()
        return response.json()

    def insert_item_into_playlist(
        self,
        playlist_id: str | int,
        item_id: str | int,
        machine_id: str,
    ) -> Any:
        """Insert items into a playlist by their IDs.

        Parameters
        ----------
        machine_id : str
            The Plex machine ID of the server where to find the item.
        playlist_id : str | int
            The ID of the playlist to insert items into.
        item_ids : list[str | int]
            The IDs of the items to insert into the playlist.
        """
        uri = f"server://{machine_id}/com.plexapp.plugins.library/library/metadata/{item_id}"
        data = {"uri": uri}
        response = self.session.request(
            "PUT",
            f"{self.session.server_url}/playlists/{playlist_id}/items",
            json=data,
        )
        response.raise_for_status()
        return response.json()


class TrackApi:
    """Track-specific Plex API client."""

    def __init__(self, session: PlexApiSession) -> None:
        self.session = session

    def fetch_tracks(
        self,
        section_id: str | int,
        page_size: int = 5000,
    ) -> Iterable[PlexApiTrackResponse]:
        """Fetch all tracks in a Plex library section, paginated.

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
            response = self.session.request(
                "GET",
                f"{self.session.server_url}/library/sections/{section_id}/all",
                params={
                    "type": PlexMediaTypes.TRACK.value,
                    "X-Plex-Container-Start": start,
                    "X-Plex-Container-Size": page_size,
                },
            )
            response.raise_for_status()
            tracks = response.json()["MediaContainer"].get("Metadata", [])
            if len(tracks) < page_size:
                yield from tracks
                break
            num_fetched += len(tracks)
            start += page_size

            # log some progress
            total_size = response.json()["MediaContainer"].get("totalSize", 0)
            if total_size != 0:
                log.debug(
                    f"Fetched {num_fetched} of {total_size} tracks"
                    " from section {section_id}."
                )

            yield from tracks

        return

    def fetch_tracks_by_path(
        self,
        file_path: Path | str,
        section_id: str | int,
    ) -> list[PlexApiTrackResponse]:
        """Fetch a track from Plex by its file path, within a given library.

        Parameters
        ----------
        file_path : str
            The full file path to search for.
        section_id : str | int
            The name or id of the Plex library (section).

        Returns
        -------
        dict: The track metadata, or None if not found.
        """
        file_path = Path(file_path).resolve()
        encoded_path = quote(str(file_path))

        response = self.session.request(
            "GET",
            f"{self.session.server_url}/library/sections/{section_id}/all",
            params={"type": PlexMediaTypes.TRACK.value, "filename": encoded_path},
        )
        response.raise_for_status()
        return response.json()["MediaContainer"].get("Metadata", [])

    def fetch_track(self, track_id: str | int) -> PlexApiTrackResponse:
        """Fetch a specific track by its ID.

        Parameters
        ----------
        track_id : str | int
            The ID of the Plex track to fetch.

        Returns
        -------
        dict: The track metadata.
        """

        response = self.session.request(
            "GET", f"{self.session.server_url}/library/metadata/{track_id}"
        )
        response.raise_for_status()
        track_data = response.json()["MediaContainer"].get("Metadata", [])
        if len(track_data) == 0:
            raise ValueError(f"Track with ID '{track_id}' not found.")
        if len(track_data) > 1:
            log.error(
                f"Multiple tracks found for ID '{track_id}'. Returning the first one."
            )
        return track_data[0]


class ConvertsApi:
    """Utility functions to convert between different Plex API identifiers."""

    def __init__(self, session: PlexApiSession, api: PlexApi) -> None:
        self.session = session
        self.api = api

    def section_name_to_id(self, section_name_or_id: str | int) -> int:
        """Convert a Plex library section name to its ID.

        This also validates that the section exists!

        Parameters
        ----------
        section_name : str | int
            The name or ID of the Plex library section.

        Note on ids and rating keys (strings vs ints):
        - Plex uses ratingKey as a unique identifier for items, which is a string.
        - However, some endpoints like `/library/sections/5` give you the id of the
          section as `'librarySectionID': 5` so we are quite sure
          that they are always integers.

        Returns
        -------
        int: The ID of the Plex library section.
        """
        try:
            section_id = int(section_name_or_id)
            self.api.section(section_id)  # raises if invalid
            return section_id
        except ValueError:
            sections = self.api.sections()["MediaContainer"].get("Directory", [])
            for section in sections:
                if section.get("title") == section_name_or_id:
                    section_id = int(section.get("key"))
                    log.debug(
                        f"Resolved section {section_id} with title"
                        f" '{section.get('title')}'."
                    )
                    return section_id
            raise ValueError(f"Library '{section_name_or_id}' not found.")

    def playlist_name_to_id(self, playlist_name_or_id: str | int) -> int:
        """Resolve a playlist ID from a name or return the ID if already numeric."""
        try:
            playlist_id = int(playlist_name_or_id)
            response = self.session.request(
                "GET", f"{self.session.server_url}/playlists/{playlist_id}"
            )
            response.raise_for_status()
        except ValueError:
            for playlist in self.api.playlist.fetch_playlists():
                if playlist.get("title") == playlist_name_or_id and (
                    playlist.get("type") == "playlist"
                ):
                    playlist_id = int(playlist["ratingKey"])
                    log.debug(
                        f"Resolved playlist {playlist_id} with title"
                        f" '{playlist.get('title')}'."
                    )
                    return playlist_id

            raise ValueError(f"Playlist '{playlist_name_or_id}' not found.")
        return playlist_id
