from __future__ import annotations
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, ClassVar, ParamSpec, TypeVar, TYPE_CHECKING
from unittest.mock import ANY, Mock

import pytest

from plistsync.core import PlaylistID
from plistsync.core.playlist import (
    Snapshot,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from plistsync.core.playlist import (
        MultiRequestServicePlaylist,
        Playlist,
        ServicePlaylist,
    )


P = ParamSpec("P")
R = TypeVar("R")


def requires_feature(feature: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Skip test if the service doesn't support the given feature."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:  # type: ignore[valid-type]
            obj = args[0] if args else None
            if obj is not None and not getattr(obj, feature, True):
                pytest.skip(f"Feature {feature!r} not supported.")
            return func(*args, **kwargs)

        return wrapper

    return decorator


class TestPlaylistBase(ABC):
    """Abstract base class for testing 'Playlist' implementations.

    Provides a unified test interface for validating playlist collection
    functionality across different music service implementations. This ensures
    consistent behavior regardless of the underlying service.

    This class is intended as unit test and does not perform any requests. It
    mocks any methods that are not required by the base implementation!
    """

    supports_description: ClassVar[bool] = True

    @abstractmethod
    def create_playlist(self) -> Playlist:
        """Create a playlist.

        FIXME: Temporary until we unify the playlist init!
        """
        ...

    @pytest.fixture
    def playlist(self) -> Playlist:
        return self.create_playlist()

    def test_property_info(self, playlist: Playlist) -> None:
        """Info returns at least a name."""

        assert isinstance(playlist.info, dict)
        assert "name" in playlist.info
        assert isinstance(playlist.info["name"], str)

    def test_property_tracks(self, playlist: Playlist) -> None:
        """Tracks can be set and retrieved"""

        if len(playlist.tracks) == 0:
            pytest.skip("Can test track property without tracks in playlist!")

        dummy_tracks = [t for t in playlist.tracks]

        # Test append
        assert isinstance(playlist.tracks, list)
        len_before = len(playlist.tracks)
        for t in dummy_tracks:
            playlist.tracks.append(t)
        assert len(dummy_tracks) + len_before == len(playlist.tracks)
        assert len(dummy_tracks) + len_before == len(playlist)
        assert playlist.tracks[-len_before:] == dummy_tracks

        # Test overwrite
        playlist.tracks = dummy_tracks
        assert len(playlist.tracks) == len(dummy_tracks)
        assert len(playlist) == len(dummy_tracks)
        assert playlist.tracks == dummy_tracks

    def test_id(self, playlist: Playlist) -> None:
        """Id can be retrieved"""

        assert isinstance(playlist.id, PlaylistID)

    def test_property_name(self, playlist: Playlist) -> None:
        """Name property can be used and reflects the info."""

        new_name = f"{playlist.name} (updated)"
        playlist.name = new_name

        assert playlist.name == new_name
        assert playlist.info.get("name") == new_name

    @requires_feature("supports_description")
    def test_property_description(self, playlist: Playlist) -> None:
        """Description can be set and retrieved."""

        new_description = f"{playlist.description} (updated)"
        playlist.description = new_description

        assert playlist.description == new_description
        assert playlist.info.get("description") == new_description

        # Setter should also support none
        playlist.description = None
        assert playlist.description is None
        assert playlist.info.get("description") is None

    def test_get_snapshot(self, playlist: Playlist) -> None:
        """Can create a snapshot"""

        snapshot = playlist.get_snapshot()
        # change playlist
        playlist.name = "new_name"
        playlist.description = "new_description"

        # Should be copies
        keys = {"name", "description", "tracks"}
        if not self.supports_description:
            keys.remove("description")
        for key in keys:
            assert id(getattr(playlist, key)) != id(getattr(snapshot, key))


class TestServicePlaylistBase(TestPlaylistBase, ABC):
    @abstractmethod
    def create_playlist(self) -> ServicePlaylist:
        """Create a playlist.

        FIXME: Temporary until we unify the playlist init!
        """
        ...

    def test_remote_delete(self, playlist: ServicePlaylist):
        """remote_delete returns an OfflinePlaylist with current state."""
        playlist._remote_delete = Mock()

        offline = playlist.delete()

        # Should return an OfflinePlaylist
        assert offline.__class__.__name__ == "OfflinePlaylist"

        # Should contain the playlist's current metadata and tracks
        assert offline.name == playlist.name
        assert offline.description == playlist.description
        assert offline.tracks == playlist.tracks

        # _remote_delete should have been called
        playlist._remote_delete.assert_called_once()

    def test_remote_update(self, playlist: ServicePlaylist):
        library = Mock()
        library.get_playlist_or_raise = Mock(return_value=playlist)
        playlist.library = library
        playlist._remote_commit = Mock()

        playlist.update()

        playlist.library.get_playlist_or_raise.assert_called_once_with(id=playlist.id)
        playlist._remote_commit.assert_called_once()

    def test_remote_edit(self, playlist: ServicePlaylist):
        """remote_edit commits changes when no exception occurs."""
        playlist._remote_commit = Mock()

        with playlist.edit():
            pass

        playlist._remote_commit.assert_called_once()

    def test_remote_edit_rollback(self, playlist: ServicePlaylist):
        """remote_edit commits changes when no exception occurs."""
        playlist._remote_commit = Mock()

        playlist.name = "a name"
        with pytest.raises(ValueError, match="test"):
            with playlist.edit():
                playlist.name = "another name"
                raise ValueError("test")

        # Should rollback
        assert playlist.name == "a name"
        playlist._remote_commit.assert_not_called()


class TestMultiRequestServicePlaylistBase(TestServicePlaylistBase, ABC):
    @abstractmethod
    def create_playlist(self) -> MultiRequestServicePlaylist:
        """Create a playlist.

        FIXME: Temporary until we unify the playlist init!
        """
        ...

    @pytest.fixture
    def mocked_playlist(self, playlist: MultiRequestServicePlaylist):
        playlist._remote_update_metadata = Mock()
        playlist._remote_insert_track = Mock()
        playlist._remote_delete_track = Mock()
        playlist._remote_move_track = Mock()
        return playlist

    def test_remote_commit_noop_does_nothing(
        self,
        mocked_playlist: MultiRequestServicePlaylist,
    ):
        before: Snapshot[Any] = Snapshot(name="n", description=None, tracks=[])
        after: Snapshot[Any] = Snapshot(name="n", description=None, tracks=[])

        mocked_playlist._remote_commit(before, after)

        mocked_playlist._remote_update_metadata.assert_not_called()
        mocked_playlist._remote_insert_track.assert_not_called()
        mocked_playlist._remote_delete_track.assert_not_called()
        mocked_playlist._remote_move_track.assert_not_called()

    def test_remote_commit_updates_metadata_only(
        self,
        mocked_playlist: MultiRequestServicePlaylist,
    ) -> None:
        before: Snapshot[Any] = Snapshot(name="old", description="d1", tracks=[])
        after: Snapshot[Any] = Snapshot(name="new", description="d2", tracks=[])

        mocked_playlist._remote_commit(before, after)

        mocked_playlist._remote_update_metadata.assert_called_once_with("new", "d2")
        mocked_playlist._remote_insert_track.assert_not_called()
        mocked_playlist._remote_delete_track.assert_not_called()
        mocked_playlist._remote_move_track.assert_not_called()

    def test_remote_commit_inserts_track(
        self,
        mocked_playlist: MultiRequestServicePlaylist,
    ) -> None:
        mocked_playlist._track_key = Mock(side_effect=lambda x: x)
        before: Snapshot[Any] = Snapshot(name="n", description=None, tracks=[0, 3, 4])
        after: Snapshot[Any] = Snapshot(name="n", description=None, tracks=[1, 4, 3])

        mocked_playlist._remote_commit(before, after)
        mocked_playlist._remote_update_metadata.assert_not_called()
        mocked_playlist._remote_delete_track.assert_called_once_with(
            idx=0, track=[0], tracks_before=ANY
        )
        mocked_playlist._remote_insert_track.assert_called_once_with(
            idx=0, track=[1], tracks_before=ANY
        )
        mocked_playlist._remote_move_track.assert_called_once_with(
            old_idx=2, new_idx=1, track=4, tracks_before=ANY
        )
