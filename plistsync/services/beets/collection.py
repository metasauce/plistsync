from pathlib import Path
from typing import Any, Generator, Iterable, List

from sqlalchemy import String, cast, select

from ...core import Collection, GlobalTrackIDs
from ...logger import log
from .database import BeetsDatabase
from .track import BeetsTrack


class BeetsCollection(Collection):
    """A beets library collection."""

    db: BeetsDatabase

    def __init__(self, db_path: Path | str | BeetsDatabase):
        if isinstance(db_path, BeetsDatabase):
            self.db = db_path
        else:
            self.db = BeetsDatabase(db_path)

    def find_by_identifiers(self, identifiers: GlobalTrackIDs) -> BeetsTrack | None:
        isrc = identifiers.get("isrc")
        if isrc is not None:
            tracks = self.get_by_isrc(isrc)

            match len(tracks):
                case 0:
                    pass
                case 1:
                    return tracks[0]
                case _:
                    log.warning(
                        f"Multiple tracks found for ISRC {isrc}. Returning the first one."
                    )
                    return tracks[0]

        return None

    def get_by_isrc(self, isrc: str) -> List[BeetsTrack]:
        """Get a list of tracks that match an ISRC."""
        table = self.db.get_table("items")

        stmt = select(table).filter(table.columns.isrc == isrc)
        with self.db.session() as session:
            rows: Iterable[Any] = session.execute(stmt)
            cols = table.columns.keys()
            rows = [dict(zip(cols, row)) for row in rows]

        return BeetsTrack.tracks_from_db_rows(rows)

    def get_by_path(self, path: str | Path) -> List[BeetsTrack]:
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

    def __iter__(self) -> Generator[BeetsTrack, None, None]:
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
