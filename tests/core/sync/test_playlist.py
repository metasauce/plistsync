"""Tests for the SyncedPlaylist cross-service synchronisation logic."""

from unittest.mock import Mock, patch

import pytest

from plistsync.core.ids import ISRC, PlaylistID
from plistsync.core.crdt.lww import LWWRegister
from plistsync.core.matching import Matches
from plistsync.core.playlist import PlaylistInfo
from plistsync.core.sync.playlist import SyncedPlaylist, SyncedPlaylistID
from plistsync.core.track import OfflineTrack
from plistsync.services.spotify import SpotifyPlaylistID
from plistsync.services.tidal import TidalPlaylistID

from ..mock_playlist import MockServicePlaylist
from ..mock_track import MockTrack

SPOTIFY_ID = SpotifyPlaylistID.parse("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M")
TIDAL_ID = TidalPlaylistID.parse("tidal:playlist:1293")


def make_track(title: str, isrc: str) -> MockTrack:
    """Create a mock track with a unique title and ISRC.

    Titles/artists must be distinct enough to not fuzzy-match each other
    (Collection.match cutoff is 0.6), otherwise tests become non-deterministic.
    """
    return MockTrack(title=title, artists=[f"{title} Artist"], ids={ISRC(isrc)})


def make_playlist(
    tracks: list[MockTrack] | None = None,
    id: PlaylistID = SPOTIFY_ID,
    name: str = "Mock",
) -> MockServicePlaylist:
    """Create a mock service playlist with a stubbed-out library."""
    playlist = MockServicePlaylist(
        info=PlaylistInfo(name=name, description=None),
        id=id,
        tracks=tracks or [],
    )
    playlist.library = Mock()
    # By default, the library knows nothing (all matching happens in-playlist).
    playlist.library.match = Mock(
        side_effect=lambda track: Matches(truth=track, found=[])
    )
    playlist.library.get_playlist_or_raise = Mock(side_effect=lambda id: playlist)
    return playlist


@pytest.fixture
def track_a() -> MockTrack:
    return make_track("Bohemian Rhapsody", "AAAA1111111A")


@pytest.fixture
def track_b() -> MockTrack:
    return make_track("Lithium", "BBBB2222222B")


@pytest.fixture
def track_c() -> MockTrack:
    return make_track("Toxicity", "CCCC3333333C")


def isrcs(tracks) -> set[str]:
    """Return the serials of all ISRCs of the given tracks."""
    return {tid.serial for t in tracks for tid in t.ids}


class TestSyncedPlaylistID:
    def test_new_generates_unique_ids(self):
        assert SyncedPlaylistID.new() != SyncedPlaylistID.new()

    def test_parse_roundtrip(self):
        pid = SyncedPlaylistID.new()
        parsed = SyncedPlaylistID.parse(str(pid))
        assert parsed == pid
        assert parsed.serial == pid.serial

    @pytest.mark.parametrize("value", ["not-a-uuid", "123", ""])
    def test_parse_invalid_raises(self, value: str):
        with pytest.raises(ValueError):
            SyncedPlaylistID.parse(value)


class TestSyncedPlaylistProtocol:
    """The Playlist-protocol surface of SyncedPlaylist."""

    def test_init_empty(self):
        playlist = SyncedPlaylist("Name", description="desc")
        assert playlist.info == {"name": "Name", "description": "desc"}
        assert playlist.tracks == []
        assert isinstance(playlist.id, SyncedPlaylistID)

    def test_init_with_tracks(self, track_a, track_b):
        playlist = SyncedPlaylist(
            "Name", tracks=[OfflineTrack.from_track(track_a), track_b]
        )
        assert playlist.tracks == [track_a, track_b]

    def test_info_setter(self):
        playlist = SyncedPlaylist("Old")
        playlist.info = PlaylistInfo(name="New", description=None)
        assert playlist.name == "New"

    def test_id(self):
        assert isinstance(SyncedPlaylist("x").id, PlaylistID)

    def test_tracks_setter_not_supported(self):
        playlist = SyncedPlaylist("x")
        with pytest.raises(NotImplementedError, match="sync"):
            playlist.tracks = []


