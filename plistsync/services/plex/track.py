from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath
from typing import ClassVar, Self

from plistsync.core import PathRewrite, Track, TrackID, TrackInfo
from plistsync.core.ids import FilePath, Scope
from plistsync.logger import log
from plistsync.services.plex.api_types import (
    PlexApiPlaylistTrackResponse,
    PlexApiTrackResponse,
)

from ..local.track import FileCache, LocalTrack


@dataclass(frozen=True)
class PlexTrackID(TrackID):
    """A Plex track identifier (rating key)."""

    # Only unique within a single server
    scope: ClassVar[Scope] = Scope.LOCAL

    id: str

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse from serial format or raw ID."""
        value = value.strip()
        if value.lower().startswith("plex:track:"):
            value = value[11:]
        if not value.isdigit():
            raise ValueError(f"Invalid Plex track id: {value!r}")
        return cls(value)

    @property
    def serial(self) -> str:
        """Plistsync's internal representation for trackid on Plex."""
        return f"plex:track:{self.id}"

    def __str__(self) -> str:
        """Compact display, understood by Plex API."""
        return self.id


class PlexTrack(Track):
    """
    Track on a plex media server.

    Ids are specific to one section (library) of one server instance.
    (No global lookups)

    For the Plex Service, we currently do not distinguish Tracks and PlaylistTracks.
    The reason is that tracks in plex playlists only get one single extra piece
    of information (the playlist_item_id), but we have no info about when they were
    added to the playlist etc.

    see also https://www.plexopedia.com/plex-media-server/api/library/music-albums-tracks/
    """

    data: PlexApiTrackResponse | PlexApiPlaylistTrackResponse

    def __init__(self, data: PlexApiTrackResponse | PlexApiPlaylistTrackResponse):
        """Initialize a PlexTrack object.

        Parameter:
        ----------
        data (Dict): The Metadata field from the Plex API response.
        """

        self.data = data

    @property
    def id(self) -> str:
        """
        Unique Identifier within the _same_ library.

        Corresponds to the ratingKey, and does not work to compare across different
        libraries.
        """
        return self.data["ratingKey"]

    @property
    def playlist_item_id(self) -> int | None:
        """
        Unique Identifier within a playlist.

        None for tracks that are not in a playlist, i.e. were created from
        PlexApiTrackResponse rather than PlexApiPlaylistTrackResponse.
        """
        value = self.data.get("playlistItemID", None)
        return (
            int(value) if isinstance(value, (int, str)) and value is not None else None
        )

    def get_local_track(
        self,
        path_rewrite: PathRewrite | None = None,
        file_cache: FileCache | None = None,
    ) -> LocalTrack:
        """Get the file-based version of this Track, for metadata not found in Plex.

        Parameters
        ----------
        - path_rewrite (PathRewrite | None): e.g. if you have local copy of the
        remote files
        - file_cache (FileCache | None): A file cache to use. See LocalTrack

        Raises
        ------
        - FileNotFoundError: If the files are not available on the local filesystem
          or cache (e.g. old tidal tracks or using different mount points)
        - ValueError: If reading file metadata fails.
        """

        if self.path is None:
            raise FileNotFoundError(
                "This PlexTrack has no path, cannot read metadata from file."
            )

        path = self.path
        if path_rewrite is not None:
            path = path_rewrite.apply(path)

        local_track = LocalTrack(path, cache=file_cache)
        return local_track

    # --------------------------------- Contracts -------------------------------- #

    @property
    def ids(self) -> frozenset[TrackID]:
        idents: set[TrackID] = {PlexTrackID(self.id)}
        try:
            p_str = self.data.get("Media", [])[0].get("Part", [])[0].get("file")
            if p_str is not None:
                idents.add(FilePath(PurePath(p_str)))
        except IndexError:
            log.debug(
                "Could not get path from plex metadata, might be an old tidal track."
            )
        return frozenset(idents)

    @property
    def info(self) -> TrackInfo:
        info = TrackInfo()

        title = self.data.get("title")
        if title is not None:
            info["title"] = title

        # In plex api speak, grandparentTitle seems to correspond to the AlbumArtist,
        # which usuall is the same as the artist.
        # If they differ, the originalTitle field is set, and contains the
        # Track Artist, and grandparentTitle contains the Album Artist.
        # TODO: how are multiple artists handled?
        artist = self.data.get("originalTitle")
        if artist is None:
            artist = self.data.get("grandparentTitle")
        if artist is not None:
            info["artists"] = [artist]

        album = self.data.get("parentTitle")
        if album is not None:
            info["albums"] = [album]

        return info
