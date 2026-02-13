# see also
# https://www.plexopedia.com/plex-media-server/api/library/music-albums-tracks/

from __future__ import annotations

from pathlib import Path

from plistsync.core import GlobalTrackIDs, PathRewrite, Track
from plistsync.core.track import LocalTrackIDs, TrackInfo
from plistsync.logger import log
from plistsync.services.plex.api_types import PlexApiTrackResponse

from ..local.track import FileCache, LocalTrack


class PlexTrack(Track):
    """
    Track on a plex media server.

    Ids are specific to one secdion (library) of one server instance.
    (No global lookups)

    For the Plex Service, we currently do not distinguish between
    Tracks and PlaylistTracks.
    """

    # TODO: Update plan: remove LocalTrack inheritance, and use
    # LocalTrack(PathRewrite(my_plex_track.path, ...)) instead.
    # maybe we have `.get_offline_info(path_rewrite)` property that does this for us.

    data: PlexApiTrackResponse

    def __init__(self, data: PlexApiTrackResponse):
        """Initialize a PlexTrack object.

        Parameter:
        ----------
        data (Dict): The Metadata field from the Plex API response.
        """

        self.data = data

    @property
    def plex_id(self) -> str:
        """
        Unique Identifier within the _same_ library.

        Corresponds to the ratingKey, and does not work to compare across different
        libraries.
        """
        return self.data["ratingKey"]

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
    def global_ids(self) -> GlobalTrackIDs:
        return GlobalTrackIDs()

    @property
    def local_ids(self) -> LocalTrackIDs:
        lids = LocalTrackIDs()

        # file path
        try:
            p_str = self.data.get("Media", [])[0].get("Part", [])[0].get("file")
            if p_str is None:
                raise IndexError("File attribute is None")
            lids["file_path"] = Path(p_str)
        except IndexError:
            log.debug(
                # Plex used to support remote tracks from Tidal.
                "Could not get path from plex metadata, might be an old tidal track."
            )

        # plex_id
        lids["plex_id"] = self.plex_id

        return lids

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
