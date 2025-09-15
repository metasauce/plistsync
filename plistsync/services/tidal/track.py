from __future__ import annotations

from datetime import datetime
from typing import Iterable

from plistsync.core import GlobalTrackIDs, Track
from plistsync.core.track import LocalTrackIDs, TrackInfo

from ...errors import NotFoundError
from ...logger import log
from .api import LookupDict


class TidalTrack(Track):
    """TidalTrack is a track object that represents a track we got from the tidal api.

    We opted to just use the returned data and included relationships from the tidal api as it is.
    For simplicity we add artists and albums as keys to the data dict see `get_tracks`.

    As usual with all Track objects, this class implements all abstract methods from the Track class
    to get the different properties of the track if available.
    """

    data: dict
    data_lookup: LookupDict

    def __init__(self, data: dict, data_lookup: LookupDict | None = None):
        self.data = data
        self.data_lookup = data_lookup or {}

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
        for artist in filter(
            lambda x: x.get("type") == "artists", self.data_lookup.values()
        ):
            yield artist

    @property
    def _raw_albums(self) -> Iterable[dict]:
        for album in filter(
            lambda x: x.get("type") == "albums", self.data_lookup.values()
        ):
            yield album

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

    added_at: datetime
    """The date and time the track was added to the playlist."""

    def __init__(self, data: dict, data_lookup: LookupDict, added_at: str | datetime):
        """Initialize a TidalPlaylistTrack with the given data.

        Expected data comes from the Tidal API, e.g. from
        playlist items endpoint.
        """
        # format: 2021-05-08T10:17:50.932847Z
        if isinstance(added_at, str):
            self.added_at = datetime.strptime(added_at, "%Y-%m-%dT%H:%M:%S.%fZ")
        elif isinstance(added_at, datetime):
            self.added_at = added_at
        else:
            raise ValueError(f"Invalid added_at value: {added_at}")

        super().__init__(data, data_lookup=data_lookup)
