from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from plistsync.core import GlobalTrackIDs, Track
from plistsync.core.track import LocalTrackIDs, TrackInfo
from plistsync.services.tidal.api_types import (
    PlaylistsItemsResourceIdentifierMeta,
    TrackResource,
)

from .api import LookupDict


class TidalTrack(Track):
    """TidalTrack is a track object that represents a track we got from the tidal api.

    We opted to just use the returned data and included relationships from the tidal api
    as it is. For simplicity we add artists and albums as keys to the data dict see
    `get_tracks`.

    As usual with all Track objects, this class implements all abstract methods from
    the Track class to get the different properties of the track if available.
    """

    data: TrackResource
    data_lookup: LookupDict

    def __init__(self, data: TrackResource, data_lookup: LookupDict | None = None):
        self.data = data
        self.data_lookup = data_lookup or {}

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def name(self) -> str | None:
        return self.data.get("attributes", {}).get("title")

    @property
    def artists(self) -> list[str]:
        return [
            str(a.get("attributes", {}).get("name"))
            for a in self._raw_artists
            if a.get("attributes", {}).get("name") is not None
        ]

    # ---------------------------------------------------------------------------- #
    #                        Helper methods (tidal specific)                       #
    # ---------------------------------------------------------------------------- #

    @property
    def _raw_artists(self) -> Iterable[dict]:
        yield from filter(
            lambda x: x.get("type") == "artists", self.data_lookup.values()
        )

    @property
    def _raw_albums(self) -> Iterable[dict]:
        yield from filter(
            lambda x: x.get("type") == "albums", self.data_lookup.values()
        )

    # ---------------------------------------------------------------------------- #
    #                                 ABC methods                                  #
    # ---------------------------------------------------------------------------- #

    @property
    def info(self) -> TrackInfo:
        return TrackInfo(
            title=self.data.get("attributes", {}).get("title"),
            artists=self.artists,
            albums=[
                str(a.get("attributes", {}).get("title"))
                for a in self._raw_albums
                if a.get("attributes", {}).get("title") is not None
            ],
        )

    @property
    def local_ids(self) -> LocalTrackIDs:
        return LocalTrackIDs()

    @property
    def global_ids(self) -> GlobalTrackIDs:
        idents: GlobalTrackIDs = {}

        if isrc := self.data.get("attributes", {}).get("isrc"):
            idents["isrc"] = isrc

        if tidal_id := self.data.get("id"):
            idents["tidal_id"] = tidal_id

        return idents


class TidalPlaylistTrack(TidalTrack):
    """A track in a Tidal playlist.

    Represents a Tidal track object as returned by the Tidal API
    when fetching playlist items.
    """

    meta: PlaylistsItemsResourceIdentifierMeta

    def __init__(
        self,
        data_or_track: TrackResource | TidalTrack,
        data_lookup: LookupDict | None = None,
        meta: PlaylistsItemsResourceIdentifierMeta | None = None,
    ):
        """Initialize a TidalPlaylistTrack with the given data.

        Expected data comes from the Tidal API, e.g. from
        playlist items endpoint.
        """
        self.meta = meta or {}
        if isinstance(data_or_track, TidalTrack):
            super().__init__(data_or_track.data, data_or_track.data_lookup)
        else:
            super().__init__(data_or_track, data_lookup=data_lookup)

    @property
    def added_at(self) -> datetime | None:
        """The datetime when the track was added to the playlist.

        Can be None if the track is not yet associated with an
        online playlist.
        """
        added_at: str | datetime | None = self.meta.get("addedAt", None)
        if isinstance(added_at, str):
            # format: 2021-05-08T10:17:50.932847Z
            added_at = datetime.strptime(added_at, "%Y-%m-%dT%H:%M:%S.%fZ")
        return added_at

    @property
    def item_id(self) -> str | None:
        """Item id of the track within a playlist.

        Can be None if the track is not yet associated with an
        online playlist.
        """
        return self.meta.get("itemId", None)
