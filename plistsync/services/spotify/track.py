from plistsync.core import GlobalTrackIDs, Track
from plistsync.core.track import LocalTrackIDs, TrackInfo
from plistsync.services.spotify.api_types import (
    AddedBy,
    SpotifyApiPlaylistTrack,
    SpotifyApiTrackResponse,
)


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

        if data.get("type") != "track":
            raise ValueError("Data is not a Spotify track object")

        self.data = data

    @property
    def info(self) -> TrackInfo:
        return TrackInfo(
            title=self.data["name"],
            artists=[artist["name"] for artist in self.data.get("artists", [])],
            albums=[self.data.get("album", {}).get("name", "")],
        )

    @property
    def local_ids(self) -> LocalTrackIDs:
        return LocalTrackIDs()

    @property
    def global_ids(self) -> GlobalTrackIDs:
        idents: GlobalTrackIDs = {
            "spotify_id": self.data["id"],
        }

        # In theory ean and upc are also available here
        external_ids = self.data.get("external_ids", {})
        if isrc := external_ids.get("isrc"):
            idents["isrc"] = isrc

        return idents

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

        super().__init__(data_or_track["track"])
