import logging

import pytest
from plistsync.services.traktor import NMLPlaylistCollection, NMLLibraryCollection
from tests.abc.playlist import (
    TestServicePlaylistBase,
)


class TestsTidalPlaylist(TestServicePlaylistBase):
    """Unit tests for the spotify playlist collection."""

    supports_description = False

    @pytest.fixture(autouse=True)
    def setup(self, collection: NMLLibraryCollection):
        self.library = collection

    def create_playlist(self) -> NMLPlaylistCollection:
        return NMLPlaylistCollection.create("A name", library=self.library)


class TestTidalPlaylistIntegration:
    """Real tests against a live nml collection."""

    # TODO: Migrate tests from test_collection!
    def test_create(self, collection: NMLLibraryCollection):
        count_before = len(list(collection._playlist_nodes()))
        pl_collection = NMLPlaylistCollection.create("New PL", library=collection)

        assert len(list(collection._playlist_nodes())) == count_before + 1
        # and it's retrievable via public API
        fetched = collection.get_playlist_or_raise(uuid=pl_collection.uuid)
        assert fetched.name == "New PL"
        assert fetched.uuid == pl_collection.uuid

    def test_create_invalid_subnodes_count(
        self, collection: NMLLibraryCollection, caplog
    ) -> None:
        subnodes_el = collection.tree.xpath(
            ".//PLAYLISTS/NODE[@TYPE='FOLDER'][@NAME='$ROOT']/SUBNODES"
        )[0]
        subnodes_el.set("COUNT", "not-an-int")

        with caplog.at_level(logging.WARNING):
            NMLPlaylistCollection.create("New PL", library=collection)

        assert "Invalid SUBNODES COUNT value" in caplog.text
        assert subnodes_el.get("COUNT") == "1"

    def test_create_invalid_name(self, collection: NMLLibraryCollection, caplog):
        with caplog.at_level(logging.WARNING):
            NMLPlaylistCollection.create("$New PL", library=collection)

        assert "name changed" in caplog.text

    def test_create_raises_if_root_subnodes_missing(
        self, collection: NMLLibraryCollection
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

        with pytest.raises(
            ValueError, match=r"Could not find SUBNODES in \$ROOT folder"
        ):
            NMLPlaylistCollection.create("New PL", library=collection)

    def test_get(self, collection: NMLLibraryCollection):
        existing_uuid = "6868ecd66b354d37a33b965dae7a82e7"

        pl = NMLPlaylistCollection.get(
            ids={"traktor_id": existing_uuid}, library=collection
        )
        assert pl is not None

        with pytest.raises(ValueError, match="not found"):
            pl = NMLPlaylistCollection.get(
                ids={"traktor_id": "nope"}, library=collection
            )

        with pytest.raises(ValueError, match="not found"):
            pl = NMLPlaylistCollection.get(ids={}, library=collection)

    def test_remote_delete(
        self,
        collection: NMLLibraryCollection,
    ):
        pl_collection = NMLPlaylistCollection.create("New PL", library=collection)

        # Remove should work as upserted before
        pl_collection.delete()

        assert collection.get_playlist(uuid=pl_collection.uuid) is None
