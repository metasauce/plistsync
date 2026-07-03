from collections.abc import Iterable
from pathlib import Path, PurePath
from typing import Any

from sqlalchemy import Row, String, cast, select

from plistsync.core import TrackID
from plistsync.core.collection import Collection, IDLookup, TrackStream
from plistsync.core.ids import ISRC, FilePath

from .database import BeetsDatabase
from .track import BeetsTrack, BeetsTrackID


class BeetsCollection(Collection, TrackStream, IDLookup):
    """A beets library collection."""

    db: BeetsDatabase

    def __init__(self, db_path: Path | str | BeetsDatabase):
        if isinstance(db_path, BeetsDatabase):
            self.db = db_path
        else:
            self.db = BeetsDatabase(db_path)

    def get_by_isrc(self, isrc: str) -> list[BeetsTrack]:
        """Get a list of tracks that match an ISRC."""
        table = self.db.get_table("items")

        stmt = select(table).filter(table.columns.isrc == isrc)
        with self.db.session() as session:
            rows: Iterable[Any] = session.execute(stmt)
            cols = table.columns.keys()
            rows = [dict(zip(cols, row)) for row in rows]

        return BeetsTrack.tracks_from_db_rows(rows)

    def get_by_path(self, path: str | PurePath) -> list[BeetsTrack]:
        """Get a track by its file path."""
        table = self.db.get_table("items")

        stmt = select(table).filter(
            cast(table.columns.path, String).like(f"%{str(path)}%")
        )
        with self.db.session() as session:
            rows: Iterable[Any] = session.execute(stmt)
            cols = table.columns.keys()
            rows = [dict(zip(cols, row)) for row in rows]

        return BeetsTrack.tracks_from_db_rows(rows)

    def get_by_id(self, beets_id: int) -> BeetsTrack | None:
        table = self.db.get_table("items")

        stmt = select(table).filter(table.columns.id == beets_id)
        with self.db.session() as session:
            row: Row[Any] | None = session.execute(stmt).one_or_none()
            if row is None:
                return None
            cols = table.columns.keys()
        return BeetsTrack(dict(zip(cols, row)))

    # --------------------------- IDLookup protocol ------------------------------ #

    def find_by_ids(self, ids: Iterable[TrackID]) -> BeetsTrack | None:
        """Find a track by its identifiers.

        Prioritizes BeetsTrackID, then FilePath, then ISRC.
        """
        for tid in ids:
            if isinstance(tid, BeetsTrackID):
                return self.get_by_id(tid.id)

        for tid in ids:
            if isinstance(tid, FilePath):
                tracks = self.get_by_path(tid.path)
                if tracks:
                    return tracks[0]

        for tid in ids:
            if isinstance(tid, ISRC):
                tracks = self.get_by_isrc(str(tid))
                if tracks:
                    return tracks[0]

        return None

    @property
    def tracks(self) -> Iterable[BeetsTrack]:
        table = self.db.get_table("items")

        stmt = select(table)
        with self.db.session() as session:
            rows = session.execute(
                stmt,
                execution_options={
                    "stream_results": True,
                    "yield_per": 50,
                    "return_dict": True,
                },
            )
            for row in rows:
                yield BeetsTrack(row._asdict())
