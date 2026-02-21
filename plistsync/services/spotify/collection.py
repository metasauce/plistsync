from __future__ import annotations

from collections.abc import Iterable
from typing import Self, overload

from typing_extensions import override

from plistsync.core import GlobalTrackIDs
from plistsync.core.collection import (
    GlobalLookup,
    LibraryCollection,
)
from plistsync.core.playlist import PlaylistCollection, PlaylistInfo
from plistsync.logger import log

from .api import SpotifyApi, extract_spotify_playlist_id
from .api_types import (
    PlaylistTracksBase,
    SpotifyApiPlaylistResponseBase,
    SpotifyApiPlaylistResponseFull,
    SpotifyApiPlaylistResponseSimplified,
    SpotifyApiPlaylistTrack,
)
from .track import SpotifyPlaylistTrack, SpotifyTrack


class SpotifyLibraryCollection(LibraryCollection, GlobalLookup):
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
            except Exception as e:
                log.debug(f"Could not find track by spotify ID {spotify_id}: {e}")

        if isrc := global_ids.get("isrc"):
            try:
                return SpotifyTrack(self.api.track.get_by_isrc(isrc))
            except Exception as e:
                log.debug(f"Could not find track by ISRC {isrc}: {e}")

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


class SpotifyPlaylistCollection(PlaylistCollection[SpotifyPlaylistTrack]):
    """A collection representing a spotify playlist."""

    library: SpotifyLibraryCollection

    # When the playlist is associated with an online playlist, we have the response.
    # Otherwise, we have at least a name via PlaylistInfo.
    # SpotifyApiPlaylistResponseBase does not contain tracks, we keep them
    # separate in PlaylistTracksBase to simplify type checking.
    data: tuple[SpotifyApiPlaylistResponseBase, PlaylistTracksBase] | PlaylistInfo

    # ----------------------------- Constructors ----------------------------- #

    def __init__(
        self,
        library: SpotifyLibraryCollection,
        name: str,
        description: str | None = None,
        tracks: list[SpotifyPlaylistTrack] | None = None,
    ):
        """Initialize a SpotifyPlaylistCollection, without creating it online."""

        self.library = library
        self._tracks = tracks or []  # do not set to None, we do not want to fetch!
        self.data = PlaylistInfo(name=name, description=description)

    @classmethod
    def from_response_data(
        cls,
        library: SpotifyLibraryCollection,
        data: SpotifyApiPlaylistResponseSimplified | SpotifyApiPlaylistResponseFull,
    ) -> Self:
        """
        Create a new instance of Spotify playlist from a given api response.

        The resulting instance will have id and we consider it is available online.
        """
        pl = cls(
            library,
            name=data["name"],
            description=data.get("description"),
        )
        tracks_obj: PlaylistTracksBase = data.get("tracks", {})
        tracks_obj_items: list[SpotifyApiPlaylistTrack] = tracks_obj.get("items", [])  # type: ignore[assignment]
        if len(tracks_obj_items) == tracks_obj.get("total", 0):
            pl._tracks = [
                SpotifyPlaylistTrack(
                    item,
                )
                for item in tracks_obj_items
            ]
        else:
            pl._tracks = None  # set to None to fetch on access

        if tracks_obj.get("items", None) is not None:
            del tracks_obj["items"]  # type: ignore
        pl.data = (data, tracks_obj)
        return pl

    # ----------------------- Properties and info logic ---------------------- #

    @property
    def online_data(
        self,
    ) -> tuple[SpotifyApiPlaylistResponseBase, PlaylistTracksBase] | None:
        """
        Indicate if this playlist is associated with it's online version.

        None if created with default constructor, but tuple once we have
        response data.
        """
        if isinstance(self.data, tuple):
            return self.data
        return None

    @property
    def id(self) -> str | None:
        """
        Playlist id.

        None if playlist is not associated with an online resource.
        """
        if data := self.online_data:
            return data[0]["id"]
        return None

    @property
    def api(self):
        return self.library.api

    @property
    def info(self) -> PlaylistInfo:
        if isinstance(self.data, tuple):
            data = self.data[0]
            info = PlaylistInfo()
            info["name"] = data["name"]
            if description := data.get("description"):
                info["description"] = description
            return info
        else:
            return self.data

    @info.setter
    def info(self, value: PlaylistInfo):
        if isinstance(self.data, tuple):
            data = self.data[0]
            data["name"] = value.get(
                "name",
                data.get("name", ""),
            )
            data["description"] = value.get(
                "description",
                data.get("description", None),
            )
        else:
            self.data = value

    # ---------------------------- Track lazy loading ---------------------------- #

    def _refetch_tracks(self) -> None:
        """Refetch the tracks from the online playlist.

        Only works if the playlist is online.
        """
        if not self.online_data:
            raise ValueError("Cannot refetch tracks for offline playlist")

        self._tracks = [
            SpotifyPlaylistTrack(item)
            for item in self.api.playlist._load_tracks(self.online_data[1])
        ]

    @property
    def tracks(self) -> list[SpotifyPlaylistTrack]:
        """Return the tracks in this playlist.

        Might load them from the API if not already loaded.
        """
        if self._tracks is None:
            self._refetch_tracks()

        return self._tracks or []

    @tracks.setter
    def tracks(self, value: list[SpotifyPlaylistTrack]) -> None:
        self._tracks = value

    def __len__(self) -> int:
        """Return the number of tracks in this playlist.

        Might load them from the API if not already loaded.
        """
        if data := self.online_data:
            return data[1].get("total", 0)
        return len(self.tracks)

    # ----------------------------- Remote operations ---------------------------- #

    @property
    def remote_associated(self) -> bool:
        """Indicate if the playlist is already linked to a remote (online) playlist."""
        return self.online_data is not None

    def _remote_create(self):
        """Create the playlist on the remote service."""
        pl_data = self.api.playlist.create(self.name, self.description or "")
        self.data = (pl_data, pl_data.get("tracks", {}))
        if self._tracks:
            self.api.playlist.add_tracks(
                pl_data["id"],
                track_uris=[t.uri for t in self._tracks],
            )
        self._refetch_tracks()  # Force refetch tracks

    def _remote_delete(self):
        if self.id is None:
            raise ValueError("Playlist must be online to call remote delete!")
        self.api.playlist.delete(self.id)

    def _remote_insert_track(
        self,
        idx: int,
        track: SpotifyPlaylistTrack,
        live_list: list[SpotifyPlaylistTrack],
    ) -> None:
        if not self.id:
            raise ValueError("Id must be set to call remote insert!")
        self.api.playlist.add_tracks(self.id, [track.uri], idx)

    def _remote_delete_track(
        self,
        idx: int,
        track: SpotifyPlaylistTrack,
        live_list: list[SpotifyPlaylistTrack],
    ):
        if not self.id:
            raise ValueError("Id must be set to call remote delete!")
        self.api.playlist.remove_tracks(self.id, [track.uri], [idx])

    def _remote_move_track(
        self,
        old_idx: int,
        new_idx: int,
        track: SpotifyPlaylistTrack,
        live_list: list[SpotifyPlaylistTrack],
    ) -> None:
        if not self.id:
            raise ValueError("Id must be set to call remote move!")
        self.api.playlist.reorder_tracks(
            playlist_id=self.id,
            range_start=old_idx,
            range_length=1,
            insert_before=new_idx,
        )

    def _remote_update_metadata(self, new_name=None, new_description=None):
        if not self.id:
            raise ValueError("Id must be set to call remote update!")
        self.api.playlist.update(
            self.id,
            new_name,
            new_description,
        )

    @staticmethod
    def _track_key(track: SpotifyPlaylistTrack):
        return track.id
