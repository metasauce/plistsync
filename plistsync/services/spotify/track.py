import re
from dataclasses import dataclass
from typing import Self

from plistsync.core import Track, TrackID, TrackInfo
from plistsync.core.ids import ISRC
from plistsync.services.spotify.api_types import (
    AddedBy,
    SpotifyApiPlaylistTrack,
    SpotifyApiTrackResponse,
)


@dataclass(frozen=True)
class SpotifyTrackID(TrackID):
    """A Spotify track identifier."""

    id: str

    @property
    def url(self) -> str:
        """Public web URL."""
        return f"https://open.spotify.com/track/{self.id}"

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse from URL, URI, or raw ID."""
        value = value.strip()
        # URL (https://open.spotify.com/track/<id>)
        if m := re.search(r"spotify\.com/track/([a-zA-Z0-9]{22})", value):
            return cls(m.group(1))
        # URI (spotify:track:<id>)
        if m := re.match(r"spotify:(?:track:)?([a-zA-Z0-9]{22})$", value):
            return cls(m.group(1))
        # Plain ID
        if re.fullmatch(r"[a-zA-Z0-9]{22}", value):
            return cls(value)
        raise ValueError(f"Invalid Spotify track id: {value!r}")

    @property
    def serial(self) -> str:
        """Plistsync's internal representation for trackid on Spotify."""
        return f"spotify:track:{self.id}"

    def __str__(self) -> str:
        """Compact display, understood by Spotify API."""
        return self.id


class SpotifyTrack(Track):
    """A track in Spotify.

    Represents a Spotify track object as returned by the Spotify Web API.
    """

    data: SpotifyApiTrackResponse

    def __init__(self, data: SpotifyApiTrackResponse):
        """Initialize a SpotifyTrack with the given data.

        Expected data comes from the spotify API, e.g. from
        `GET /tracks/{id}` or `GET /playlists/{playlist_id}/tracks`.
        """

        self.data = data

    @property
    def info(self) -> TrackInfo:
        return TrackInfo(
            title=self.data["name"],
            artists=[artist["name"] for artist in self.data.get("artists", [])],
            albums=[self.data.get("album", {}).get("name", "")],
        )

    @property
    def ids(self) -> frozenset[TrackID]:
        idents: set[TrackID] = {SpotifyTrackID(self.data["id"])}
        external_ids = self.data.get("external_ids", {})
        if isrc := external_ids.get("isrc"):
            idents.add(ISRC(isrc))
        return frozenset(idents)

    @property
    def name(self) -> str:
        """The name of the track."""
        return self.data["name"]

    @property
    def id(self) -> str:
        """The Spotify ID of the track."""
        return self.data["id"]

    @property
    def uri(self) -> str:
        return self.data["uri"]


class SpotifyPlaylistTrack(SpotifyTrack):
    """A track in a Spotify playlist.

    Represents a Spotify track object as returned by the Spotify Web API
    when fetching playlist items.
    """

    added_at: str | None
    """The date and time the track was added to the playlist."""

    added_by: AddedBy | None
    """The user who added the track to the playlist."""

    is_local: bool = False

    def __init__(self, data_or_track: SpotifyApiPlaylistTrack | SpotifyTrack):
        """Initialize a SpotifyPlaylistTrack with the given data.

        Expected data comes from the spotify API, e.g. from
        `GET /playlists/{playlist_id}/tracks`.

        """
        if isinstance(data_or_track, SpotifyTrack):
            super().__init__(data_or_track.data)
            self.added_at = None
            self.added_by = None
            self.is_local = False
            return

        self.added_at = data_or_track.get("added_at", None)
        self.added_by = data_or_track.get("added_by", None)
        self.is_local = data_or_track.get("is_local", False)

        # TODO: Episode handling?
        super().__init__(data_or_track["track"])  # type: ignore[arg-type]
