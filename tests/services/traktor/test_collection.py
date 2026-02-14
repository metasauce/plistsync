import logging
from pathlib import Path
import sys
import pytest
from plistsync.services.traktor import NMLCollection
from plistsync.services.traktor.collection import NMLPlaylistCollection, TraktorPath
from plistsync.services.traktor.track import NMLPlaylistTrack
from tests.abc import CollectionTestBase, LibraryCollectionTestBase

from lxml.etree import _Element


class TestNMLCollection(LibraryCollectionTestBase):
    """Test the NMLCollection class."""

    collection_class = NMLCollection
    collection: NMLCollection

    length = 265  # Number of tracks in the test NML file

    @pytest.fixture(autouse=True)
    def setup(self, collection, sample_track):
        self.collection = collection
        self.track = sample_track

    def create_collection(self):
        yield self.collection

    def create_sample_track(self):
        return self.track

    @property
    def known_playlists(self):
        return [
            ("name", "Silvester Full Playthrough"),  # By name
            ("uuid", "6868ecd66b354d37a33b965dae7a82e7"),  # By UUID
        ]

    @property
    def unknown_playlists(self):
        return [
            ("name", "unknown playlist", True),
            ("uuid", "asdasdas", True),
        ]

    def test_get_playlist_invalid_args(self, collection):
        with pytest.raises(ValueError):
            collection.get_playlist(name="Foo", uuid="bar")

    def test_len(self):
        """Test the length of the collection."""
        assert len(self.collection) == self.length

        # Remove the COLLECTION node to force 0
        node: _Element = self.collection.tree.find("COLLECTION")  # type: ignore
        parent: _Element = node.getparent()  # type: ignore
        parent.remove(node)
        assert len(self.collection) == 0

    def test_find_by_path(self):
        """Test finding a track by its file path."""
        # Test with a valid path in collection
        tp_exists = TraktorPath.from_path(
            "D:/SYNC/library/Amoss, Fre4knc/Watermark Volume 2/04 Dragger [1028kbps].flac"
        )
        # Try with Volume specified
        track = self.collection.find_by_traktor_path(tp_exists)
        assert track is not None
        assert track.title == "Dragger"

        # Test with an invalid path
        tp_nonexistent = TraktorPath.from_path("D:/:nonexistent.mp3")
        track = self.collection.find_by_traktor_path(tp_nonexistent)
        assert track is None

    def test_write_persists(self, collection: NMLCollection) -> None:
        """Calling write should persist the collection"""
        new_name = "Updated name"
        p = collection.get_playlist(uuid="6868ecd66b354d37a33b965dae7a82e7")
        p.name = new_name
        collection.write()

        # After reload should be persisteted!
        reloaded = NMLCollection(collection.path)
        p2 = reloaded.get_playlist(uuid="6868ecd66b354d37a33b965dae7a82e7")
        assert p2.name == new_name


