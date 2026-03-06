from collections.abc import Iterable
from typing import overload

from requests import HTTPError
from typing_extensions import override

from plistsync.core import GlobalTrackIDs
from plistsync.core.collection import (
    GlobalLookup,
    LibraryCollection,
)
from plistsync.logger import log

from .api import SpotifyApi, extract_spotify_playlist_id
from .playlist import SpotifyPlaylistCollection
from .track import SpotifyTrack


class SpotifyLibraryCollection(LibraryCollection[SpotifyTrack], GlobalLookup):
    """A collection representing the full spotify library.

    It is not possible to add or remove items from this collection. Also iteration
    is not supported, as the library is basically infinite.
    """

    api: SpotifyApi

    def __init__(self) -> None:
        self.api = SpotifyApi()

    # ------------------------ LibraryCollection protocol ------------------------ #

    @property
    def playlists(self) -> Iterable[SpotifyPlaylistCollection]:
        """Get all playlists of the current user.

        This can take quite some time, as it fetches all playlists and their tracks.
        """
        return [
            SpotifyPlaylistCollection.from_response_data(
                self,
                playlist,
            )
            for playlist in self.api.user.get_playlists(preload=False)
        ]

    @overload
    def get_playlist(self, *, name: str) -> SpotifyPlaylistCollection | None: ...

    @overload
    def get_playlist(self, *, id: str) -> SpotifyPlaylistCollection: ...

    @overload
    def get_playlist(self, *, url: str) -> SpotifyPlaylistCollection: ...

    @overload
    def get_playlist(self, *, uri: str) -> SpotifyPlaylistCollection: ...

    @override
    def get_playlist(
        self,
        name: str | None = None,
        id: str | None = None,
        url: str | None = None,
        uri: str | None = None,
    ) -> SpotifyPlaylistCollection | None:
        """Get a specific playlist.

        One of the kwargs must be given. Either search
        by name or get by id/url/uri.

        Will raise on id/url/uri not found but return None if
        search by name not found.
        """

        if sum(arg is not None for arg in [name, id, url, uri]) != 1:
            raise ValueError("Exactly one of name, id, url, or uri must be provided")

        if url is not None:
            id = extract_spotify_playlist_id(url)
        if uri is not None:
            id = extract_spotify_playlist_id(uri)

        # Resolve name to id
        if name is not None:
            plists = self.api.user.get_playlists(preload=False)
            for plist in plists:
                if plist["name"] == name:
                    id = plist["id"]
                    break

            if id is None:
                # For searches we want to return None if not found
                log.debug(f"Could not find playlist with name '{name}'")
                return None

        # This should never realistically happen -> assert instead of error
        assert id is not None, "ID must be set after resolving name/url/uri"

        #  Direct ID lookup (fastest path)
        return SpotifyPlaylistCollection.from_response_data(
            self,
            self.api.playlist.get(id),
        )

    # --------------------------- GlobalLookup protocol -------------------------- #

    def find_by_global_ids(self, global_ids: GlobalTrackIDs) -> SpotifyTrack | None:
        """Find a track by its global ID.

        Prioritizes spotify_id, but also supports lookup by isrc if available.
        """
        if spotify_id := global_ids.get("spotify_id"):
            try:
                return SpotifyTrack(self.api.track.get(spotify_id))
            except HTTPError as e:
                if e.response.status_code == 404:
                    log.debug(f"Could not find track by spotify ID {spotify_id}: {e}")
                else:
                    raise

        if isrc := global_ids.get("isrc"):
            if data := self.api.track.get_by_isrc(isrc):
                return SpotifyTrack(data)

        return None

    def find_many_by_global_ids(
        self, global_ids_list: Iterable[GlobalTrackIDs]
    ) -> Iterable[SpotifyTrack | None]:
        """Find many tracks by their global IDs.

        Prioritizes spotify_id, but also supports lookup by isrc if available.
        Performs batch lookup for all tracks with spotify_id if possible.
        """
        found_tracks: dict[int, SpotifyTrack] = {}
        # avoid consuming this, we iterate twice.
        global_ids_list = list(global_ids_list)

        # Get all with spotify id for batch lookup
        idxes = []
        spotify_ids: list[str] = []
        for idx, gids in enumerate(global_ids_list):
            if "spotify_id" in gids:
                idxes.append(idx)
                spotify_ids.append(gids["spotify_id"])

        if spotify_ids:
            tracks = self.api.track.get_many(spotify_ids)

            if len(spotify_ids) != len(tracks):
                log.warning(
                    f"Expected {len(spotify_ids)} tracks but received {len(tracks)} "
                    "tracks as result from spotify batch lookup."
                )

            for idx, track in zip(idxes, tracks):
                found_tracks[idx] = SpotifyTrack(track)

        # Individual lookup for all missing tracks
        for idx, gids in enumerate(global_ids_list):
            if idx in found_tracks:
                yield found_tracks[idx]
            else:
                yield self.find_by_global_ids(gids)
