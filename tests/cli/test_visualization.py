"""Tests for Rich rendering of domain objects."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
import typer
from rich.console import Console, Group
from rich.prompt import Confirm
from rich.text import Text
from typer._click._compat import strip_ansi

from plistsync.cli.visualization import (
    confirm_or_abort,
    render_playlists,
    render_tracks,
    to_rich,
)
from plistsync.core.diff import list_diff
from plistsync.core.ids import ISRC
from plistsync.core.playlist import PlaylistInfo, Snapshot
from plistsync.core.track import OfflineTrack, TrackInfo
from tests.core.mock_playlist import MockPlaylistID, MockServicePlaylist
from tests.core.mock_track import MockTrackID

if TYPE_CHECKING:
    from rich.table import Table

    from plistsync.core.ids import PlaylistID, TrackID


def render(renderable: object) -> str:
    stream = io.StringIO()
    Console(file=stream, highlight=False).print(renderable)
    return strip_ansi(stream.getvalue())


def track(title: str, *ids: TrackID) -> OfflineTrack:
    return OfflineTrack(TrackInfo(title=title, artists=["Artist"]), ids=ids)


def mock_playlist(description: str | None = "Chill") -> MockServicePlaylist:
    return MockServicePlaylist(
        id=MockPlaylistID("p"),
        info=PlaylistInfo(name="Party", description=description),
        tracks=[],
    )


def test_passthrough() -> None:
    # Callers mix domain objects with str/Text/Table, which must stay untouched.
    assert to_rich("plain") == "plain"


@pytest.mark.parametrize(
    ("identifier", "style"),
    [
        (ISRC("USRC17607839"), ""),
        (MockPlaylistID("abc"), "link https://example.com/playlist/abc"),
        (MockTrackID("abc"), "link https://example.com/track/abc"),
    ],
    ids=["isrc", "playlist", "track"],
)
def test_id_rendering(identifier: TrackID | PlaylistID, style: str) -> None:
    # IDs with a public URL become terminal hyperlinks, the rest stay plain.
    rendered = to_rich(identifier)
    assert isinstance(rendered, Text)
    assert rendered.plain == identifier.serial
    assert rendered.style == style


@pytest.mark.parametrize(
    ("table", "present"),
    [
        (
            render_tracks([track("One"), track("Two")]),
            ("Artist", "Title", "0", "1", "One", "Two"),
        ),
        (
            render_playlists([mock_playlist()], title="Playlists"),
            ("Playlists", "Party", "Chill"),
        ),
    ],
    ids=["tracks", "playlists"],
)
def test_table_rendering(table: Table, present: tuple[str, ...]) -> None:
    # Design: borderless tables, dim headers, left-aligned title in accent color.
    assert table.box is None and table.header_style == "dim"
    assert table.title_justify == "left" and table.title_style == "bold cyan"
    output = render(table)
    assert all(text in output for text in present)


@pytest.mark.parametrize(
    ("snapshot", "present", "absent"),
    [
        (
            Snapshot(name="Mix", description="Dance", tracks=[track("One")]),
            ("Mix", "Dance", "Tracks", "One"),
            (),
        ),
        (
            Snapshot(name="Empty", description=None, tracks=[]),
            ("Tracks",),
            ("Artist",),
        ),
    ],
    ids=["tracks", "empty"],
)
def test_snapshot(
    snapshot: Snapshot, present: tuple[str, ...], absent: tuple[str, ...]
) -> None:
    # Metadata always renders; the track table is omitted when there are none.
    output = render(to_rich(snapshot))
    assert all(text in output for text in present)
    assert all(text not in output for text in absent)


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        ([track("A")], [track("A")], "No track changes"),
        ([track("A"), track("B")], [track("B"), track("A")], "moved"),
        ([track("A")], [track("A"), track("B")], "added"),
        ([track("A"), track("B")], [track("B")], "removed"),
    ],
    ids=["unchanged", "moved", "added", "removed"],
)
def test_diff(
    before: list[OfflineTrack], after: list[OfflineTrack], expected: str
) -> None:
    # One case per operation the renderer can emit, plus the no-op message.
    operations = list_diff(before, after, key_func=lambda t: t)
    assert expected in render(to_rich(operations))


def test_render_examples() -> None:
    """Render one example per format (view with ``pytest -s``)."""
    examples = {
        "id": Group(to_rich(MockPlaylistID("abc")), to_rich(MockTrackID("abc"))),
        "snapshot": Snapshot(
            name="Mix",
            description="Dance",
            tracks=[
                track("One", MockTrackID("one"), ISRC("USRC17607839")),
                track("Two"),
            ],
        ),
        "diff": list_diff(
            [track("One", MockTrackID("one")), track("Two", MockTrackID("two"))],
            [track("Two", MockTrackID("two")), track("Three", MockTrackID("three"))],
            key_func=lambda t: t,
        ),
        "tracks": render_tracks(
            [track("One", MockTrackID("one"), ISRC("USRC17607839")), track("Two")]
        ),
        "playlists": render_playlists([mock_playlist()], title="Playlists"),
    }

    console = Console(highlight=False, record=True)
    for label, example in examples.items():
        console.rule(label)
        console.print(to_rich(example))

    # Assert the labels so the gallery cannot silently render nothing.
    output = console.export_text()
    assert all(label in output for label in examples)


class TestConfirmOrAbort:
    """``confirm_or_abort`` prints the change and asks for confirmation."""

    def test_yes_skips_prompt_and_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stream = io.StringIO()
        ask = Mock(side_effect=AssertionError("prompted"))
        monkeypatch.setattr(Confirm, "ask", ask)

        confirm_or_abort(Console(file=stream), Text("change"), yes=True, default=False)

        ask.assert_not_called()
        assert stream.getvalue() == ""

    def test_prints_renderable_before_asking(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stream = io.StringIO()
        ask = Mock(return_value=True)
        monkeypatch.setattr(Confirm, "ask", ask)

        confirm_or_abort(Console(file=stream), Text("change"), yes=False, default=False)

        ask.assert_called_once()
        assert "change" in strip_ansi(stream.getvalue())

    def test_declining_aborts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stream = io.StringIO()
        monkeypatch.setattr(Confirm, "ask", Mock(return_value=False))

        with pytest.raises(typer.Exit) as exc:
            confirm_or_abort(
                Console(file=stream), Text("change"), yes=False, default=False
            )

        assert exc.value.exit_code == 1
        output = strip_ansi(stream.getvalue())
        assert "change" in output
        assert "Aborted" in output
