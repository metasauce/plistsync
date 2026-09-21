"""Shared fixtures for the playlist command tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from plistsync.core.ids import ISRC
from plistsync.services import Service
from tests.core.mock_collections import MockLibrary
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
