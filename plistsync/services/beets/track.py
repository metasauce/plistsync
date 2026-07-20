from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, ClassVar, Self

from plistsync.core import Track, TrackID, TrackInfo
from plistsync.core.ids import ISRC, FilePath, Scope


@dataclass(frozen=True)
class BeetsTrackID(TrackID):
    """A Beets track identifier (database row ID)."""

    # Only unique within a single beets database
    scope: ClassVar[Scope] = Scope.LOCAL

    id: int

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse from serial format or raw ID."""
        value = value.strip()
        if value.lower().startswith(cls.prefix()):
            value = value[len(cls.prefix()) + 1 :].strip()
        if not value.isdigit():
            raise ValueError(f"Invalid Beets track id: {value!r}")
        return cls(int(value))

    @property
    def serial(self) -> str:
        """Plistsync's internal representation for trackid on Beets."""
        return f"{self.prefix()}:{self.id}"

    def __str__(self) -> str:
        """Compact display, understood by Beets API."""
        return str(self.id)

    def __int__(self) -> int:
        """Compact display, understood by Beets API."""
        return self.id


class BeetsTrack(Track):
    """A track is a piece of music.

    We might want to add more functionality in the future.
    """

    row: dict[str, Any]

    def __init__(self, row: dict) -> None:
        """By default we expect you to pass a row from the beets database.

        Each track corresponds to one row of the `items` table in the beets sqlite db.

        The `path`, which is a binary in the db, gets cast to a string.

        Look at other classmethods for other ways to create a track.
        """
        self.row = row

        # cast path, if it is a binary (in db)
        if isinstance(self.row["path"], bytes):
            self.row["path"] = self.row["path"].decode("utf-8")

    @classmethod
    def tracks_from_db_rows(cls, rows: list[dict]) -> list[Self]:
        """Construct one or multiple tracks from a row in the beets database.

        One track in beets might have multiple isrcs or identifier associated with it.
        We use an isrc as the main way to compare tracks, and assume one track to
        correspond to a unique isrc.
        This method splits theses `items` rows into multiple tracks, one for each isrc.
        (Same metadata, but different isrcs)
        """
        tracks = []
        for row in rows:
            isrc_str = row.get("isrc")
            if isrc_str is None:
                tracks.append(cls(row))
                continue

            for isrc in isrc_str.split(";"):
                this_row = row.copy()
                this_row["isrc"] = isrc
                tracks.append(cls(this_row))

        return tracks

    # ----------------------------- Info Getters ----------------------------- #

    @property
    def path(self) -> Path:
        return Path(self.row["path"]).resolve()

    @property
    def primary_artist(self) -> str | None:
        """Returns the beets artist field.

        In contrast to most other services, beets keeps artists and artist separate.
        Not necessarily the first item in the list of artists!
        """
        return self.row.get("artist", None)

    # ------------------------------- Contracts ------------------------------ #

    @property
    def ids(self) -> frozenset[TrackID]:
        idents: set[TrackID] = {BeetsTrackID(self.row["id"])}

        # File path
        path = self.path
        if path is not None:
            idents.add(FilePath(PurePath(path)))

        # ISRC (already single-valued due to tracks_from_db_rows)
        isrc = self.row.get("isrc", None)
        if isinstance(isrc, str) and isrc.strip():
            try:
                idents.add(ISRC(isrc.strip()))
            except ValueError:
                pass

        # TODO: beets support multiple identifiers, e.g. discogs, musicbrainz, etc.

        return frozenset(idents)

    @property
    def info(self) -> TrackInfo:
        info = TrackInfo()

        title = self.row.get("title")
        if title is not None:
            info["title"] = title

        artists = self.row.get("artists")
        if artists is not None:
            if isinstance(artists, str):
                artists = [artists]
            info["artists"] = artists

        albums = self.row.get("album")
        if albums is not None:
            info["albums"] = [albums]

        return info

    __slots__ = ("row",)


"""
CREATE TABLE items (
  id INTEGER PRIMARY KEY,
  path BLOB,
  album_id INTEGER,
  title TEXT,
  artist TEXT,
  artists TEXT,
  artists_ids TEXT,
  artist_sort TEXT,
  artists_sort TEXT,
  artist_credit TEXT,
  artists_credit TEXT,
  remixer TEXT,
  album TEXT,
  albumartist TEXT,
  albumartists TEXT,
  albumartist_sort TEXT,
  albumartists_sort TEXT,
  albumartist_credit TEXT,
  albumartists_credit TEXT,
  genre TEXT,
  style TEXT,
  discogs_albumid INTEGER,
  discogs_artistid INTEGER,
  discogs_labelid INTEGER,
  lyricist TEXT,
  composer TEXT,
  composer_sort TEXT,
  work TEXT,
  mb_workid TEXT,
  work_disambig TEXT,
  arranger TEXT,
  grouping TEXT,
  year INTEGER,
  month INTEGER,
  day INTEGER,
  track INTEGER,
  tracktotal INTEGER,
  disc INTEGER,
  disctotal INTEGER,
  lyrics TEXT,
  comments TEXT,
  bpm INTEGER,
  comp INTEGER,
  mb_trackid TEXT,
  mb_albumid TEXT,
  mb_artistid TEXT,
  mb_artistids TEXT,
  mb_albumartistid TEXT,
  mb_albumartistids TEXT,
  mb_releasetrackid TEXT,
  trackdisambig TEXT,
  albumtype TEXT,
  albumtypes TEXT,
  label TEXT,
  barcode TEXT,
  acoustid_fingerprint TEXT,
  acoustid_id TEXT,
  mb_releasegroupid TEXT,
  release_group_title TEXT,
  asin TEXT,
  isrc TEXT,
  catalognum TEXT,
  script TEXT,
  language TEXT,
  country TEXT,
  albumstatus TEXT,
  media TEXT,
  albumdisambig TEXT,
  releasegroupdisambig TEXT,
  disctitle TEXT,
  encoder TEXT,
  rg_track_gain REAL,
  rg_track_peak REAL,
  rg_album_gain REAL,
  rg_album_peak REAL,
  r128_track_gain REAL,
  r128_album_gain REAL,
  original_year INTEGER,
  original_month INTEGER,
  original_day INTEGER,
  initial_key TEXT,
  length REAL,
  bitrate INTEGER,
  bitrate_mode TEXT,
  encoder_info TEXT,
  encoder_settings TEXT,
  format TEXT,
  samplerate INTEGER,
  bitdepth INTEGER,
  channels INTEGER,
  mtime REAL,
  added REAL
)
"""
