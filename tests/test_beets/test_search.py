from pathlib import Path
from beets.library import Library

from plistsync.services.beets import BeetsDatabase, BeetsCollection

from ._common import item


def test_db_create(beets_lib):
    db = BeetsDatabase(beets_lib.path)


def test_isrc(beets_lib_empty: Library):
    beets_lib = beets_lib_empty
    # Add some items to the library
    isrc = "GBLHX1407006"
    beets_lib.add(
        item(
            path="/path/to/strange.mp3",
            isrc=isrc,
        )
    )
    beets_lib.add(item(path="/path/to/strange.flac", isrc="NotTheSame"))
    assert len(beets_lib.items()) == 2

    beets_col = BeetsCollection(beets_lib.path)

    # Test the get_by_isrc function
    res = beets_col.get_by_isrc(isrc)
    assert len(res) == 1

    assert res[0].path == Path("/path/to/strange.mp3")
    assert res[0].isrc == isrc


def test_path(beets_lib_empty):
    beets_lib = beets_lib_empty
    # Add some items to the library
    path_one = Path("/path/one/one.flac")
    path_two = Path("/path/two/two.mp3")
    beets_lib.add(item(path=str(path_one)))
    beets_lib.add(item(path=str(path_two)))

    print(beets_lib.items()[0]["path"])
    assert len(beets_lib.items()) == 2

    beets_col = BeetsCollection(beets_lib.path)

    # Test the get_by_path function
    res = beets_col.get_by_path("/path/one/one.flac")
    assert len(res) == 1
    assert res[0].path == path_one

    # Test get by partial path
    res = beets_col.get_by_path("one")
    assert len(res) == 1
    assert res[0].path == path_one

    # .mp3
    res = beets_col.get_by_path(".mp3")
    assert len(res) == 1
    assert res[0].path == path_two

    # path
    res = beets_col.get_by_path("path")
    assert len(res) == 2
    assert res[0].path == path_one
    assert res[1].path == path_two

    # With Path objects
    res = beets_col.get_by_path(path_one)
    assert len(res) == 1
    assert res[0].path == path_one