class TestRegister:
    def test_register_empty_playlist(self):
        playlist = SyncedPlaylist("x")
        service = make_playlist()

        playlist.register(service)

        assert playlist._linked_playlists == {1: service}
        assert playlist.tracks == []

    def test_register_merges_service_tracks(self, track_a, track_b):
        playlist = SyncedPlaylist("x")
        service = make_playlist([track_a, track_b])

        playlist.register(service)

        assert isrcs(playlist.tracks) == isrcs([track_a, track_b])

    def test_register_preserves_internal_tracks(self, track_a, track_b):
        playlist = SyncedPlaylist("x", tracks=[OfflineTrack.from_track(track_a)])
        service = make_playlist([track_b])

        playlist.register(service)

        assert isrcs(playlist.tracks) == isrcs([track_a, track_b])

    def test_register_pushes_internal_tracks(self, track_a, track_b):
        """Tracks already in the internal collection appear in the new playlist."""
        playlist = SyncedPlaylist("x", tracks=[OfflineTrack.from_track(track_a)])
        service = make_playlist([track_b])
        # The service's library can resolve track_a (it exists in its catalog).
        service.library.match = Mock(
            return_value=Matches(
                truth=track_a, found=[track_a], found_similarities=[1.0]
            )
        )

        playlist.register(service)

        assert isrcs(service.tracks) == isrcs([track_b, track_a])

    def test_register_assigns_incrementing_replica_ids(self):
        playlist = SyncedPlaylist("x")
        first, second = make_playlist(), make_playlist(id=TIDAL_ID)

        playlist.register(first)
        playlist.register(second)

        assert playlist._linked_playlists == {1: first, 2: second}


class TestRefresh:
    def test_refresh_replaces_linked_playlists(self):
        playlist = SyncedPlaylist("x")
        service = make_playlist()
        refreshed = make_playlist()
        playlist.register(service)

        service.library.get_playlist_or_raise = Mock(return_value=refreshed)
        playlist.fetch()

        service.library.get_playlist_or_raise.assert_called_once_with(id=service.id)
        assert playlist._linked_playlists[1] is refreshed


class TestMerge:
    def test_merge_added_track(self, track_a, track_b):
        playlist = SyncedPlaylist("x")
        service = make_playlist([track_a])
        playlist.register(service)

        # External change: track_b added on the service
        service.tracks = [track_a, track_b]
        playlist.merge()

        assert isrcs(playlist.tracks) == isrcs([track_a, track_b])

    def test_merge_removed_track(self, track_a, track_b):
        playlist = SyncedPlaylist("x")
        service = make_playlist([track_a, track_b])
        playlist.register(service)

        # External change: track_a removed on the service
        service.tracks = [track_b]
        playlist.merge()

        assert isrcs(playlist.tracks) == isrcs([track_b])

    def test_merge_reordered_tracks(self, track_a, track_b):
        playlist = SyncedPlaylist("x")
        service = make_playlist([track_a, track_b])
        playlist.register(service)

        # External change: order flipped on the service
        service.tracks = [track_b, track_a]
        playlist.merge()

        assert isrcs(playlist.tracks) == isrcs([track_b, track_a])
        assert playlist.tracks[0].ids == track_b.ids

    def test_merge_tracks_from_other_playlist_untouched(
        self, track_a, track_b, track_c
    ):
        """A track missing from one service must not be deleted by its merge."""
        playlist = SyncedPlaylist("x")
        first = make_playlist([track_a, track_b])
        second = make_playlist(id=TIDAL_ID)
        playlist.register(first)
        playlist.register(second)

        # track_a + track_b are in the internal collection, but `second` is empty.
        # track_c gets added to `second` externally.
        second.tracks = [track_c]
        playlist.merge()

        # track_a/track_b (only in `first`) survive; track_c is merged in.
        assert isrcs(playlist.tracks) == isrcs([track_a, track_b, track_c])


