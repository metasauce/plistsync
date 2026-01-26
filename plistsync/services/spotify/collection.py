from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Self

from plistsync.core import GlobalTrackIDs
from plistsync.core.collection import (
    GlobalLookup,
    LibraryCollection,
)
from plistsync.core.playlist import PlaylistCollection
from plistsync.logger import log
from plistsync.services.spotify.api_types import SpotifyApiPlaylistResponse

from .api import SpotifyApi
from .track import SpotifyPlaylistTrack, SpotifyTrack


class SpotifyLibraryCollection(LibraryCollection, GlobalLookup):
    """A collection representing the full spotify library.

    It is not possible to add or remove items from this collection. Also iteration
    is not supported, as the library is basically infinite.
    """

    def __init__(self) -> None:
        self.api = SpotifyApi()

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
            for playlist in self.api.user.get_playlists()
        ]

    def get_playlist(
        self, name: str | Path, allow_name=True
    ) -> SpotifyPlaylistCollection | None:
        """Get a specific playlist by its ID."""

        if isinstance(name, Path):
            raise ValueError("Playlist name cannot be a Path")

        plist_identifier: str = name

        # We fetch all playlists by the user and check if the name matches
        if allow_name:
            plists = self.api.user.get_playlists(True)
            for plist in plists:
                if plist["name"] == plist_identifier:
                    plist_identifier = plist["id"]
                    break

        try:
            return SpotifyPlaylistCollection.from_response_data(
                self,
                self.api.playlist.get(plist_identifier),
            )
        except Exception as e:
            log.debug(f"Could not fetch playlist {name}: {e}")
            return None

    # ------------------------------- global lookup ------------------------------ #

    def find_by_global_ids(self, global_ids: GlobalTrackIDs) -> SpotifyTrack | None:
        """Find a track by its global ID.

        Prioritizes spotify_id, but also supports lookup by isrc if available.
        """
        if spotify_id := global_ids.get("spotify_id"):
            try:
                return SpotifyTrack(self.api.track.get(spotify_id))
            except Exception as e:
                log.debug(f"Could not find track by spotify ID {spotify_id}: {e}")

        if isrc := global_ids.get("isrc"):
            try:
                return SpotifyTrack(self.api.track.get_by_isrc(isrc))
            except Exception as e:
                log.debug(f"Could not find track by ISRC {isrc}: {e}")

        return None

    def find_many_by_global_ids(
        self, global_ids_list: list[GlobalTrackIDs]
    ) -> Iterable[SpotifyTrack | None]:
        """Find many tracks by their global IDs.

        Prioritizes spotify_id, but also supports lookup by isrc if available.
        Performs batch lookup for all tracks with spotify_id if possible.
        """
        found_tracks: dict[int, SpotifyTrack] = {}

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


class SpotifyPlaylistCollection(PlaylistCollection[SpotifyPlaylistTrack]):
    """A collection representing a spotify playlist."""

    _name: str
    _description: str | None
    _tracks: list[SpotifyPlaylistTrack]
    library: SpotifyLibraryCollection

    # convention: when id is None, the playlist has not been created online
    # (or assoicted with an existing online playlist)
    id: str | None

    def __init__(
        self,
        library: SpotifyLibraryCollection,
        name: str,
        description: str | None = None,
        tracks: list[SpotifyPlaylistTrack] | None = None,
    ):
        """Initialize a SpotifyPlaylistCollection."""

        self.library = library
        self._name = name
        self._description = description
        self._tracks = tracks or []
        self.id = None

    @property
    def api(self):
        return self.library.api

    @classmethod
    def from_url(cls, library: SpotifyLibraryCollection, url: str):
        """Get playlist via its url, uri or id.

        TODO: regex id from url
        """
        pass

    @classmethod
    def from_response_data(
        cls,
        library: SpotifyLibraryCollection,
        data: SpotifyApiPlaylistResponse,
    ) -> Self:
        """Create a new empty Spotify playlist with the given name and description."""
        name = data["name"]
        description = data.get("description")

        tracks: list[SpotifyPlaylistTrack] = []
        items = data.get("tracks", {}).get("items", [])
        for item in items:
            # It is possible to add episodes or other non-track items to a playlist
            # We add a placeholder to keep the order
            if item["track"]["type"] == "track":
                tracks.append(SpotifyPlaylistTrack(item))
            else:
                log.debug(
                    f"Skipping non-track item in playlist "
                    f"'{name}': {item['track']['type']}"
                )

        pl = cls(
            library,
            name,
            description,
            tracks,
        )
        pl.id = data["id"]
        return pl

    @property
    def name(self) -> str:
        """The name of the playlist."""
        return self._name

    @name.setter
    def name(self, value: str):
        self._name = value

    @property
    def description(self) -> str | None:
        """The description of the playlist."""
        return self._description

    @description.setter
    def description(self, value: str | None):
        self._description = value

    def _remote_insert_track(self, idx: int, track: SpotifyPlaylistTrack) -> None:
        raise NotImplementedError("Insert not implemented")

    def _remote_delete_track(self, idx: int, track: SpotifyPlaylistTrack):
        raise NotImplementedError("Delete not implemented")

    def _remote_update_metadata(self, new_name=None, new_description=None):
        raise NotImplementedError("Update not implemented")

    @staticmethod
    def _track_key(track: SpotifyPlaylistTrack):
        return track.id
