import logging
from uuid import UUID

import pytest
from plistsync.services.traktor import NMLPlaylist, NMLLibrary
from plistsync.services.traktor.playlist import NMLPlaylistID
from tests.abc.playlist import (
    TestServicePlaylistBase,
)


class TestsTidalPlaylist(TestServicePlaylistBase):
    """Unit tests for the spotify playlist collection."""

    supports_description = False

    @pytest.fixture(autouse=True)
    def setup(self, collection: NMLLibrary):
        self.library = collection

    def create_playlist(self) -> NMLPlaylist:
        return self.library.create_playlist(
            "A name",
        )


class TestTidalPlaylistIntegration:
    """Real tests against a live nml collection."""

    # TODO: Migrate tests from test_collection!
    def test_create(self, collection: NMLLibrary):
        count_before = len(list(collection._playlist_nodes()))
        pl_collection = collection.create_playlist(
            "A name",
        )

        assert len(list(collection._playlist_nodes())) == count_before + 1
        # and it's retrievable via public API
        fetched = collection.get_playlist_or_raise(id=pl_collection.uuid)
        assert fetched.name == "A name"
        assert fetched.uuid == pl_collection.uuid

    def test_create_invalid_subnodes_count(
        self, collection: NMLLibrary, caplog
    ) -> None:
        subnodes_el = collection.tree.xpath(
            ".//PLAYLISTS/NODE[@TYPE='FOLDER'][@NAME='$ROOT']/SUBNODES"
        )[0]
        subnodes_el.set("COUNT", "not-an-int")

        with caplog.at_level(logging.WARNING):
            collection.create_playlist(
                "New PL",
            )

        assert "Invalid SUBNODES COUNT value" in caplog.text
        assert subnodes_el.get("COUNT") == "1"

    def test_create_invalid_name(self, collection: NMLLibrary, caplog):
        with caplog.at_level(logging.WARNING):
            collection.create_playlist(
                "$New PL",
            )

        assert "name changed" in caplog.text

    def test_create_raises_if_root_subnodes_missing(
        self, collection: NMLLibrary
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
            collection.create_playlist("New PL")

    def test_get(self, collection: NMLLibrary):
        existing_uuid = "6868ecd66b354d37a33b965dae7a82e7"

        pl = collection.get_playlist(id=NMLPlaylistID.parse(existing_uuid))
        assert pl is not None

        with pytest.raises(ValueError, match="Could not find playlist"):
            pl = collection.get_playlist_or_raise(id="nope")

    def test_remote_delete(
        self,
        collection: NMLLibrary,
    ):
        pl_collection = collection.create_playlist("New PL")

        # Remove should work as upserted before
        pl_collection.delete()

        assert collection.get_playlist(id=pl_collection.uuid) is None


class TestNMLPlaylistID:
    @pytest.mark.parametrize(
        "input_value, expected_id",
        [
            # UUID object (direct support)
            (
                UUID("550e8400-e29b-41d4-a716-446655440000"),
                "550e8400-e29b-41d4-a716-446655440000",
            ),
            # UUID string (canonical form)
            (
                "550e8400-e29b-41d4-a716-446655440000",
                "550e8400-e29b-41d4-a716-446655440000",
            ),
            # Traktor URI formats
            (
                "traktor:playlist:550e8400-e29b-41d4-a716-446655440000",
                "550e8400-e29b-41d4-a716-446655440000",
            ),
            (
                "nml:playlist:550e8400-e29b-41d4-a716-446655440000",
                "550e8400-e29b-41d4-a716-446655440000",
            ),
            # XML / export formats
            (
                '<playlist uuid="550e8400-e29b-41d4-a716-446655440000">',
                "550e8400-e29b-41d4-a716-446655440000",
            ),
            (
                "<Playlist uuid='550e8400-e29b-41d4-a716-446655440000'>",
                "550e8400-e29b-41d4-a716-446655440000",
            ),
        ],
    )
    def test_valid_inputs(self, input_value, expected_id):
        """Test parsing of valid Traktor/NML UUID inputs."""
        result = NMLPlaylistID.parse(input_value)

        assert isinstance(result, NMLPlaylistID)
        assert str(result.id) == expected_id

    @pytest.mark.parametrize(
        "invalid_input",
        [
            # Wrong services
            "spotify:playlist:550e8400-e29b-41d4-a716-446655440000",
            "tidal:playlist:12345678",
            # Invalid UUIDs
            "550e8400-e29b-41d4-a716-zzzzzzzzzzzz",
            "550e8400-e29b-41d4-a716-44665544000",  # too short
            "550e8400-e29b-41d4-a716-446655440000-extra",
            # Missing values
            "traktor:playlist:",
            "nml:playlist:",
            "<playlist uuid=''>",
            # Garbage
            "not a uuid",
            "",
            "12345",
            "playlist://invalid",
        ],
    )
    def test_invalid_inputs(self, invalid_input):
        """Test invalid inputs raise ValueError."""
        with pytest.raises(ValueError):
            NMLPlaylistID.parse(invalid_input)
