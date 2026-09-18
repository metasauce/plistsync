"""Tests for the per-service playlist CLI command group."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer._click._compat import strip_ansi
from typer.main import get_group

from plistsync.cli.service_commands.playlist import (
    PlaylistArgument,
    _playlist_id_text,
    parse_track_id,
)
from plistsync.core.ids import ISRC
from plistsync.services import Service
from tests.core.mock_collections import MockLibrary
from tests.core.mock_playlist import MockPlaylistID
from tests.core.mock_track import MockTrack

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    import typer
    from typer.testing import CliRunner, Result

    from tests.core.mock_playlist import MockServicePlaylist

    Invoke = Callable[..., Result]


class MockLibraryService(Service):
    """Service exposing the mock library, so the playlist group is mounted."""

    __module__ = "plistsync.services.mock_library_cli"

    def library(self) -> type[MockLibrary]:
        return MockLibrary


class NoLibraryService(Service):
    """Service without library support."""

    __module__ = "plistsync.services.no_library_cli"

    def library(self) -> None:
        return None


@pytest.fixture
def app(service_app: Callable[[Service], typer.Typer]) -> typer.Typer:
    """Command app for the mock library service."""
    return service_app(MockLibraryService())


@pytest.fixture
def create(runner: CliRunner, app: typer.Typer) -> Invoke:
    """Invoke ``playlist create``."""

    def _create(args: list[str] | None = None, user_input: str = "") -> Result:
        return runner.invoke(
            app, ["playlist", "create", *(args or [])], input=user_input
        )

    return _create


@pytest.fixture
def remove(runner: CliRunner, app: typer.Typer) -> Invoke:
    """Invoke ``playlist remove``."""

    def _remove(args: list[str] | None = None, user_input: str = "") -> Result:
        return runner.invoke(
            app, ["playlist", "remove", *(args or [])], input=user_input
        )

    return _remove


@pytest.fixture
def list_playlists(runner: CliRunner, app: typer.Typer) -> Invoke:
    """Invoke ``playlist list``."""

    def _list_playlists() -> Result:
        return runner.invoke(app, ["playlist", "list"])

    return _list_playlists


@pytest.fixture
def playlist(_mock_library: None) -> MockServicePlaylist:
    """A playlist known to the mock library."""
    return MockLibrary().create_playlist("Party Mix", description="Chill")


@pytest.fixture(autouse=True)
def _mock_library() -> Iterator[None]:
    """Give the mock library one findable track and reset its recordings."""
    MockLibrary.tracks = [
        MockTrack(title="Found by id", artists=["Artist"], ids={ISRC("USRC17607839")})
    ]
    MockLibrary.created.clear()
    yield
    MockLibrary.tracks = []
    MockLibrary.created.clear()


class TestCreate:
    """``plistsync <service> playlist create``."""

    def test_mounted_only_with_library(
        self, service_app: Callable[[Service], typer.Typer]
    ) -> None:
        group = get_group(service_app(MockLibraryService()))

        assert set(group.commands) == {"playlist"}
        assert set(group.commands["playlist"].commands) == {
            "create",
            "remove",
            "rm",
            "list",
            "ls",
        }
        assert get_group(service_app(NoLibraryService())).commands == {}

    @pytest.mark.parametrize("option", ["--name", "--description", "--add", "--yes"])
    def test_help_lists_options(self, create: Invoke, option: str) -> None:
        result = create(["--help"])

        assert result.exit_code == 0
        assert option in strip_ansi(result.output)

    @pytest.mark.parametrize(
        ("args", "user_input", "expected"),
        [
            ([], "My Playlist\nMy Description\n\n", ("My Playlist", "My Description")),
            ([], "My Playlist\n\n\n", ("My Playlist", None)),
            (["--name", "N", "--description", "D"], "\n", ("N", "D")),
        ],
    )
    def test_prompts_for_metadata(
        self,
        create: Invoke,
        args: list[str],
        user_input: str,
        expected: tuple[str, str | None],
    ) -> None:
        result = create(args, user_input)

        assert result.exit_code == 0, result.output
        created = MockLibrary.created[0]
        assert (created.name, created.description) == expected

    def test_confirmation_lists_metadata_and_tracks(self, create: Invoke) -> None:
        result = create(
            ["--name", "N", "--description", "D", "--add", "isrc:USRC17607839"], "\n"
        )
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert all(
            text in output
            for text in (
                "Name",
                "'N'",
                "Description",
                "Tracks",
                "Artist",
                "Found by id",
                "Continue?",
            )
        )
        assert [track.title for track in MockLibrary.created[0].tracks] == [
            "Found by id"
        ]

    @pytest.mark.parametrize(
        ("value", "expected_titles"),
        [
            ("isrc:USRC17607839", ["Found by id"]),
            ("not-a-track", []),
        ],
    )
    def test_add_option(
        self, create: Invoke, value: str, expected_titles: list[str]
    ) -> None:
        result = create(["--name", "N", "--description", "D", "-y", "--add", value])

        assert result.exit_code == 0, result.output
        assert [t.title for t in MockLibrary.created[0].tracks] == expected_titles

    def test_yes_skips_confirmation(self, create: Invoke) -> None:
        result = create(["--name", "N", "--description", "D", "-y"])

        assert result.exit_code == 0, result.output
        assert "Continue?" not in result.output

    def test_declining_confirmation_aborts(self, create: Invoke) -> None:
        result = create([], "N\nD\nn\n")

        assert result.exit_code != 0
        assert "Aborted" in strip_ansi(result.output)
        assert MockLibrary.created == []

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("isrc:USRC17607839", ISRC("USRC17607839")),
            ("not-a-track", None),
        ],
    )
    def test_parse_track_id(self, value: str, expected: ISRC | None) -> None:
        assert parse_track_id(value) == expected


class TestRemove:
    """``plistsync <service> playlist remove``."""

    def test_help_lists_yes(self, remove: Invoke) -> None:
        result = remove(["--help"])

        assert result.exit_code == 0
        assert "--yes" in strip_ansi(result.output)

    def test_removes_by_name(
        self, remove: Invoke, playlist: MockServicePlaylist
    ) -> None:
        result = remove(["Party Mix", "-y"])

        assert result.exit_code == 0, result.output
        assert "Removed playlist 'Party Mix'" in strip_ansi(result.output)
        assert ("remote_delete",) in playlist.log

    def test_removes_by_serial(
        self, remove: Invoke, playlist: MockServicePlaylist
    ) -> None:
        result = remove([playlist.id.serial, "-y"])

        assert result.exit_code == 0, result.output
        assert ("remote_delete",) in playlist.log

    def test_confirmation_aborts(
        self, remove: Invoke, playlist: MockServicePlaylist
    ) -> None:
        result = remove(["Party Mix"], "n\n")

        assert result.exit_code != 0
        assert "Aborted" in strip_ansi(result.output)
        assert ("remote_delete",) not in playlist.log

    def test_unknown_playlist_fails(self, remove: Invoke) -> None:
        result = remove(["nope", "-y"])

        assert result.exit_code != 0
        assert "No playlist found" in strip_ansi(result.output)

    def test_autocompletion_lists_names_and_serials(
        self, playlist: MockServicePlaylist
    ) -> None:
        param = PlaylistArgument(MockLibrary)

        def complete(incomplete: str) -> list[str]:
            items = param.shell_complete(None, None, incomplete)  # type: ignore[arg-type]
            return [item.value for item in items]

        assert complete("") == ["Party Mix", playlist.id.serial]
        assert complete("Party") == ["Party Mix"]
        assert complete("test:playlist:") == [playlist.id.serial]
        assert complete("nope") == []


class TestList:
    """``plistsync <service> playlist list``."""

    def test_lists_name_description_and_serial(
        self, list_playlists: Invoke, playlist: MockServicePlaylist
    ) -> None:
        result = list_playlists()
        output = strip_ansi(result.output)

        assert result.exit_code == 0, result.output
        assert "Party Mix" in output
        assert "Chill" in output
        assert playlist.id.serial in output

    def test_empty_library_message(self, list_playlists: Invoke) -> None:
        result = list_playlists()

        assert result.exit_code == 0, result.output
        assert "No playlists found" in strip_ansi(result.output)

    def test_id_links_to_url_when_available(self) -> None:
        playlist_id = MockPlaylistID("abc")
        text = _playlist_id_text(playlist_id)

        assert text.plain == playlist_id.serial
        assert text.style == f"link {playlist_id.url}"
