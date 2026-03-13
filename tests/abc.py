from contextlib import nullcontext
import pytest
from pathlib import PurePath
from typing import Any, ClassVar
from abc import ABC, abstractmethod

from plistsync.core import LibraryCollection, Track, Collection
from plistsync.core.collection import (
    GlobalLookup,
    InfoLookup,
    Iterable,
    LocalLookup,
    TrackStream,
)
from plistsync.core.matching import Matches
from plistsync.core.playlist import PlaylistCollection, Snapshot

from unittest.mock import Mock, ANY


class TrackTestBase(ABC):
    """Base class for testing tracks.

    Implements some basic tests for tracks which should be the same for all tracks.
    """

    track_class: ClassVar[type[Track]]

    test_config = {
        "has_path": False,
    }

    @abstractmethod
    def create_track(self, *args, **kwargs) -> Iterable[Track]:
        """Create a track for testing.

        This method should create a track with some dummy data. Has to be implemented by the subclass.
        """
        pass

    # ---------------------------------------------------------------------------- #
    #                             Test abstract methods                            #
    # ---------------------------------------------------------------------------- #

    def test_title(self):
        for track in self.create_track():
            assert isinstance(track.title, str), "Title should be a string"

    def test_artists(self):
        for track in self.create_track():
            assert isinstance(track.artists, list), "Artists should be a list"

    def test_albums(self):
        for track in self.create_track():
            assert isinstance(track.albums, list), "Albums should be a list"

    def test_identifiers(self):
        for track in self.create_track():
            assert isinstance(track.global_ids, dict), "Identifiers should be a dict"

    # ---------------------------------------------------------------------------- #
    #                              Test Common methods                             #
    # ---------------------------------------------------------------------------- #

    def test_isrc(self):
        for track in self.create_track():
            assert isinstance(track.isrc, (str, type(None))), (
                "ISRC should be a string or None"
            )

    def test_primary_artist(self):
        for track in self.create_track():
            assert isinstance(track.primary_artist, (str, type(None))), (
                "Primary artist should be a string or None"
            )

    # ---------------------------------------------------------------------------- #

    def test_path(self):
        for track in self.create_track():
            if self.test_config["has_path"]:
                assert isinstance(track.path, PurePath), "Path should be a Path object"
            else:
                with pytest.raises(NotImplementedError):
                    track.path


class CollectionTestBase(ABC):
    """Base class for testing collections.

    Implements some basic tests for collections that should be the same for all types of collections.
    """

    collection_class: ClassVar[type[Collection]]

    @abstractmethod
    def create_collection(self, *args, **kwargs) -> Iterable[Collection]:
        """Create a collection for testing.

        This method should create a collection with some dummy data. It must be implemented by the subclass.
        """
        pass

    @abstractmethod
    def create_sample_track(self) -> Track:
        """Create a sample track for testing matches within collections.
        This has to be implemented by the subclass and be a valid Track in the
        collection!
        """
        pass

    def test_global_lookup(self):
        """Test collections that implement GlobalLookup."""
        track = self.create_sample_track()
        for collection in self.create_collection():
            if isinstance(collection, GlobalLookup):
                found_track = collection.find_by_global_ids(track.global_ids)
                # assumptions on the track returned by global id lookup
                assert found_track is None or found_track == track, (
                    "Global lookup should return the matching track or None"
                )

    def test_local_lookup(self):
        """Test collections that implement LocalLookup."""
        track = self.create_sample_track()
        for collection in self.create_collection():
            if isinstance(collection, LocalLookup):
                found_track = collection.find_by_local_ids(track.local_ids)
                # assumptions on the track returned by local id lookup
                # TODO PS@semohr how do we want to decide that "they are equal"?
                assert found_track is None or found_track.diff(track) == {}, (
                    "Local lookup should return the matching track or None"
                )

    def test_info_lookup(self):
        """Test collections that implement InfoLookup."""
        track = self.create_sample_track()
        for collection in self.create_collection():
            if isinstance(collection, InfoLookup):
                found_tracks = list(collection.find_by_info(track.info))
                # assumptions on the track returned by info lookup
                assert all(isinstance(t, Track) for t in found_tracks), (
                    "Info lookup should return iterable of Track instances"
                )

    def test_track_stream(self):
        """Test collections that implement TrackStream."""
        for collection in self.create_collection():
            if isinstance(collection, TrackStream):
                tracks = list(collection.tracks)
                # assumptions on the track returned by track stream
                assert all(isinstance(t, Track) for t in tracks), (
                    "Track Stream should return iterable over Track instances"
                )

    def test_match_method(self):
        """Test the collection's match method."""
        track = self.create_sample_track()
        for collection in self.create_collection():
            matches = collection.match(track)
            assert isinstance(matches, Matches), (
                "Match method should return Matches instance"
            )
            # Further tests could include verifying the contents of Matches


