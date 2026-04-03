import pytest
from pathlib import Path
from tinytag import TinyTag

from plistsync.services.local.collection import LocalCollection

from tests.conftest import set_tags


def test_create(audio_files: Path):
    collection = LocalCollection(audio_files)
    assert collection.path == audio_files

    # Test create with invalid path
    with pytest.raises(FileNotFoundError):
        LocalCollection("does/not/exist")


def test_find_by_identifiers(audio_files: Path):
    # Set dummy isrc tags
    isrc = "US-AT1-99-00001"
    set_tags(audio_files, {"isrc": isrc})

    collection = LocalCollection(audio_files)

    # Test finding a track by isrc
    track = collection.find_by_identifiers({"isrc": isrc})
    assert track is not None, "Track should be found"
    assert track.global_ids.get("isrc") == isrc, "Track should have the correct isrc"

    # Test finding with different capitalization
    track = collection.find_by_identifiers({"isrc": isrc.lower()})

    assert track is not None, "Track should be found"
    assert track.global_ids.get("isrc") == isrc, "Track should have the correct isrc"


def test_nested_audio_folder(audio_files_nested: Path):
    collection = LocalCollection(audio_files_nested)

    # Test finding a track by isrc
    count = 0
    for p in audio_files_nested.iterdir():
        if p.is_dir():
            continue

        if TinyTag.is_supported(p):
            count += 1

    assert len(list(collection)) == count * 2, "All tracks should be found twice"
