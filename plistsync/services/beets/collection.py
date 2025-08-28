from pathlib import Path, PurePath
from typing import Any, Iterable, Iterator, List

from sqlalchemy import Row, String, cast, select

from plistsync.core.collection import Collection, GlobalLookup, LocalLookup, TrackStream
from plistsync.core.track import GlobalTrackIDs, LocalTrackIDs

from ...logger import log
from .database import BeetsDatabase
from .track import BeetsTrack


class BeetsCollection(Collection, TrackStream, GlobalLookup, LocalLookup):
    """A beets library collection."""

    db: BeetsDatabase

    def __init__(self, db_path: Path | str | BeetsDatabase):
        if isinstance(db_path, BeetsDatabase):
            self.db = db_path
        else:
            self.db = BeetsDatabase(db_path)

    def get_by_isrc(self, isrc: str) -> List[BeetsTrack]:
        """Get a list of tracks that match an ISRC."""
        table = self.db.get_table("items")

        stmt = select(table).filter(table.columns.isrc == isrc)
        with self.db.session() as session:
            rows: Iterable[Any] = session.execute(stmt)
            cols = table.columns.keys()
            rows = [dict(zip(cols, row)) for row in rows]

        return BeetsTrack.tracks_from_db_rows(rows)

    def get_by_path(self, path: str | PurePath) -> List[BeetsTrack]:
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

    # ------------------------------- Protocols ------------------------------ #

    def find_by_global_ids(self, global_ids: GlobalTrackIDs) -> BeetsTrack | None:
        isrc = global_ids.get("isrc")
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

    def find_by_local_ids(self, local_ids: LocalTrackIDs) -> BeetsTrack | None:
        tracks: list[BeetsTrack] = []
        if file_path := local_ids.get("file_path"):
            tracks.extend(self.get_by_path(file_path))

        if beets_id := local_ids.get("beets_id"):
            track = self.get_by_id(beets_id)
            if track:
                tracks.append(track)

        if len(tracks) == 0:
            return None
        elif len(tracks) == 1:
            return tracks[0]
        else:
            log.warning(
                f"Multiple tracks found for local IDs {local_ids}. Returning the first one."
            )
            return tracks[0]

    def __iter__(self) -> Iterator[BeetsTrack]:
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