class LibraryCollectionTestBase(CollectionTestBase, ABC):
    @abstractmethod
    def create_collection(self, *args, **kwargs) -> Iterable[LibraryCollection]:
        """Create a collection for testing.

        This method should create a collection with some dummy data. It must be implemented by the subclass.
        """
        pass

    @property
    @abstractmethod
    def known_playlists(self) -> Iterable[tuple[str, Any]]:
        """Know playlist for lookup by [key, value].

        E.g. ["uri", "spotify:asdasdasd"]
        will call get_playlist(uri="spotify:asdasdasd")
        """
        pass

    @property
    @abstractmethod
    def unknown_playlists(self) -> Iterable[tuple[str, Any]]:
        """Unknow playlist for lookup by [key, value].

        E.g. ["uri", "spotify:not_found"]
        will call get_playlist(uri="spotify:asdasdasd") -> check None
        and get_playlist_or_raise(uri="spotify:asdasdasd") -> check raises
        """

        pass

    def test_playlists_property(self):
        """Test that the playlists property returns the expected results."""
        for library_collection in self.create_collection():
            playlists = library_collection.playlists
            assert isinstance(playlists, Iterable), "Playlists should be iterable"
            # Optionally: further assertions based on expected behavior, e.g., length, types
            for pl in playlists:
                assert isinstance(pl, PlaylistCollection)

    def test_get_playlist_known(self):
        """Test retrieval of playlists by name or identifier."""
        for library_collection in self.create_collection():
            for key, identifier in self.known_playlists:
                playlist = library_collection.get_playlist(**{key: identifier})
                assert playlist is not None, "Known playlist should be found"

    def test_get_playlist_unknown(self):
        """Test retrieval of unknown playlists by name or identifier."""
        for library_collection in self.create_collection():
            for key, identifier in self.unknown_playlists:
                playlist = library_collection.get_playlist(**{key: identifier})
                assert playlist is None, "Unknown playlist should not be found"

                with pytest.raises(ValueError):
                    playlist = library_collection.get_playlist_or_raise(
                        **{key: identifier}
                    )