class TestNMLPlaylistUpsert:
    def test_upsert_new_playlist(self, collection: NMLCollection) -> None:
        """Allow to insert new playlist collection"""
        count_before = len(list(collection._playlist_nodes()))
        pl_collection = NMLPlaylistCollection(collection, "New PL")
        collection.upsert_playlist(pl_collection)

        assert len(list(collection._playlist_nodes())) == count_before + 1
        # and it's retrievable via public API
        fetched = collection.get_playlist(uuid=pl_collection.uuid)
        assert fetched.name == "New PL"
        assert fetched.uuid == pl_collection.uuid

    def test_upsert_playlist_invalid_subnodes_count(
        self, collection: NMLCollection, caplog
    ) -> None:
        subnodes_el = collection.tree.xpath(
            ".//PLAYLISTS/NODE[@TYPE='FOLDER'][@NAME='$ROOT']/SUBNODES"
        )[0]
        subnodes_el.set("COUNT", "not-an-int")

        pl_collection = NMLPlaylistCollection(collection, "New PL")
        with caplog.at_level(logging.WARNING):
            collection.upsert_playlist(pl_collection)

        assert "Invalid SUBNODES COUNT value" in caplog.text
        assert subnodes_el.get("COUNT") == "1"

    def test_upsert_playlist_raises_if_root_subnodes_missing(
        self, collection: NMLCollection
    ) -> None:
        # sanity: the fixture file should normally have $ROOT/SUBNODES
        subnodes = collection.tree.xpath(
            ".//PLAYLISTS/NODE[@TYPE='FOLDER'][@NAME='$ROOT']/SUBNODES"
        )
        assert len(subnodes) == 1
        subnodes_el = subnodes[0]

        parent = subnodes_el.getparent()
        assert parent is not None

        # remove SUBNODES so xpath in upsert_playlist finds nothing
        parent.remove(subnodes_el)

        new_pl = NMLPlaylistCollection(collection, "New PL")
        with pytest.raises(
            ValueError, match=r"Could not find SUBNODES in \$ROOT folder"
        ):
            collection.upsert_playlist(new_pl)

    def test_upsert_playlist_replaces_existing_by_uuid_and_removes_old_node(
        self, collection: NMLCollection
    ) -> None:
        existing_uuid = "6868ecd66b354d37a33b965dae7a82e7"

        # Grab the actual node currently in the tree
        old_node = collection._get_playlist_root_node_by_uuid(existing_uuid)
        old_parent = old_node.getparent()
        assert old_parent is not None
        old_index = old_parent.index(old_node)

        # Create a *different* playlist element, but reuse the same UUID
        replacement = NMLPlaylistCollection(collection, "Replaced Name")
        replacement.uuid = existing_uuid
        assert (
            replacement.root_node is not old_node
        )  # ensures parent.remove path is taken

        collection.upsert_playlist(replacement)

        # old node must be detached now (proves it was removed from its parent)
        assert old_node.getparent() is None

        # exactly one playlist with that uuid exists
        matches = collection.tree.xpath(
            f".//NODE[@TYPE='PLAYLIST']/*[@UUID='{existing_uuid}']/.."
        )
        assert len(matches) == 1
        new_node = matches[0]

        # inserted in the same parent at the same index (in-place replacement)
        assert new_node.getparent() is old_parent
        assert old_parent.index(new_node) == old_index

        # and public API returns the replaced playlist data
        fetched = collection.get_playlist(uuid=existing_uuid)
        assert fetched.name == "Replaced Name"
        assert fetched.uuid == existing_uuid

    def test_upsert_playlist_raises_if_existing_matching_node_has_no_parent(
        self,
        collection: NMLCollection,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # orphan node: getparent() is None
        orphan_existing = _Element("NODE", {"TYPE": "PLAYLIST"})
        assert orphan_existing.getparent() is None

        def _fake_get_playlist_root_node_by_uuid(_: str):
            return orphan_existing

        # Force the "replace" branch and specifically the parent None check
        monkeypatch.setattr(
            collection,
            "_get_playlist_root_node_by_uuid",
            _fake_get_playlist_root_node_by_uuid,
        )

        pl = NMLPlaylistCollection(collection, "New PL")
        with pytest.raises(
            ValueError, match=r"Existing playlist node has no parent; cannot replace"
        ):
            collection.upsert_playlist(pl)


class TestNMLPlaylistCollection(CollectionTestBase):
    """Test the NMLPlaylistCollection class."""

    collection_class = NMLPlaylistCollection

    @pytest.fixture(autouse=True)
    def setup(self, collection: NMLCollection, sample_track):
        self.collection = collection
        self.track = sample_track

    def create_collection(self):
        yield self.collection

    def create_sample_track(self):
        return self.track

    # The file only has one playlist
    name = "Silvester Full Playthrough"
    uuid = "6868ecd66b354d37a33b965dae7a82e7"

    def test_set_uuid(self):
        """Test setting the UUID of a playlist."""
        p1 = self.collection.get_playlist(name=self.name)
        assert p1 is not None

        p1.uuid = "new-uuid"
        assert p1.uuid == "new-uuid"

        # Reset to original UUID
        p1.uuid = self.uuid
        assert p1.uuid == self.uuid

    def test_set_name(self):
        """Test setting the name of a playlist."""
        p1 = self.collection.get_playlist(name=self.name)
        assert p1 is not None

        p1.name = "New Playlist Name"
        assert p1.name == "New Playlist Name"

        # Reset to original name
        p1.name = self.name
        assert p1.name == self.name

    @pytest.mark.parametrize(
        "track_path",
        [Path("/Volumes/Macintosh HD/foo/bar.mp3")],
    )
    def test_insert_track(self, track_path):
        """Test adding a track to a playlist."""
        p1 = self.collection.get_playlist(name=self.name)
        assert p1 is not None

        l_before = len(p1)
        with p1.edit():
            p1.tracks.append(NMLPlaylistTrack.from_path(track_path))
        assert len(p1) == l_before + 1

    @pytest.mark.skipif(
        sys.platform == "linux",
        reason="""
        we do path prefix checks, which require a macOS or Windows style
        absolute path - which is not possible with real files on linux.
        """,
    )
    def test_insert_track_real_file(self, audio_files: Path):
        p1 = self.collection.get_playlist(name=self.name)
        assert p1 is not None

        l_before = len(p1)
        with p1.edit():
            for audio_file in audio_files.iterdir():
                p1.tracks.append(NMLPlaylistTrack.from_path(audio_file))
                break
        assert len(p1) == l_before + 1

    def test_find_by_path(self, collection: NMLCollection, audio_files: Path):
        """Test finding a track by its file path in a playlist."""
        p1 = collection.get_playlist(name=self.name)
        assert p1 is not None

        # Test with a valid traktor path
        example_path = "D:/:SYNC/:library/:Amoss, Fre4knc/:Watermark Volume 2/:04 Dragger [1028kbps].flac"  # noqa: E501
        track = p1.find_by_traktor_path(TraktorPath(example_path))
        assert track is not None

        # Test with a valid path
        example_path = Path(
            "D:/SYNC/library/Amoss, Fre4knc/Watermark Volume 2/04 Dragger [1028kbps].flac"
        )
        track = p1.find_by_local_ids({"file_path": example_path})
        assert track is not None

        # Test valid but not in collection
        track = p1.find_by_traktor_path(TraktorPath("D:/:Not/:existing.flac"))
        assert track is None
