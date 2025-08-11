# see also
# https://www.plexopedia.com/plex-media-server/api/library/music-albums-tracks/

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, NamedTuple, Self

from plistsync.core import Track, TrackIdentifiers
from plistsync.logger import log
from ..local.track import FileCache, LocalTrack


class PathRewrite(NamedTuple):
    old: str
    new: str


class PlexTrack(LocalTrack, Track):
    data: Dict
    path_rewrite: None | PathRewrite = None

    def __init__(
        self,
        data: Dict,
        cache: FileCache | None = None,
        path_rewrite: None | PathRewrite = None,
    ):
        """Initialize a PlexTrack object.

        Parameter:
        ----------
        data (Dict): The Metadata field from the Plex API response.
        cache (FileCache | None): A file cache to use for this track, to avoid rereading id3 info from disk.
        """

        self.data = data
        self.path_rewrite = path_rewrite

        try:
            path = self.path
            LocalTrack.__init__(self, path, cache)
        except (IndexError, TypeError):
            # Plex used to have tracks without paths because of tidal integration
            # this is not the case anymore, but we keep this here for backwards compatibility
            # TypeError occurs when path is None
            log.debug(f"Could not get path from track: {self.data}")
            Track.__init__(self)
        except FileNotFoundError as e:
            log.warning(f"Could not find file for track: {e}")
            log.warning("Might be due to inconsistent mount points or permissions.")
            Track.__init__(self)

    @property
    def plex_id(self) -> str:
        """
        Unique Identifier within the _same_ library.

        Corresponds to the ratingKey, and does not work to compare across different
        libraries.
        """
        return self.data["ratingKey"]

    @property
    def path(self) -> Path:
        try:
            p_str = self.data.get("Media", [])[0].get("Part", [])[0].get("file")
            if p_str is None:
                raise IndexError("Track has no file path")
            if self.path_rewrite and p_str.startswith(self.path_rewrite.old):
                p_str = p_str.replace(self.path_rewrite.old, self.path_rewrite.new, 1)
        except IndexError:
            log.error(f"Could not get path from track: {self.data}")
            raise
        return Path(p_str)

    # ---------------------------------------------------------------------------- #
    #                                 ABC methods                                  #
    # ---------------------------------------------------------------------------- #

    @property
    def title(self) -> str:
        return self.data["title"]

    @property
    def artists(self) -> List[str]:
        """
        Artist of the track.

        In plex api speak, grandparentTitle seems to correspond to the AlbumArtist,
        which usuall is the same as the artist.
        If they differ, the originalTitle field is set, and contains the
        Track Artist, and grandparentTitle contains the Album Artist.
        """
        artist = self.data.get("originalTitle")
        if artist is None:
            artist = self.data.get("grandparentTitle")
        if artist is None:
            return []
        return [artist]

    @property
    def albums(self) -> List[str]:
        album = self.data.get("parentTitle")
        if album is None:
            return []
        return [album]

    @property
    def identifiers(self) -> TrackIdentifiers:
        if isinstance(self, LocalTrack):
            return super().identifiers
        return TrackIdentifiers()

    def serialize(self) -> dict:
        return {
            "data": self.data,
        }

    @classmethod
    def deserialize(cls, data: dict) -> Self:
        return cls(data["data"])


"""
{
"Metadata": [
{
    "Image": [
    {
        "alt": "We Are Your Crazy Friends (Baramuda Bootleg Mix)",
        "type": "coverPoster",
        "url": "/library/metadata/58473/thumb/1713284425"
    },
    {
        "alt": "We Are Your Crazy Friends (Baramuda Bootleg Mix)",
        "type": "background",
        "url": "/library/metadata/55906/art/1713284398"
    }
    ],
    "Media": [
    {
        "Part": [
        {
            "container": "mp3",
            "duration": 629032,
            "file": "/media/music/clean/Various Artists/Tech And Minimal Collection Volume 20/43 We Are Your Crazy Friends (Baramuda Bootleg Mix) [320kbps].mp3",
            "hasThumbnail": "1",
            "id": 112271,
            "key": "/library/parts/112271/1716780133/file.mp3",
            "size": 26170369
        }
        ],
        "audioChannels": 2,
        "audioCodec": "mp3",
        "bitrate": 320,
        "container": "mp3",
        "duration": 629032,
        "hasVoiceActivity": false,
        "id": 58357
    }
    ],
    "addedAt": 1713284375,
    "art": "/library/metadata/55906/art/1713284398",
    "duration": 629032,
    "grandparentArt": "/library/metadata/55906/art/1713284398",
    "grandparentGuid": "plex://artist/5d07bbfc403c6402904a5ec9",
    "grandparentKey": "/library/metadata/55906",
    "grandparentRatingKey": "55906",
    "grandparentThumb": "/library/metadata/55906/thumb/1713284398",
    "grandparentTitle": "Various Artists", --> Album Artist (this is a compilation)
    "guid": "local://58516",
    "index": 43,
    "key": "/library/metadata/58516",
    "lastViewedAt": 1725619057,
    "librarySectionID": 5,
    "librarySectionKey": "/library/sections/5",
    "librarySectionTitle": "Music",
    "musicAnalysisVersion": "1",
    "originalTitle": "Sharam Vs Justice",  --> Track Artist
    "parentGuid": "local://58473",
    "parentIndex": 1,
    "parentKey": "/library/metadata/58473",
    "parentRatingKey": "58473",
    "parentThumb": "/library/metadata/58473/thumb/1713284425",
    "parentTitle": "Tech And Minimal Collection Volume 20",
    "parentYear": 2011,
    "ratingKey": "58516",
    "summary": "",
    "thumb": "/library/metadata/58473/thumb/1713284425",
    "title": "We Are Your Crazy Friends (Baramuda Bootleg Mix)",
    "type": "track"
}
"""
