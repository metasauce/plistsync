from abc import ABC, abstractmethod
from contextlib import nullcontext
from functools import wraps
from typing import Any, ClassVar, ParamSpec, TypeVar
from collections.abc import Callable
from unittest.mock import ANY, Mock, PropertyMock

import pytest

from plistsync.core.playlist import (
    MultiRequestPlaylistCollection,
    PlaylistCollection,
    Snapshot,
)
from plistsync.errors import PlaylistAssociationError


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


class TestPlaylistCollection(ABC):
    """Abstract base class for testing 'PlaylistCollection' implementations.

    Provides a unified test interface for validating playlist collection
    functionality across different music service implementations. This ensures
    consistent behavior regardless of the underlying service (Spotify, Tidal,
    Plex, etc.).

    Subclasses must implement the 'Playlist' class attribute to a valid
    class of the collection you want to test.

    Usage:

    ```python

    class TestSpotifyPlaylist(TestPlaylistCollection):
        Playlist = SpotifyPlaylistCollection
    ```

    This class is intended as unit test and does not perform any requests. It
    mocks any methods that are not required by the base implementation!
    """

    Playlist: ClassVar[type[PlaylistCollection]]
    supports_description: ClassVar[bool]

    @abstractmethod
    def create_playlist(self) -> PlaylistCollection:
        """Create a playlist.

        FIXME: Temporary until we unify the playlist init!
        """
        ...

    @pytest.fixture
    def playlist(self) -> PlaylistCollection:
        return self.create_playlist()

    def test_property_info(self, playlist: PlaylistCollection) -> None:
        """Info returns at least a name."""

        assert isinstance(playlist.info, dict)
        assert "name" in playlist.info
        assert isinstance(playlist.info["name"], str)

    def test_property_name(self, playlist: PlaylistCollection) -> None:
        """Name property can be used and reflects the info."""

        new_name = f"{playlist.name} (updated)"
        playlist.name = new_name

        assert playlist.name == new_name
        assert playlist.info.get("name") == new_name

    @requires_feature("supports_description")
    def test_property_description(self, playlist: PlaylistCollection) -> None:
        """Description can be set and retrieved."""

        new_description = f"{playlist.description} (updated)"
        playlist.description = new_description

        assert playlist.description == new_description
        assert playlist.info.get("description") == new_description

        # Setter should also support none
        playlist.description = None
        assert playlist.description is None
        assert playlist.info.get("description") is None

    def test_property_tracks(self, playlist: PlaylistCollection) -> None:
        """Tracks can be set and retrieved"""

        dummy_tracks = [i for i in range(5)]

        # Test append
        assert isinstance(playlist.tracks, list)
        for t in dummy_tracks:
            playlist.tracks.append(t)
        assert len(playlist.tracks) == len(dummy_tracks)
        assert len(playlist) == len(dummy_tracks)
        assert playlist.tracks == dummy_tracks

        # Test overwrite
        playlist.tracks = dummy_tracks
        assert len(playlist.tracks) == len(dummy_tracks)
        assert len(playlist) == len(dummy_tracks)
        assert playlist.tracks == dummy_tracks

    @pytest.mark.parametrize(
        ("remote_associated", "should_error", "method"),
        [
            (True, True, "remote_create"),
            (False, False, "remote_create"),
            (False, True, "remote_delete"),
            (True, False, "remote_delete"),
            (False, True, "remote_edit"),
            (True, False, "remote_edit"),
        ],
    )
    def test_remote_methods(
        self,
        playlist: PlaylistCollection,
        remote_associated: bool,
        should_error: bool,
        method: str,
    ) -> None:
        """All remote methods error when expected.

        This is mostly a smoke test and does mocks most irelevant methods.
        """
        # Mock remote_associated
        type(playlist).remote_associated = PropertyMock(return_value=remote_associated)

        mock = Mock()
        playlist._remote_create = mock
        playlist._remote_delete = mock
        playlist._remote_commit = mock

        ctx = pytest.raises(PlaylistAssociationError) if should_error else nullcontext()

        with ctx:
            if method == "remote_edit":
                with playlist.remote_edit():
                    pass
            else:
                getattr(playlist, method)()

        assert mock.call_count == (0 if should_error else 1)

    def test_remote_edit_rollsback(
        self,
        playlist: PlaylistCollection,
    ) -> None:
        type(playlist).remote_associated = PropertyMock(return_value=True)
        initial_name = playlist.name

        playlist._remote_commit = Mock()

        with pytest.raises(ValueError, match="test error"):
            with playlist.remote_edit():
                playlist.name = f"{initial_name} (updated)"
                raise ValueError("test error")

        # rollback happened
        assert playlist.name == initial_name

        # since we errored inside the context, diff application should not run
        playlist._remote_commit.assert_not_called()


class TestMultiRequestPlaylistCollection(TestPlaylistCollection, ABC):
    @abstractmethod
    def create_playlist(self) -> MultiRequestPlaylistCollection:
        """Create a playlist.

        FIXME: Temporary until we unify the playlist init!
        """
        ...

    @pytest.fixture
    def mocked_playlist(self, playlist: MultiRequestPlaylistCollection):
        type(playlist).remote_associated = PropertyMock(return_value=False)
        playlist._remote_update_metadata = Mock()
        playlist._remote_insert_track = Mock()
        playlist._remote_delete_track = Mock()
        playlist._remote_move_track = Mock()
        return playlist

    def test_remote_commit_noop_does_nothing(
        self,
        mocked_playlist: MultiRequestPlaylistCollection,
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
        mocked_playlist: MultiRequestPlaylistCollection,
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
        mocked_playlist: MultiRequestPlaylistCollection,
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