class PlaylistCollectionTestBase(ABC):
    """Base class for testing PlaylistCollection implementations.

    Assumes the implementation under test records remote operations in a log
    (e.g. ('insert', idx, track), ('remote_create',), ...).
    """

    @abstractmethod
    def create_playlist(
        self,
        *,
        remote_associated: bool = True,
    ) -> PlaylistCollection:
        raise NotImplementedError

    @abstractmethod
    def create_track(self, *, isrc: str) -> Track:
        raise NotImplementedError

    def test_info(self) -> None:
        pl = self.create_playlist()
        assert isinstance(pl.info, dict)

        # Name is required
        assert "name" in pl.info
        assert isinstance(pl.info["name"], str)

    def test_name_reflects_info(self) -> None:
        pl = self.create_playlist()

        assert pl.name == pl.info["name"]  # type: ignore

    def test_name_setter(self) -> None:
        pl = self.create_playlist()
        new_name = f"{pl.name} (updated)"

        pl.name = new_name

        assert pl.name == new_name
        assert pl.info["name"] == new_name  # type: ignore

    def test_description(self) -> None:
        pl = self.create_playlist()
        new_description = f"{pl.description} (updated)"
        pl.description = new_description

        assert pl.description == new_description
        assert pl.info.get("description") == new_description

        # Setter should also support none
        pl.description = None
        assert pl.description is None
        assert pl.info.get("description") is None

    def test_tracks(self) -> None:
        pl = self.create_playlist()
        t1 = self.create_track(isrc="t1")
        t2 = self.create_track(isrc="t2")

        assert isinstance(pl.tracks, list)

        # Test setter
        pl.tracks = [t1, t2]
        assert pl.tracks == [t1, t2]
        assert len(pl) == 2
        assert len(pl) == len(pl.tracks)

    # -------------------------------- remote_edit ------------------------------- #

    def test_remote_edit_raises_when_not_associated(self) -> None:
        pl = self.create_playlist(remote_associated=False)

        with pytest.raises(ValueError, match="remote_edit\\(\\)"):
            with pl.remote_edit():
                pass

    def test_remote_edit_calls_apply_diff_on_success(self) -> None:
        pl = self.create_playlist(remote_associated=True)
        old_name = pl.name

        pl._apply_diff = Mock()

        with pl.remote_edit():
            pl.name = f"{old_name} (updated)"

        pl._apply_diff.assert_called_once()
        before, after = pl._apply_diff.call_args.args
        assert isinstance(before, Snapshot)
        assert isinstance(after, Snapshot)
        assert before.name == old_name
        assert after.name == f"{old_name} (updated)"

    def test_remote_edit_rolls_back_on_exception(self) -> None:
        pl = self.create_playlist(remote_associated=True)
        initial_name = pl.name
        initial_description = pl.description
        initial_tracks = list(pl.tracks)

        pl._apply_diff = Mock()

        with pytest.raises(ValueError):
            with pl.remote_edit():
                pl.name = f"{initial_name} (updated)"
                pl.description = f"{initial_description} (updated)"
                pl.tracks = [self.create_track(isrc="t1")]
                raise ValueError("test error")

        # rollback happened
        assert pl.name == initial_name
        assert pl.description == initial_description
        assert pl.tracks == initial_tracks

        # since we errored inside the context, diff application should not run
        pl._apply_diff.assert_not_called()

    # ------------------------------- remote_create ------------------------------ #

    @pytest.mark.parametrize(
        "remote_associated, expect_raise, match",
        [
            (True, True, "already associated"),
            (False, False, ""),
        ],
    )
    def test_remote_create(
        self,
        remote_associated: bool,
        expect_raise: bool,
        match: str,
    ) -> None:
        pl = self.create_playlist(remote_associated=remote_associated)

        sentinel = object()
        mocked = Mock(return_value=sentinel)
        pl._remote_create = mocked

        ctx = pytest.raises(ValueError, match=match) if expect_raise else nullcontext()
        with ctx:
            result = pl.remote_create()
            if not expect_raise:
                assert result is sentinel

        if expect_raise:
            mocked.assert_not_called()
        else:
            mocked.assert_called_once_with()

    # ------------------------------- remote_delete ------------------------------ #

    @pytest.mark.parametrize(
        "remote_associated, expect_raise, match",
        [
            (False, True, "associated"),
            (True, False, ""),
        ],
    )
    def test_remote_delete(
        self,
        remote_associated: bool,
        expect_raise: bool,
        match: str,
    ) -> None:
        pl = self.create_playlist(remote_associated=remote_associated)

        sentinel = object()
        mocked = Mock(return_value=sentinel)
        pl._remote_delete = mocked

        ctx = pytest.raises(ValueError, match=match) if expect_raise else nullcontext()
        with ctx:
            result = pl.remote_delete()
            if not expect_raise:
                assert result is sentinel

        if expect_raise:
            mocked.assert_not_called()
        else:
            mocked.assert_called_once_with()

    # -------------------------------- _apply_diff ------------------------------- #

    def test_apply_diff_noop_does_nothing(self) -> None:
        pl = self.create_playlist(remote_associated=True)
        t1 = self.create_track(isrc="1")

        pl._remote_update_metadata = Mock()
        pl._remote_insert_track = Mock()
        pl._remote_delete_track = Mock()
        pl._remote_move_track = Mock()

        before = Snapshot(name="n", description=None, tracks=[t1])
        after = Snapshot(name="n", description=None, tracks=[t1])

        pl._apply_diff(before, after)

        pl._remote_update_metadata.assert_not_called()
        pl._remote_insert_track.assert_not_called()
        pl._remote_delete_track.assert_not_called()
        pl._remote_move_track.assert_not_called()

    def test_apply_diff_updates_metadata_only(self) -> None:
        pl = self.create_playlist(remote_associated=True)
        t1 = self.create_track(isrc="1")

        pl._remote_update_metadata = Mock()
        pl._remote_insert_track = Mock()
        pl._remote_delete_track = Mock()
        pl._remote_move_track = Mock()

        before = Snapshot(name="old", description="d1", tracks=[t1])
        after = Snapshot(name="new", description="d2", tracks=[t1])

        pl._apply_diff(before, after)

        pl._remote_update_metadata.assert_called_once_with("new", "d2")
        pl._remote_insert_track.assert_not_called()
        pl._remote_delete_track.assert_not_called()
        pl._remote_move_track.assert_not_called()

    def test_apply_diff_inserts_track(self) -> None:
        pl = self.create_playlist(remote_associated=True)
        t1 = self.create_track(isrc="1")
        t4 = self.create_track(isrc="4")

        # sanity: track keys must distinguish tracks (otherwise list_diff can't work)
        assert pl._track_key(t1) != pl._track_key(t4)  # type: ignore[misc]

        pl._remote_update_metadata = Mock()
        pl._remote_insert_track = Mock()
        pl._remote_delete_track = Mock()
        pl._remote_move_track = Mock()

        before = Snapshot(name="n", description=None, tracks=[t4])
        after = Snapshot(name="n", description=None, tracks=[t1, t4])

        pl._apply_diff(before, after)

        pl._remote_update_metadata.assert_not_called()
        pl._remote_insert_track.assert_called_once_with(
            idx=0, track=[t1], tracks_before=ANY
        )
        pl._remote_delete_track.assert_not_called()
        pl._remote_move_track.assert_not_called()
