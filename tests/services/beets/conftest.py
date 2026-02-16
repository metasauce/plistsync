import pytest
import os
from pathlib import Path


@pytest.fixture(autouse=True, scope="session")
def beets_lib(plist_config):
    # Setup beets to use the tempdir
    # for reference, see also
    # https://github.com/beetbox/beets/blob/22163d70a77449d83670e60ad3758474463de31b/beets/test/helper.py#L196
    temp_dir = plist_config[1]
    os.environ["BEETSDIR"] = str(temp_dir / "beets")
    os.environ["HOME"] = str(temp_dir)

    # Initialize a new beets library
    import beets.library

    lib = beets.library.Library(temp_dir / "beets.db")

    # clear_db
    from plistsync.services.beets.database import BeetsDatabase
    from sqlalchemy import text

    db = BeetsDatabase(temp_dir / "beets.db")

    tables = db.get_tables()
    with db.session() as session:
        for table in tables:
            stmt = text(f"DELETE FROM {table.name}")
            session.execute(stmt)

    # Test the library
    assert (temp_dir / "beets.db").exists()
    assert "PSYNC_CONFIG_DIR" in os.environ
    assert "BEETSDIR" in os.environ
    assert len(lib.items()) == 0

    # Yield the library for other functions to use
    yield lib
    lib._close()

    # Remove the beets database
    Path(temp_dir / "beets.db").unlink()


@pytest.fixture
def beets_lib_empty(beets_lib):
    # Clear the beets library
    from plistsync.services.beets.database import BeetsDatabase
    from sqlalchemy import text

    db = BeetsDatabase(beets_lib.path)

    tables = db.get_tables()
    with db.session() as session:
        for table in tables:
            stmt = text(f"DELETE FROM {table.name}")
            session.execute(stmt)

    assert len(beets_lib.items()) == 0
    return beets_lib
