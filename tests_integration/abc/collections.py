"""Ordered collections tests shared by every service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from plistsync.logger import log

if TYPE_CHECKING:
    from collections.abc import Iterator

    from plistsync.core import ServicePlaylist, Track, TrackID

    from .scenario import CollectionsScenario


@dataclass
class CollectionsState:
    """Mutable state shared across the ordered scenario tests."""

    scenario: CollectionsScenario
    playlist: ServicePlaylist[Any, Any] | None = None
    first_track: Track | None = None
    second_track: Track | None = None

    def require_playlist(self) -> ServicePlaylist[Any, Any]:
        if self.playlist is None:
            pytest.fail(
                "Playlist has not been created. The ordered scenario tests must "
                "run in order (test_create_playlist runs before the later steps)."
            )
        return self.playlist


def _matches(track: Track, sample: tuple[TrackID, ...]) -> bool:
    """Whether ``track`` carries any of the identifiers in ``sample``."""
    return any(track_id in track.ids for track_id in sample)


class CollectionsTestBase:
    """Ordered collections scenario applied to one service.

    Subclasses provide a ``scenario`` fixture. The tests share one playlist and
    must run in definition order.
    """

    @pytest.fixture(scope="class")
    def state(self, scenario: CollectionsScenario) -> Iterator[CollectionsState]:
        state = CollectionsState(scenario=scenario)
        try:
            yield state
        finally:
            # Safety net: clean up even if a step failed or was interrupted.
            if state.playlist is not None:
                try:
                    state.playlist.delete()
                except Exception as exc:
                    log.warning(
                        "Failed to clean up playlist %s: %s", state.playlist.id, exc
                    )

    def test_track_lookup_first_track(self, state: CollectionsState) -> None:
        """Look up the first track by each of its identifiers; all must match."""
        scenario = state.scenario
        sample = scenario.tracks[0]

        tracks: list[Track] = []
        for track_id in sample:
            track = scenario.find_track(track_id)
            if track is None:
                pytest.skip(f"{scenario.service}: no track for {track_id!r}")
            tracks.append(track)

        assert all(track == tracks[0] for track in tracks)
        state.first_track = tracks[0]

    def test_track_lookup_second_track(self, state: CollectionsState) -> None:
        """Look up the second track used by the add/reorder/remove steps."""
        scenario = state.scenario
        track = scenario.find_track(scenario.tracks[1][0])
        if track is None:
            pytest.skip(f"{scenario.service}: no track for {scenario.tracks[1][0]!r}")
        state.second_track = track

    def test_list_playlists(self, state: CollectionsState) -> None:
        """Iterate the user's playlists as a retrieval smoke test."""
        playlists = list(state.scenario.library.playlists)
        assert all(playlist.name for playlist in playlists)

    def test_create_playlist(self, state: CollectionsState) -> None:
        """Create a uniquely named playlist and keep it for the later steps."""
        state.playlist = state.scenario.library.create_playlist(
            name=f"plistsync-{state.scenario.service}-{uuid4().hex[:8]}",
            description="Created via plistsync",
        )
        assert state.playlist.name

    def test_get_playlist(self, state: CollectionsState) -> None:
        """Retrieve the created playlist by name and by id."""
        playlist = state.require_playlist()
        library = state.scenario.library

        by_name = library.get_playlist(name=playlist.name)
        assert by_name is not None
        assert by_name.id == playlist.id

        by_id = library.get_playlist_or_raise(id=playlist.id)
        assert by_id.id == playlist.id

    def test_update_description(self, state: CollectionsState) -> None:
        """Edit the description through the ``edit()`` context manager."""
        playlist = state.require_playlist()
        with playlist.edit():
            playlist.description = "Updated description"
        assert playlist.description == "Updated description"

    def test_add_tracks(self, state: CollectionsState) -> None:
        """Add the two looked-up tracks and verify their order."""
        playlist = state.require_playlist()
        assert state.first_track is not None
        assert state.second_track is not None
        scenario = state.scenario

        with playlist.edit():
            playlist.tracks = [state.first_track, state.second_track]

        assert _matches(playlist.tracks[0], scenario.tracks[0])
        assert _matches(playlist.tracks[1], scenario.tracks[1])

    def test_reorder_tracks(self, state: CollectionsState) -> None:
        """Move the last track to the front and verify the new order."""
        playlist = state.require_playlist()
        assert state.first_track is not None
        assert state.second_track is not None
        scenario = state.scenario

        with playlist.edit():
            playlist.tracks.insert(0, playlist.tracks.pop())

        assert _matches(playlist.tracks[0], scenario.tracks[1])
        assert _matches(playlist.tracks[1], scenario.tracks[0])

    def test_remove_track(self, state: CollectionsState) -> None:
        """Remove the last track and verify only the other one remains."""
        playlist = state.require_playlist()
        assert state.second_track is not None

        with playlist.edit():
            playlist.tracks.pop()

        assert len(playlist.tracks) == 1
        assert _matches(playlist.tracks[0], state.scenario.tracks[1])

    def test_delete_playlist(self, state: CollectionsState) -> None:
        """Delete the playlist and verify it can no longer be retrieved."""
        playlist = state.require_playlist()
        library = state.scenario.library
        playlist_id = playlist.id

        playlist.delete()
        state.playlist = None  # avoid deleting it a second time in teardown

        assert library.get_playlist(id=playlist_id) is None
        with pytest.raises(ValueError):
            library.get_playlist_or_raise(id=playlist_id)