class TestMergeInfo:
    """Merging of playlist metadata (name/description) from linked playlists."""

    def test_service_name_is_not_merged(self):
        playlist = SyncedPlaylist("internal")
        service = make_playlist(name="service")
        playlist.register(service)

        playlist.merge()

        assert "name" in playlist.info
        assert playlist.info["name"] == "internal"

    def test_unchanged_service_creates_no_ops(self):
        playlist = SyncedPlaylist("internal")
        service = make_playlist(name="service")
        playlist.register(service)

        playlist.merge()
        ops_before = len(playlist._info.history("name"))
        playlist.merge()

        assert len(playlist._info.history("name")) == ops_before

    def test_local_edit_not_clobbered_by_unchanged_service(self):
        playlist = SyncedPlaylist("internal")
        service = make_playlist(name="service")
        playlist.register(service)
        playlist.merge()

        playlist.name = "local-edit"
        playlist.merge()

        assert "name" in playlist.info
        assert playlist.info["name"] == "local-edit"

    def test_service_rename_is_merged(self):
        playlist = SyncedPlaylist("internal")
        service = make_playlist(name="service")
        playlist.register(service)
        playlist.merge()

        service.info = PlaylistInfo(name="renamed")
        playlist.merge()

        assert "name" in playlist.info
        assert playlist.info["name"] == "renamed"

    def test_conflicting_names_resolve_deterministically(self):
        playlist = SyncedPlaylist("internal")
        first = make_playlist(name="one")
        second = make_playlist(name="two", id=TIDAL_ID)
        playlist.register(first)
        playlist.register(second)

        # Update names
        first.name = "one"
        second.name = "two"

        playlist.merge()

        # Replica 2 merged after replica 1, so its op has the higher counter.
        assert "name" in playlist.info
        assert playlist.info["name"] == "two"

    def test_merge_is_order_independent(self):
        """Replaying the produced ops in any order yields the same winner."""
        playlist = SyncedPlaylist("internal")
        first = make_playlist(name="one")
        second = make_playlist(name="two", id=TIDAL_ID)
        playlist._linked_playlists[1] = first
        playlist._linked_playlists[2] = second
        playlist.merge()

        other = LWWRegister()
        for op in reversed(playlist._info.history("name")):
            other.apply(op)

        assert "name" in playlist.info
        assert other["name"] == playlist.info["name"]

    def test_description_is_merged(self):
        playlist = SyncedPlaylist("internal")
        service = make_playlist(name="service")
        playlist.register(service)

        service.info = PlaylistInfo(name="service", description="service desc")

        playlist.merge()

        assert "description" in playlist.info
        assert playlist.info["description"] == "service desc"

    def test_missing_description_is_untouched(self):
        """Fields absent from the service's info are not treated as deletions."""
        playlist = SyncedPlaylist("internal", description="internal desc")
        service = make_playlist(name="service")
        service.info = PlaylistInfo(name="service")  # no description key
        playlist.register(service)

        playlist.merge()

        assert "description" in playlist.info
        assert playlist.info["description"] == "internal desc"

    def test_none_description_clears_internal(self):
        """An explicit None description overwrites/clears the internal value."""
        playlist = SyncedPlaylist("internal", description="internal desc")
        service = make_playlist(name="service")
        playlist.register(
            service  # <- Overwrite the service's info internal info
        )

        # External change: service's description is cleared
        service.info = PlaylistInfo(name="service", description=None)

        # Merge should propagate the None value to the internal info.
        playlist.merge()

        assert "description" in playlist.info
        assert playlist.info["description"] is None


