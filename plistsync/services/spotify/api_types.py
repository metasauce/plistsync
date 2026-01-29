from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class ExternalUrls(TypedDict):
    """External URLs for Spotify objects."""

    spotify: str


class Image(TypedDict):
    """Image object for albums, artists, etc."""

    url: str
    width: int
    height: int


class Artist(TypedDict):
    """Artist object."""

    external_urls: ExternalUrls
    href: str
    id: str
    name: str
    type: Literal["artist"]
    uri: str


class Album(TypedDict):
    """Album object."""

    available_markets: list[str]
    type: Literal["album"]
    album_type: Literal["album", "single", "compilation"]
    href: str
    id: str
    images: list[Image]
    name: str
    release_date: str
    release_date_precision: Literal["year", "month", "day"]
    uri: str
    artists: list[Artist]
    external_urls: ExternalUrls
    total_tracks: int


class ExternalIds(TypedDict):
    """External IDs for tracks."""

    isrc: NotRequired[str]
    ean: NotRequired[str]
    upc: NotRequired[str]


class SpotifyApiTrackResponse(TypedDict):
    """Track object."""

    preview_url: str | None
    available_markets: list[str]
    explicit: bool
    type: Literal["track"]
    episode: bool
    track: bool
    album: Album
    artists: list[Artist]
    disc_number: int
    track_number: int
    duration_ms: int
    external_ids: ExternalIds
    external_urls: ExternalUrls
    href: str
    id: str
    name: str
    popularity: int
    uri: str
    is_local: bool


class AddedBy(TypedDict):
    """User who added a track to a playlist."""

    external_urls: ExternalUrls
    href: str
    id: str
    type: Literal["user"]
    uri: str


class SpotifyApiPlaylistTrack(TypedDict):
    """Track item within a playlist."""

    added_at: str
    added_by: AddedBy
    is_local: bool
    primary_color: str | None
    track: SpotifyApiTrackResponse
    video_thumbnail: dict[str, Any]  # Usually {"url": None}


class PlaylistTracks(TypedDict):
    """Tracks object within a playlist."""

    href: str
    items: list[SpotifyApiPlaylistTrack]
    limit: int
    next: str | None
    offset: int
    previous: str | None
    total: int


class Owner(TypedDict):
    """Playlist owner."""

    external_urls: ExternalUrls
    href: str
    id: str
    type: Literal["user", "artist"]
    uri: str
    display_name: NotRequired[str]


class SpotifyApiPlaylistResponseBase(TypedDict):
    """Type shared by the full and simplified response."""

    collaborative: bool
    description: str | None
    external_urls: ExternalUrls
    href: str
    id: str
    images: list[Image]
    name: str
    owner: Owner
    public: bool
    snapshot_id: str
    type: Literal["playlist"]
    uri: str


class SpotifyApiPlaylistResponseFull(SpotifyApiPlaylistResponseBase):
    """Full playlist object."""

    tracks: PlaylistTracks


class SpotifyApiPlaylistResponseSimplified(SpotifyApiPlaylistResponseBase):
    """Simplified playlist object (without full tracks)."""

    tracks: dict[str, Any]  # TODO: propper types Simplified tracks info


class UserProfile(TypedDict):
    """User profile object."""

    display_name: str | None
    external_urls: ExternalUrls
    href: str
    id: str
    images: NotRequired[list[Image]]
    type: Literal["user"]
    uri: str
    followers: NotRequired[dict[str, Any]]  # {"href": None, "total": int}


class SearchTracksResponse(TypedDict):
    """Response from track search."""

    tracks: dict[str, Any]  # Contains "items", "limit", "next", etc.


class TracksResponse(TypedDict):
    """Response for multiple tracks."""

    tracks: list[SpotifyApiTrackResponse]


class SnapshotResponse(TypedDict):
    """Response from playlist modification operations."""

    snapshot_id: str
