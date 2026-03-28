import pytest

from plistsync.services.beets.database import BeetsDatabase
from plistsync.services.beets import BeetsTrack
from sqlalchemy import select

from tests.abc.tracks import TestTrack
from tests.services.beets._common import item


class TestBeetsTrack(TestTrack):
    track_class = BeetsTrack
    test_config = {
        "has_path": True,
    }

    db: BeetsDatabase

    @pytest.fixture(autouse=True)
    def _request_beets_db(self, beets_lib):
        self.__beets_lib = beets_lib
        self.__beets_lib.add(item(path="/path/to/song.mp3"))
        self.db = BeetsDatabase(self.__beets_lib.path)

    def create_track(self, *args, **kwargs) -> BeetsTrack:
        # Add item
        table = self.db.get_table("items")
        stmt = select(table)

        tracks = []
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
                tracks.append(BeetsTrack(row._asdict()))

        return tracks[0]