class TestEnrich:
    def test_enrich_adds_playlist_association_and_ids(self, track_a):
        """A track present on the service gets linked and enriched."""
        playlist = SyncedPlaylist("x", tracks=[OfflineTrack.from_track(track_a)])
        service = make_playlist([track_a])
        # Only register the playlist in the internal mapping, without
        # going through register() (which already enriches).
        playlist._linked_playlists[1] = service

        service_track = MockTrack(
            title=track_a.title,
            artists=track_a.artists,
            ids={ISRC("ZZZZ9999999Z")},
        )
        service.match = Mock(
            return_value=Matches(
                truth=track_a, found=[service_track], found_similarities=[1.0]
            )
        )

        playlist.enrich()

        (link,) = playlist._fugue
        assert service.id in link.playlists
        # The internal track picked up the id of its service match.
        assert ISRC("ZZZZ9999999Z") in link.track.ids

    def test_enrich_falls_back_to_library(self, track_a):
        """If the playlist itself has no match, the library is consulted."""
        playlist = SyncedPlaylist("x", tracks=[OfflineTrack.from_track(track_a)])
        service = make_playlist()
        playlist._linked_playlists[1] = service

        service.library.match = Mock(
            return_value=Matches(
                truth=track_a, found=[track_a], found_similarities=[1.0]
            )
        )

        playlist.enrich()

        service.library.match.assert_called_once()
        (link,) = playlist._fugue
        assert service.id in link.playlists

    def test_enrich_without_match_keeps_track_unlinked(self, track_a):
        playlist = SyncedPlaylist("x", tracks=[OfflineTrack.from_track(track_a)])
        service = make_playlist()
        playlist._linked_playlists[1] = service

        playlist.enrich()

        (link,) = playlist._fugue
        assert link.playlists == set()


class TestPush:
    def test_push_aligns_service_playlist(self, track_a, track_b):
        playlist = SyncedPlaylist(
            "x",
            tracks=[OfflineTrack.from_track(track_a), OfflineTrack.from_track(track_b)],
        )
        service = make_playlist([track_a, track_b])
        playlist._linked_playlists[1] = service
        # Link the internal tracks to the service playlist.
        for link in playlist._fugue:
            link.playlists.add(service.id)

        playlist.push()

        assert isrcs(service.tracks) == isrcs([track_a, track_b])

    def test_push_skips_unlinked_tracks(self, track_a, track_b):
        """Tracks not associated with the playlist are not pushed."""
        playlist = SyncedPlaylist(
            "x",
            tracks=[OfflineTrack.from_track(track_a), OfflineTrack.from_track(track_b)],
        )
        service = make_playlist([track_a])
        playlist._linked_playlists[1] = service
        # Only the first track is linked.
        link = next(iter(playlist._fugue))
        link.playlists.add(service.id)

        playlist.push()

        assert isrcs(service.tracks) == isrcs([track_a])

    def test_push_removes_association_when_track_not_found(self, track_a):
        """Unresolvable tracks are dropped from the playlist association."""
        playlist = SyncedPlaylist("x", tracks=[OfflineTrack.from_track(track_a)])
        service = make_playlist()
        playlist._linked_playlists[1] = service
        link = next(iter(playlist._fugue))
        link.playlists.add(service.id)

        # Neither the playlist nor the library can resolve the track.
        service.match = Mock(return_value=Matches(truth=track_a, found=[]))

        playlist.push()

        assert service.id not in link.playlists
        assert service.tracks == []


class TestSync:
    def test_sync_calls_phases_in_order(self):
        playlist = SyncedPlaylist("x")
        with (
            patch.object(playlist, "fetch") as fetch,
            patch.object(playlist, "merge") as merge,
            patch.object(playlist, "enrich") as enrich,
            patch.object(playlist, "push") as push,
        ):
            playlist.sync()

        fetch.assert_called_once_with()
        merge.assert_called_once_with()
        enrich.assert_called_once_with()
        push.assert_called_once_with()

    def test_sync_end_to_end(self, track_a, track_b, track_c):
        """Two service playlists converge to the same tracks after sync."""
        playlist = SyncedPlaylist("x")
        first = make_playlist([track_a, track_b])
        second = make_playlist([track_c], id=TIDAL_ID)
        # Both libraries can resolve every track (full catalog availability).
        for service in (first, second):
            service.library.match = Mock(
                side_effect=lambda track: Matches(
                    truth=track, found=[track], found_similarities=[1.0]
                )
            )
        playlist.register(first)
        playlist.register(second)

        # External change: track_b removed from `first`
        first.tracks = [track_a]
        playlist.sync()

        assert isrcs(playlist.tracks) == isrcs([track_a, track_c])
        assert isrcs(first.tracks) == isrcs([track_a, track_c])
        assert isrcs(second.tracks) == isrcs([track_a, track_c])
