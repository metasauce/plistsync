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

from .api import TidalApi
from .playlist import TidalPlaylist, TidalPlaylistID
from .track import TidalTrack, TidalTrackID


class TidalLibrary(
    Library[TidalTrack, TidalPlaylist],
    IDLookup[TidalTrack],
):
    """A collection of Tidal library items."""

    api: TidalApi

    def __init__(self) -> None:
        self.api = TidalApi()

    # ------------------------ LibraryCollection protocol ------------------------ #

    @property
    def playlists(self) -> Iterable[TidalPlaylist]:
        """Get all playlists of the current user.

        This can take quite some time, as it fetches all playlists and their tracks.
        """
        playlists, lookup = self.api.playlist.get_many_by_user(self.api.user.me()["id"])
        return [TidalPlaylist(self, pl, lookup) for pl in playlists]

    @overload
    def get_playlist(self, *, name: str | None = None) -> TidalPlaylist | None: ...
    @overload
    def get_playlist(
        self, *, id: PlaylistID | str | int | None = None
    ) -> TidalPlaylist | None: ...
    @overload
    def get_playlist(self, *, url: str | None = None) -> TidalPlaylist | None: ...

    def get_playlist(
        self,
        *,
        id: PlaylistID | str | int | None = None,
        name: str | None = None,
        url: str | None = None,
    ) -> TidalPlaylist | None:
        """Get a specific playlist.

        Exactly one of the kwargs must be given: name/id/url.

        Returns None if not found.
        """
        if sum(arg is not None for arg in [id, name, url]) != 1:
            raise ValueError("Exactly one of name, id, or url must be provided")

        raw: str | PlaylistID

        # resolve name via user playlists
        if name is not None:
            playlists, _ = self.api.playlist.get_many_by_user(
                self.api.user.me()["id"], include=[]
            )
            found = [p for p in playlists if p["attributes"]["name"] == name]
            if len(found) == 0:
                log.debug(f"No playlist found for name={name!r}")
                return None
            else:
                raw = found[0]["id"]

            if len(found) > 1:
                log.info(
                    f"Found more than one playlist with name {name!r}, using {raw}"
                )
        else:
            # exactly one guaranteed here!
            raw = id or url  # type: ignore[assignment]

        # normalize into PlaylistID
        if isinstance(raw, PlaylistID):
            playlist_id = raw
        else:
            try:
                playlist_id = TidalPlaylistID.parse(raw)
            except ValueError:
                log.warning(f"Invalid playlist id format: {raw!r}")
                return None

        try:
            return TidalPlaylist(
                self,
                *self.api.playlist.get(str(playlist_id)),
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
        tracks: Sequence[TidalTrack] | None = None,
    ):
        pl = TidalPlaylist(
            self,
            *self.api.playlist.create(name, description or ""),
        )

        if tracks:
            with pl.edit():
                pl.tracks = tracks

        return pl

    def has_playlist(self, name: str) -> bool:
        """Check if a playlist with the given name exists in the user's library."""
        for pl in self.api.playlist.get_many_by_user(
            self.api.user.me()["id"], include=[]
        )[0]:
            if pl["attributes"]["name"] == name:
                return True
        return False

    # --------------------------- IDLookup protocol ------------------------------ #

    def find_by_ids(self, ids: Iterable[TrackID]) -> TidalTrack | None:
        """Find a track by its identifiers.

        Prioritizes tidal ID lookups over ISRC lookups.
        """
        return list(self.find_many_by_ids([ids]))[0]

    def find_many_by_ids(
        self, track_ids_batch: Iterable[Iterable[TrackID]]
    ) -> Iterable[TidalTrack | None]:
        """Find many tracks by their identifiers.

        Prioritizes tidal ID lookups over ISRC lookups.
        """
        found_tracks: dict[int, TidalTrack] = {}

        # avoid consuming this, we iterate twice.
        # inner: ids for one track, outer: tracks
        ids_list = [frozenset(ids) for ids in track_ids_batch]

        # Tidal ids batch lookup
        idxes: list[int] = []
        tidal_ids: list[str] = []
        for idx, ids in enumerate(ids_list):
            for tid in ids:
                if isinstance(tid, TidalTrackID):
                    idxes.append(idx)
                    tidal_ids.append(str(tid))
                    break

        if tidal_ids:
            tracks, lookup = self.api.tracks.get_many(tidal_ids)
            for idx, track in zip(idxes, tracks):
                if not track:
                    log.debug(f"Track with tidal_id '{tidal_ids[idx]}' not found")
                else:
                    found_tracks[idx] = TidalTrack(track, lookup)

        # ISRC batch lookup for remaining ids
        idxes = []
        isrcs: list[str] = []
        for idx, ids in enumerate(ids_list):
            if idx in found_tracks:
                continue
            for tid in ids:
                if isinstance(tid, ISRC):
                    idxes.append(idx)
                    isrcs.append(str(tid))
                    break

        if isrcs:
            tracks, lookup = self.api.tracks.get_many_by_isrc(isrcs)
            for idx, track in zip(idxes, tracks):
                if not track:
                    log.debug(f"Track with isrc '{isrcs[idx]}' not found")
                else:
                    found_tracks[idx] = TidalTrack(track, lookup)

        for idx, ids in enumerate(ids_list):
            yield found_tracks.get(idx, None)
