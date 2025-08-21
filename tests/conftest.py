from typing import Any, List
import pytest
import os


@pytest.fixture(scope="session", autouse=True)
def plist_config(tmpdir_factory):
    # Create a temporary directory for our config
    tmp_dir = tmpdir_factory.mktemp("plistsync")

    config_file = tmp_dir / "config.yml"
    config_file.write_text(
        f"""
        beets:
            enabled: true
            database: {tmp_dir}/beets.db
        plex:
            enabled: true
            server_url: http://localhost:32400
            auth_token: {os.environ.get("PLEX_AUTH_TOKEN", None)}
        """,
        encoding="utf-8",
    )
    os.environ["PSYNC_CONFIG_DIR"] = config_file.dirname
    return config_file, tmp_dir


import shutil
from pathlib import Path

from mutagen._file import File


@pytest.fixture
def audio_files(plist_config: tuple[Path, Path]):
    # Copy from tests/data/audio to the temporary directory
    # such that we can transform the files without changing the originals
    source = Path(__file__).parent / "data" / "audio"
    dest = Path(plist_config[1]) / "audio"
    Path(dest).mkdir(exist_ok=True)

    shutil.copytree(source, dest, dirs_exist_ok=True)

    yield dest

    # Clean up the copied files
    shutil.rmtree(dest)


@pytest.fixture
def audio_files_nested(plist_config: tuple[Path, Path]):
    # Copy from tests/data/audio to the temporary directory
    # such that we can transform the files without changing the originals
    source = Path(__file__).parent / "data" / "audio"
    dest = Path(plist_config[1]) / "audio"
    Path(dest).mkdir(exist_ok=True)

    shutil.copytree(source, dest, dirs_exist_ok=True)
    shutil.copytree(source, dest / "nested", dirs_exist_ok=True)

    yield dest

    # Clean up the copied files
    shutil.rmtree(dest)


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
    assert os.path.exists(temp_dir / "beets.db")
    assert "PSYNC_CONFIG_DIR" in os.environ
    assert "BEETSDIR" in os.environ
    assert len(lib.items()) == 0

    # Yield the library for other functions to use
    yield lib
    lib._close()

    # Remove the beets database
    os.remove(temp_dir / "beets.db")


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
    yield beets_lib


def set_tags(file_dir: Path | List[Path], tags: dict[str, Any]):
    # Set the tags of the audio files

    if isinstance(file_dir, Path):
        file_dir = list(file_dir.iterdir())

    for file in file_dir:
        audio = File(file, easy=True)
        for key, value in tags.items():
            audio[key] = value  # type: ignore
        audio.save()  # type: ignore

    # Print the tags for debugging
    for file in file_dir:
        audio = File(file, easy=True)
