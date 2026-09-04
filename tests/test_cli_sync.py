import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Self
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from plistsync.cli import app
from plistsync.core.ids import ISRC, PlaylistID
from plistsync.core.playlist import PlaylistInfo
from plistsync.core.track import OfflineTrack
from plistsync.services.sync import SyncedPlaylist
from plistsync.services.sync.playlist import _TrackLink
from tests.core.mock_playlist import MockServicePlaylist

runner = CliRunner()


@dataclass(frozen=True)
class _FakePlaylistID(PlaylistID, service="test"):
    """Minimal playlist ID for tests."""

    id: str

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a ``test:playlist:<id>`` serial or raw id."""
        if value.startswith("test:playlist:"):
            value = value[len("test:playlist:") :]
        return cls(value)

    @classmethod
    @cache
    def service(cls) -> str:
        """Service name for the fake."""
        return "test"

    @property
    def serial(self) -> str:
        return f"test:playlist:{self.id}"

    def __str__(self) -> str:
        return self.id


class _FakeLibrary:
    """Minimal library stub returning a mock playlist."""

    def get_playlist_or_raise(self, id):
        return _make_service_playlist(id, "Chill Vibes")


class _FakeService:
    """Duck-typed service stub resolving ``test:playlist:`` ids."""

    name = "test"

    def playlist_ids(self):
        return [_FakePlaylistID]

    def library(self):
        return _FakeLibrary


def _make_service_playlist(
    pid: _FakePlaylistID,
    name: str,
    tracks: list[OfflineTrack] | None = None,
) -> MockServicePlaylist:
    """Create a mock service playlist whose library returns itself."""
    playlist = MockServicePlaylist(
        id=pid,
        info=PlaylistInfo(name=name, description=None),
        tracks=tracks or [],
    )
    playlist.library.get_playlist_or_raise.return_value = playlist
    return playlist


@pytest.fixture
def sync_dir(tmp_path, monkeypatch):
    """Redirect the sync config dir to a temporary directory."""
    sync_dir = tmp_path / "sync"
    sync_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "plistsync.cli.commands.sync.__sync_dir",
        lambda: sync_dir,
    )
    return sync_dir


def _create_synced_playlist(sync_dir, name, description=None) -> SyncedPlaylist:
    """Create and persist a synced playlist, returning it."""
    playlist = SyncedPlaylist(name=name, description=description)
    playlist.save_to(sync_dir / f"{playlist.id}.json")
    return playlist


@pytest.fixture
def synced(sync_dir) -> SyncedPlaylist:
    """A persisted synced playlist named 'Party Mix'."""
    return _create_synced_playlist(sync_dir, name="Party Mix")


class TestSyncCreate:
    """Test the ``plistsync sync create`` command."""

    def test_create(self, sync_dir):
        """create writes a new synced playlist file and prints a summary."""
        result = runner.invoke(app, ["sync", "create", "Party Mix"])

        assert result.exit_code == 0
        assert "Party Mix" in result.output
        assert "ID:" in result.output

        files = list(sync_dir.glob("*.json"))
        assert len(files) == 1
        loaded = SyncedPlaylist.load_from(files[0])
        assert loaded.name == "Party Mix"
        assert loaded.description is None

    def test_create_with_description(self, sync_dir):
        """-d/--description is stored in the playlist metadata."""
        result = runner.invoke(
            app, ["sync", "create", "Party Mix", "-d", "Dancefloor bangers"]
        )

        assert result.exit_code == 0
        loaded = SyncedPlaylist.load_from(next(iter(sync_dir.glob("*.json"))))
        assert loaded.name == "Party Mix"
        assert loaded.description == "Dancefloor bangers"

    def test_create_json(self, sync_dir):
        """--json prints the playlist details including the file path."""
        result = runner.invoke(app, ["sync", "create", "Party Mix", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["name"] == "Party Mix"
        assert Path(payload["path"]).exists()
        loaded = SyncedPlaylist.load_from(payload["path"])
        assert str(loaded.id) == payload["id"]

    def test_create_duplicate_name_warns(self, sync_dir, synced):
        """Creating a playlist with an existing name logs a warning."""
        with patch("plistsync.cli.commands.sync.log.warning") as mock_warning:
            result = runner.invoke(app, ["sync", "create", "Party Mix"])

        assert result.exit_code == 0
        assert any(
            "already exists" in str(call.args[0])
            for call in mock_warning.call_args_list
        )
        assert len(list(sync_dir.glob("*.json"))) == 2

    def test_create_skips_unreadable_files(self, sync_dir):
        """create ignores corrupt JSON files while checking for name clashes."""
        _create_synced_playlist(sync_dir, name="Other Mix")
        (sync_dir / "broken.json").write_text("{not valid json", encoding="utf-8")

        with patch("plistsync.cli.commands.sync.log.warning") as mock_warning:
            result = runner.invoke(app, ["sync", "create", "Party Mix"])

        assert result.exit_code == 0
        assert any(
            "Skipping unreadable sync file" in str(call.args[0])
            for call in mock_warning.call_args_list
        )
        assert len(list(sync_dir.glob("*.json"))) == 3

    def test_sync_dir_creates_directory(self, tmp_path, monkeypatch):
        """The sync dir is created under the user config dir."""
        monkeypatch.setattr(
            "plistsync.cli.commands.sync.user_config_dir",
            lambda *args, **kwargs: str(tmp_path),
        )

        result = runner.invoke(app, ["sync", "create", "Party Mix"])

        assert result.exit_code == 0
        assert (tmp_path / "sync").is_dir()


class TestSyncRemove:
    """Test the ``plistsync sync remove`` command."""

    def test_remove_by_name(self, sync_dir, synced):
        """Removing by name deletes the matching JSON file."""
        result = runner.invoke(app, ["sync", "remove", "Party Mix", "--confirm"])

        assert result.exit_code == 0
        assert "Party Mix" in result.output
        assert not (sync_dir / f"{synced.id}.json").exists()
        assert list(sync_dir.glob("*.json")) == []

    def test_remove_by_id(self, sync_dir, synced):
        """Removing by raw ID deletes the matching JSON file."""
        result = runner.invoke(app, ["sync", "remove", str(synced.id), "-y"])

        assert result.exit_code == 0
        assert "Party Mix" in result.output
        assert not (sync_dir / f"{synced.id}.json").exists()

    def test_remove_keeps_unrelated_playlists(self, sync_dir):
        """Removing one playlist leaves the others untouched."""
        keep = _create_synced_playlist(sync_dir, name="Keep Me")
        drop = _create_synced_playlist(sync_dir, name="Drop Me")

        result = runner.invoke(app, ["sync", "remove", "Drop Me", "-y"])

        assert result.exit_code == 0
        assert not (sync_dir / f"{drop.id}.json").exists()
        assert (sync_dir / f"{keep.id}.json").exists()

    def test_remove_json_output(self, sync_dir):
        """--json prints the removed playlist's details as JSON."""
        playlist = _create_synced_playlist(
            sync_dir, name="Party Mix", description="Dancefloor bangers"
        )

        result = runner.invoke(
            app, ["sync", "remove", "Party Mix", "--json", "--confirm"]
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["id"] == str(playlist.id)
        assert payload["name"] == "Party Mix"
        assert payload["description"] == "Dancefloor bangers"
        assert payload["path"] == str(sync_dir / f"{playlist.id}.json")
        assert payload["removed"] is True

    def test_remove_aborts_when_not_confirmed(self, sync_dir, synced):
        """Answering 'no' to the confirmation prompt aborts the removal."""
        result = runner.invoke(app, ["sync", "remove", "Party Mix"], input="n\n")

        assert result.exit_code == 1
        assert (sync_dir / f"{synced.id}.json").exists()

    def test_remove_confirms(self, sync_dir, synced):
        """Answering 'yes' to the prompt removes the playlist."""
        result = runner.invoke(app, ["sync", "remove", "Party Mix"], input="y\n")

        assert result.exit_code == 0
        assert not (sync_dir / f"{synced.id}.json").exists()

    def test_remove_not_found(self, sync_dir):
        """Removing an unknown playlist fails with a non-zero exit code."""
        _create_synced_playlist(sync_dir, name="Existing")

        result = runner.invoke(app, ["sync", "remove", "Missing"])

        assert result.exit_code == 2
        assert "No synced playlist found matching" in result.output
        # Nothing was deleted.
        assert len(list(sync_dir.glob("*.json"))) == 1

    def test_remove_ambiguous_name(self, sync_dir):
        """Duplicate names are rejected; the ID must be used instead."""
        _create_synced_playlist(sync_dir, name="Party Mix")
        _create_synced_playlist(sync_dir, name="Party Mix")

        result = runner.invoke(app, ["sync", "remove", "Party Mix"])

        assert result.exit_code == 2
        assert "Multiple synced playlists match" in result.output
        assert len(list(sync_dir.glob("*.json"))) == 2


class TestSyncList:
    """Test the ``plistsync sync list`` command."""

    def test_list_table(self, sync_dir):
        """Listing shows a table with name, ID, description, and registered column."""
        playlist = _create_synced_playlist(
            sync_dir, name="Party Mix", description="Dancefloor bangers"
        )

        result = runner.invoke(app, ["sync", "list"])

        assert result.exit_code == 0
        assert "Synced playlists" in result.output
        assert "Party Mix" in result.output
        # The ID column may be truncated with an ellipsis in narrow terminals.
        assert str(playlist.id)[:8] in result.output
        assert "Dancefloor bangers" in result.output
        assert "Registered" in result.output

    def test_list_json(self, sync_dir):
        """--json prints the playlists as a JSON array."""
        playlist = _create_synced_playlist(
            sync_dir, name="Party Mix", description="Dancefloor bangers"
        )

        result = runner.invoke(app, ["sync", "list", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload == [
            {
                "id": str(playlist.id),
                "name": "Party Mix",
                "description": "Dancefloor bangers",
                "registered": 0,
            }
        ]

    def test_list_registered_count(self, synced):
        """The registered-playlists count reflects linked playlists."""
        playlist = SyncedPlaylist(name="Party Mix")
        playlist._linked_playlists[1] = MagicMock()
        playlist._linked_playlists[2] = MagicMock()

        with patch(
            "plistsync.cli.commands.sync.SyncedPlaylist.load_from",
            return_value=playlist,
        ):
            result = runner.invoke(app, ["sync", "list", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload[0]["registered"] == 2

    def test_iter_all_skips_unreadable_files(self, sync_dir, synced):
        """Corrupt JSON files are skipped instead of breaking commands."""
        (sync_dir / "broken.json").write_text("{not valid json", encoding="utf-8")

        result = runner.invoke(app, ["sync", "list"])

        assert result.exit_code == 0
        assert "Party Mix" in result.output

    def test_list_empty(self, sync_dir):
        """Listing without playlists prints a hint."""
        result = runner.invoke(app, ["sync", "list"])

        assert result.exit_code == 0
        assert "No synced playlists registered yet" in result.output


class TestSyncRegister:
    """Test the ``plistsync sync register`` command."""

    @staticmethod
    def _patch_service():
        """Patch ServiceLoader.all with a stub resolving ``test:playlist:`` ids."""
        from plistsync.services import ServiceLoader

        return patch.object(ServiceLoader, "all", return_value={"test": _FakeService()})

    def test_register_links_playlist(self, sync_dir, synced):
        """register links a service playlist to the synced playlist."""
        with self._patch_service():
            result = runner.invoke(
                app,
                ["sync", "register", "Party Mix", "test:playlist:abc123"],
            )

        assert result.exit_code == 0
        assert "Registered playlist" in result.output
        # The original playlist name is shown (it adopts the synced name later).
        assert "Chill Vibes" in result.output
        assert "test:playlist:abc123" in result.output
        payload = json.loads((sync_dir / f"{synced.id}.json").read_text())
        assert payload["linked_playlists"] == {"1": "test:playlist:abc123"}

    def test_register_json_output(self, synced):
        """--json prints the registration details."""
        with self._patch_service():
            result = runner.invoke(
                app,
                ["sync", "register", "Party Mix", "test:playlist:abc123", "--json"],
            )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["id"] == str(synced.id)
        assert payload["name"] == "Party Mix"
        assert payload["playlist"] == "test:playlist:abc123"
        assert payload["tracks"] == 0

    def test_register_synced_not_found(self, sync_dir):
        """Registering with an unknown synced playlist fails."""
        result = runner.invoke(
            app, ["sync", "register", "does-not-exist", "test:playlist:abc123"]
        )

        assert result.exit_code == 2
        assert "No synced playlist found matching" in result.output

    def test_register_unresolvable_playlist(self, synced):
        """An unresolvable playlist reference is rejected."""
        result = runner.invoke(
            app, ["sync", "register", str(synced.id), "not-a-playlist"]
        )

        assert result.exit_code == 2
        assert "No service could parse playlist" in result.output

    def test_register_ambiguous_playlist(self, synced):
        """A playlist reference parseable by several services is rejected."""
        from plistsync.services import ServiceLoader

        services = {"test": _FakeService(), "other": _FakeService()}
        with patch.object(ServiceLoader, "all", return_value=services):
            result = runner.invoke(
                app, ["sync", "register", "Party Mix", "test:playlist:abc123"]
            )

        assert result.exit_code == 2
        assert "Multiple services could parse playlist" in result.output

    def test_register_service_without_library(self, synced):
        """A service without library support is rejected with an error."""
        from plistsync.services import ServiceLoader

        class _NoLibraryService(_FakeService):
            def library(self):
                return None

        with patch.object(
            ServiceLoader, "all", return_value={"test": _NoLibraryService()}
        ):
            result = runner.invoke(
                app, ["sync", "register", "Party Mix", "test:playlist:abc123"]
            )

        assert result.exit_code == 1
        assert isinstance(result.exception, ValueError)
        assert "does not support library operations" in str(result.exception)


class TestSyncShow:
    """Test the ``plistsync sync show`` command."""

    def _synced_with_linked(self) -> SyncedPlaylist:
        """Build a SyncedPlaylist with an internal collection and one linked playlist."""
        track_a = OfflineTrack(
            info={"title": "Song A", "artists": ["Artist One"]},
            ids={ISRC("USRC17607839")},
        )
        track_b = OfflineTrack(
            info={"title": "Song B", "artists": ["Artist Two"]},
            ids={ISRC("USRC17607840")},
        )
        linked = _make_service_playlist(
            _FakePlaylistID("abc123"), "Chill Vibes", tracks=[track_b]
        )

        synced = SyncedPlaylist(name="Party Mix")
        synced._linked_playlists[1] = linked
        synced._fugue.insert(0, _TrackLink(track=track_a, playlists=set()))
        synced._fugue.insert(1, _TrackLink(track=track_b, playlists={linked.id}))
        return synced

    def test_show_track_matrix(self, sync_dir):
        """The matrix shows tracks with per-playlist presence."""
        _create_synced_playlist(sync_dir, name="Party Mix")
        synced = self._synced_with_linked()

        with patch(
            "plistsync.cli.commands.sync.SyncedPlaylist.load_from",
            return_value=synced,
        ):
            result = runner.invoke(app, ["sync", "show", str(synced.id)])

        assert result.exit_code == 0
        assert "Song A" in result.output
        assert "Artist One" in result.output
        assert "Song B" in result.output
        assert "Artist Two" in result.output
        # Linked playlists are shown as "service (serial)".
        assert "test" in result.output
        assert "test:playlist:abc123" in result.output
        assert "✓" in result.output
        assert "✗" in result.output

    def test_show_by_name(self, sync_dir):
        """show accepts a playlist name instead of an ID."""
        _create_synced_playlist(sync_dir, name="Party Mix")
        synced = self._synced_with_linked()

        with patch(
            "plistsync.cli.commands.sync.SyncedPlaylist.load_from",
            return_value=synced,
        ):
            result = runner.invoke(app, ["sync", "show", "Party Mix"])

        assert result.exit_code == 0
        assert "Song A" in result.output

    def test_show_not_found(self, sync_dir):
        """An unknown name or ID fails with a non-zero exit code."""
        result = runner.invoke(app, ["sync", "show", "Missing"])

        assert result.exit_code == 2
        assert "No synced playlist found matching" in result.output

    def test_show_empty(self, sync_dir):
        """A synced playlist without tracks renders an empty matrix."""
        _create_synced_playlist(sync_dir, name="Party Mix")
        synced = SyncedPlaylist(name="Party Mix")

        with patch(
            "plistsync.cli.commands.sync.SyncedPlaylist.load_from",
            return_value=synced,
        ):
            result = runner.invoke(app, ["sync", "show", str(synced.id)])

        assert result.exit_code == 0
        assert "Synced playlist" in result.output
        assert "Party Mix" in result.output
        assert "✓" not in result.output
        assert "✗" not in result.output


class TestSyncRun:
    """Test the ``plistsync sync run`` command."""

    def test_run_by_name(self, sync_dir, synced):
        """run synchronises the named playlist and saves its state."""
        with patch.object(SyncedPlaylist, "sync") as mock_sync:
            result = runner.invoke(app, ["sync", "run", "Party Mix"])

        assert result.exit_code == 0
        mock_sync.assert_called_once()
        assert (sync_dir / f"{synced.id}.json").exists()

    def test_run_by_id(self, sync_dir, synced):
        """run accepts an ID instead of a name."""
        with patch.object(SyncedPlaylist, "sync") as mock_sync:
            result = runner.invoke(app, ["sync", "run", str(synced.id)])

        assert result.exit_code == 0
        mock_sync.assert_called_once()

    def test_run_multiple(self, sync_dir):
        """run synchronises several playlists in one invocation."""
        _create_synced_playlist(sync_dir, name="Party Mix")
        _create_synced_playlist(sync_dir, name="Holiday Hits")

        with patch.object(SyncedPlaylist, "sync") as mock_sync:
            result = runner.invoke(app, ["sync", "run", "Party Mix", "Holiday Hits"])

        assert result.exit_code == 0
        assert mock_sync.call_count == 2

    def test_run_all(self, sync_dir):
        """run without arguments synchronises every synced playlist."""
        _create_synced_playlist(sync_dir, name="Party Mix")
        _create_synced_playlist(sync_dir, name="Holiday Hits")

        with patch.object(SyncedPlaylist, "sync") as mock_sync:
            result = runner.invoke(app, ["sync", "run"])

        assert result.exit_code == 0
        assert mock_sync.call_count == 2

    def test_run_not_found(self, sync_dir):
        """run fails when the playlist does not exist."""
        result = runner.invoke(app, ["sync", "run", "Missing"])

        assert result.exit_code == 2
        assert "No synced playlist found matching" in result.output

    def test_run_logs_completion(self, synced):
        """run logs the completion message."""
        with patch("plistsync.cli.commands.sync.log.info") as mock_info:
            result = runner.invoke(app, ["sync", "run", "Party Mix"])

        assert result.exit_code == 0
        mock_info.assert_any_call("All synchronisations completed.")


class TestSyncCompletion:
    """Test the ``_autocomplete_name_or_id`` shell-completion callback."""

    def _complete(self, incomplete: str) -> list[str]:
        from plistsync.cli.commands.sync import _autocomplete_name_or_id

        return list(_autocomplete_name_or_id(incomplete))

    def test_completes_by_name_prefix(self, synced):
        """Typing a name prefix suggests the name and the ID."""
        assert self._complete("Party") == ["Party Mix", str(synced.id)]

    def test_completes_by_id_prefix(self, synced):
        """Typing an ID prefix suggests the name and the ID."""
        assert self._complete(str(synced.id)[:8]) == ["Party Mix", str(synced.id)]

    def test_empty_incomplete_suggests_everything(self, synced):
        """An empty prefix suggests every playlist's name and ID."""
        assert self._complete("") == ["Party Mix", str(synced.id)]

    def test_no_matches(self, synced):
        """No prefix match yields no completions."""
        assert self._complete("zzz") == []
