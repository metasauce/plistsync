from collections.abc import Iterable, Sequence
from typing import overload

from requests import HTTPError

from plistsync.core import TrackID
from plistsync.core.collection import (
    IDLookup,
    Library,
)
from plistsync.core.ids import ISRC
from plistsync.core.playlist import PlaylistID
from plistsync.logger import log

from .api import SpotifyApi
from .playlist import SpotifyPlaylist, SpotifyPlaylistID
from .track import SpotifyTrack, SpotifyTrackID


class SpotifyLibrary(
    Library[SpotifyTrack, SpotifyPlaylist],
    IDLookup[SpotifyTrack],
):
    """A collection representing the full spotify library.

    It is not possible to add or remove items from this collection. Also iteration
    is not supported, as the library is basically infinite.
    """

    api: SpotifyApi

    def __init__(self) -> None:
        self.api = SpotifyApi()

    # ------------------------ LibraryCollection protocol ------------------------ #

    @property
    def playlists(self) -> Iterable[SpotifyPlaylist]:
        """Get all playlists of the current user.

        This can take quite some time, as it fetches all playlists and their tracks.
        """
        return [
            SpotifyPlaylist(
                self,
                playlist,
            )
            for playlist in self.api.user.get_playlists(preload=False)
        ]

    @overload
    def get_playlist(self, *, name: str | None = None) -> SpotifyPlaylist | None: ...
    @overload
    def get_playlist(
        self, *, id: PlaylistID | str | None = None
    ) -> SpotifyPlaylist | None: ...
    @overload
    def get_playlist(self, *, url: str | None = None) -> SpotifyPlaylist | None: ...
    @overload
    def get_playlist(self, *, uri: str | None = None) -> SpotifyPlaylist | None: ...

    def get_playlist(
        self,
        *,
        name: str | None = None,
        id: PlaylistID | str | None = None,
        url: str | None = None,
        uri: str | None = None,
    ) -> SpotifyPlaylist | None:
        """Get a specific playlist.

        Exactly one of the kwargs must be given: name/id/url/uri.

        Returns None if not found.
        """
        if sum(arg is not None for arg in [id, name, url, uri]) != 1:
            raise ValueError("Exactly one of name, id, uri, or url must be provided")

        raw: str | PlaylistID

        # resolve name via user playlists
        if name is not None:
            for plist in self.api.user.get_playlists(preload=False):
                if plist["name"] == name:
                    raw = plist["id"]
                    break
            else:
                log.debug(f"No playlist found for name={name!r}")
                return None
        else:
            # exactly one guaranteed here!
            raw = id or url or uri  # type: ignore[assignment]

        # normalize into PlaylistID
        if isinstance(raw, PlaylistID):
            playlist_id = raw
        else:
            try:
                playlist_id = SpotifyPlaylistID.parse(raw)
            except ValueError:
                log.warning(f"Invalid playlist id format: {raw!r}")
                return None

        # enforce Spotify boundary
        if not isinstance(playlist_id, SpotifyPlaylistID):
            raise TypeError(
                f"Expected SpotifyPlaylistID, got {type(playlist_id).__name__}"
            )

        try:
            return SpotifyPlaylist(
                self,
                self.api.playlist.get(str(playlist_id)),
            )
        except HTTPError as e:
            log.debug(
                f"Failed to get playlist for {playlist_id=}, likely invalid id: {e}"
            )
            return None

    def create_playlist(
        self,
        name: str,
        description: str | None = None,
        tracks: Sequence[SpotifyTrack] | None = None,
    ):
        pl = SpotifyPlaylist(
            self,
            self.api.playlist.create(name, description or ""),
        )

        if tracks:
            with pl.edit():
                pl.tracks = list(tracks)

        return pl

    # --------------------------- IDLookup protocol ------------------------------ #

    def find_by_ids(self, ids: Iterable[TrackID]) -> SpotifyTrack | None:
        """Find a track by its identifiers.

        Prioritizes Spotify ID lookups over ISRC lookups.
        """
        for spotify_id in (tid for tid in ids if isinstance(tid, SpotifyTrackID)):
            try:
                return SpotifyTrack(self.api.track.get(str(spotify_id)))
            except HTTPError as e:
                if e.response.status_code == 404:
                    log.debug(f"Could not find track by spotify ID {spotify_id}: {e}")
                else:
                    raise

        for isrc in (tid for tid in ids if isinstance(tid, ISRC)):
            if data := self.api.track.get_by_isrc(str(isrc)):
                return SpotifyTrack(data)

        return None

    def find_many_by_ids(
        self, track_ids_batch: Iterable[Iterable[TrackID]]
    ) -> Iterable[SpotifyTrack | None]:
        """Find many tracks by their identifiers.

        Prioritizes Spotify ID lookups over ISRC lookups.
        Performs batch lookup for all tracks with Spotify IDs if possible.
        """
        found_tracks: dict[int, SpotifyTrack] = {}

        # avoid consuming this, we iterate twice.
        # inner: ids for one track, outer: tracks
        ids_list = [frozenset(ids) for ids in track_ids_batch]

        # Spotify IDs batch lookup
        idxes: list[int] = []
        spotify_ids: list[str] = []
        for idx, ids in enumerate(ids_list):
            for tid in ids:
                if isinstance(tid, SpotifyTrackID):
                    idxes.append(idx)
                    spotify_ids.append(str(tid))
                    break

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
        for idx, ids in enumerate(ids_list):
            if idx in found_tracks:
                yield found_tracks[idx]
            else:
                yield self.find_by_ids(ids)
