import json
import platform
import subprocess
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
        logging:
            level: DEBUG

        services:
            beets:
                enabled: true
                database: {tmp_dir}/beets.db
            plex:
                enabled: true
                default_server_url: http://localhost:32400
            spotify:
                enabled: true
                client_id: 3b408bca2c3344dfa1cda1c7fa9adde4
                redirect_port: 5001
        """,
        encoding="utf-8",
    )
    os.environ["PSYNC_CONFIG_DIR"] = config_file.dirname

    # Also write spotify token
    spotify_token_file = tmp_dir / "spotify_token.json"
    spotify_token = {
        "access_token": "BQDeDfFpiUzzmwVoXH8c7UurBfUPagZwb0GXu1HPHCVbOQRQtmaUUTW3_4JCIKYv-NNaRjG7zbjH1D4ahqWhtwgfZo2-1-7e2Yw0JfYoioRFBDBmyhFI-S_ibB1WlfNOpX7c0lAe8wUWqcVpcu2lHki3_9CbY6OBfujNizPXgMIklhLjSsfhTVXDqqslC1cGbgHQpVRRIk0Z0RKPCHLBu7fvcJ6CGfTaySinkkZyP0QbF10HaSdYSVkSRPk0k4HGqTGpeJNJaI0l_rWXgjBM9XLDURZwMSyK",
        "scope": "playlist-read-private playlist-read-collaborative playlist-modify-private playlist-modify-public",
        "refresh_token": "AQBpaDBrDZc0K0fOcqv7A3Y5S5DrIabG6F5UYgeHBIDmGOLxWybRCNaE2lS3P76zlWVgZzrmpEbuZtSSQDjGV5GZOAI90GvLSgWZ9ram92lMRUyJXR9HI2XyQjOkUIsexLPxHA",
        "token_type": "Bearer",
        "expires_at": "2025-09-18T20:40:06+00:00",
    }
    spotify_token_file.write_text(json.dumps(spotify_token, indent=4), encoding="utf-8")

    # Also write plex token
    plex_token_file = tmp_dir / "plex_token.json"
    plex_token = {
        "X-Plex-Token": os.environ.get("PLEX_AUTH_TOKEN", "FAKE_TOKEN_FOR_TESTS_ONLY"),
    }
    plex_token_file.write_text(json.dumps(plex_token, indent=4), encoding="utf-8")

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
    dest = fix_path_prefix_for_traktor(dest)
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
    dest = fix_path_prefix_for_traktor(dest)
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


def fix_path_prefix_for_traktor(dest: Path):
    """Make sure this pass is compatible with absolute path required
    by Traktor, i.e.

    /Volumes/Macintosh HD/... on macOS
    C: ... on Windows

    ... linux?
    """

    if platform.system() == "Darwin":
        volume_name = _find_macos_volume_name()
        dest = Path(f"/Volumes/{volume_name}") / dest.relative_to(dest.anchor)
    elif platform.system() == "Windows":
        # should be just fine
        dest = Path(dest.drive) / dest.relative_to(dest.anchor)
    else:
        # on linux, we might want to do a workaround via symlink
        # as /Volumes/foo/ ...
        dest = dest.resolve()

    return dest


def _find_macos_volume_name() -> str:
    cmd = [
        "diskutil",
        "info",
        "/",
    ]
    output = subprocess.check_output(cmd, text=True)
    for line in output.splitlines():
        if "Volume Name:" in line:
            return line.split(":", 1)[1].strip()

    return "Macintosh HD"
