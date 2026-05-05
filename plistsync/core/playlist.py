"""Playlist collections.

This module defines the `PlaylistCollection` class, which represents a collection of
tracks as a playlist. To support playlist management on different platforms, we define a
number of protocols which each service-specific implementation may adhere to.

The main idea here is to have an abstraction to allow updates/edit playlist in a generic
way.

Usage Example:
--------------
Create a custom playlist collection by subclassing `PlaylistCollection` and implementing
the required methods.

.. code-block:: python

    class MyPlaylistCollection(PlaylistCollection):
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Hashable, Sequence
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from typing import ClassVar, Generic, Self, TypedDict

from typing_extensions import TypeVar

from .collection import Collection, Library, TrackStream
from .diff import DeleteOp, InsertOp, MoveOp, batch_consecutive, list_diff
from .track import OfflineTrack, Track


@dataclass(frozen=True)
class PlaylistID(ABC):
    """Immutable base for service-specific playlist identifiers.

    Should contain a unique identifier for a playlist
    within a specific service.
    """

    service_name: ClassVar[str]

    @classmethod
    @abstractmethod
    def parse(cls, value: str) -> Self:
        """Parse from user input (URL, URI, or raw id)."""
        raise NotImplementedError

    @abstractmethod
    def serialize(self) -> str:
        """Canonical service-prefixed representation."""
        raise NotImplementedError

    def __str__(self) -> str:
        """For domain specific usage"""
        return self.serialize()


class PlaylistInfo(TypedDict, total=False):
    """Unified metadata for a playlist, independent of any specific service.

    This object captures descriptive information about a playlist that
    is consistent across services or platforms.

    Unlike `PlaylistIDs`, which uniquely identify a playlist, `PlaylistInfo`
    contains human-readable metadata such as the playlist's name, description,
    and other relevant attributes.

    Fields may be partially populated depending on the source service.
    """

    name: str
    """The display name of the playlist."""

    description: str | None
    """Optional textual description of the playlist."""

    # TODO: add more unified fields like owner, date_created etc


T = TypeVar("T", bound=Track)


@dataclass(slots=True, frozen=True)
class Snapshot(Generic[T]):
    """Represents a snapshot of a playlist's state."""

    name: str
    description: str | None
    tracks: list[T]


class Playlist(Generic[T], Collection[T], TrackStream[T], ABC):
    """Abstract base class defining the core playlist interface.

    This class provides a minimal protocol for playlist-like objects without
    assuming any specific storage model (local files, remote APIs, in-memory, etc.).
    It defines the essential properties that all playlists must support:
    metadata access (`info`, `name`, `description`), track list access (`tracks`),
    and unique identifiers (`ids`).

    Concrete implementations should subclass this and implement the abstract
    properties. Use this as a base when building playlist abstractions for
    specific music services or local file formats.
    """

    # --------------------------- Required (protocol) ---------------------------- #

    @property
    @abstractmethod
    def info(self) -> PlaylistInfo:
        """Get this playlist's information."""
        ...

    @info.setter
    @abstractmethod
    def info(self, value: PlaylistInfo):
        """Set playlist information."""
        ...

    @property
    @abstractmethod
    def tracks(self) -> list[T]:
        """Get the list of tracks in the playlist."""
        ...

    @tracks.setter
    @abstractmethod
    def tracks(self, value: list[T]) -> None:
        """Set the list of tracks in the playlist."""
        ...

    @property
    @abstractmethod
    def id(self) -> PlaylistID:
        """Get the unique identifiers of the playlist."""
        ...

    # ----------------------------- Usability helpers ---------------------------- #

    @property
    def name(self) -> str:
        """The name of the playlist."""
        name = self.info.get("name")
        if name is None:
            raise ValueError("Playlists has no name!")
        return name

    @name.setter
    def name(self, value: str):
        """Set the name of the playlist."""
        info = deepcopy(self.info)
        info.update({"name": value})
        self.info = info

    @property
    def description(self) -> str | None:
        """The description of the playlist, if available."""
        return self.info.get("description")

    @description.setter
    def description(self, value: str | None) -> None:
        """Set playlist description on remote service."""
        info = deepcopy(self.info)
        info.update({"description": value})
        self.info = info

    def get_snapshot(self) -> Snapshot[T]:
        """Get a snapshot of the current state of the playlist."""
        return Snapshot(
            name=self.name,
            description=self.description,
            tracks=deepcopy(self.tracks),
        )

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r}, tracks={len(self)})"

    def __len__(self) -> int:
        return len(self.tracks)


class OfflinePlaylist(Playlist[OfflineTrack]):
    """A offline (in memory) playlist with no service synchronization.

    This class provides a concrete implementation of `Playlist` for
    managing playlists in memory without any connection to online music services.
    It is useful for testing, temporary playlist manipulation, or as an intermediate
    representation during playlist conversions.
    """

    _tracks: list[OfflineTrack]
    _info: PlaylistInfo
    _ids: PlaylistIDs

    def __init__(
        self,
        name: str,
        description: str | None = None,
        tracks: Sequence[OfflineTrack] | None = None,
    ) -> None:
        self._info = PlaylistInfo(
            name=name,
            description=description,
        )
        self._tracks = list(tracks or [])
        self._ids = PlaylistIDs()

    @property
    def ids(self) -> PlaylistIDs:
        return self._ids

    @property
    def info(self) -> PlaylistInfo:
        return self._info

    @info.setter
    def info(self, value: PlaylistInfo) -> None:
        self._info = value

    @property
    def tracks(self) -> list[OfflineTrack]:
        return self._tracks

    @tracks.setter
    def tracks(self, value: list[OfflineTrack]) -> None:
        self._tracks = value


class ServicePlaylist(Generic[T], Playlist[T], ABC):
    """Abstract base class for playlists synchronized with music services.

    Extends `Playlist` with methods to manage the lifecycle and state synchronization
    between a in memory representation and its service counterpart (e.g., on Spotify,
    Tidal). By convention, every `ServicePlaylist` instance corresponds to an existing
    "remote" playlist, and has a library and/or api associated. If the "remote" playlist
    is deleted, the specific "ServicePlaylist" instance should be discarded in favor of
    an `OfflinePlaylist` to retain the data.

    Provides two synchronization strategies:
      - `edit()` - transactional edits with automatic local rollback
      - `update()` - bulk update by comparing remote and local snapshots
    """

    library: Library[Track, Self]

    # --------------------------- Required (protocol) ---------------------------- #

    @abstractmethod
    def _remote_delete(self):
        """Delete the playlist on the service."""
        ...

    @abstractmethod
    def _remote_commit(self, before: Snapshot[T], after: Snapshot[T]) -> None:
        """Write the current playlist state to its online version."""
        ...

    # ----------------------------- Usability helpers ---------------------------- #

    def delete(self) -> OfflinePlaylist:
        """Delete the playlist from the remote service and return an offline copy.

        Removes the playlist from the connected remote service and returns a new
        `OfflinePlaylist` instance containing the playlist's metadata and tracks
        as they existed before deletion. This allows the data to be preserved or
        migrated elsewhere even after the remote resource is gone.
        """
        offline = OfflinePlaylist(
            self.name,
            self.description,
            [OfflineTrack.from_track(t) for t in self.tracks],
        )
        self._remote_delete()
        return offline

    def update(self):
        """Update the playlist on the remote service.

        Creates the playlist if it doesn't exist, or updates it to match the
        current local state.

        Performance Note
        ----------------
        Less efficient than `edit()` for changes, as it retrieves the full remote state
        before committing. Use the `edit()` context manager for better
        performance/fewer API requests.
        """
        truth = self.library.get_playlist_or_raise(ids=self.ids)
        snapshot_before = truth.get_snapshot()
        snapshot_after = self.get_snapshot()
        self._remote_commit(snapshot_before, snapshot_after)

    @contextmanager
    def edit(self):
        """Context manager for transactional playlist edits with automatic rollback.

        Enables safe modifications to a remote playlist by capturing the current
        state before entering the block. On successful exit, commits the changes
        to the remote service. If an exception occurs, restores the local state
        to its pre-edit condition.

        Usage
        -----
        .. code-block:: python

            with playlist.edit():
                playlist.tracks.append(new_track)
                playlist.name = "Updated Name"
            # Changes committed to remote on success
            # Local state restored on error (remote rollback not implemented)
        """
        # Main use case is for roll backs of IncrementalPlaylistCollection, where
        # individual remote operations might fail.
        # But we want a consistent interface, therefore we define it in this base class,
        # even though roll-backs are an uncommon requirement for local changes.

        snapshot_before = self.get_snapshot()
        try:
            yield
            snapshot_after = self.get_snapshot()
            self._remote_commit(snapshot_before, snapshot_after)
        except Exception:
            self.tracks = snapshot_before.tracks
            self.name = snapshot_before.name
            self.description = snapshot_before.description
            # TODO: maybe we want a online rollback too
            raise


class MultiRequestServicePlaylist(ServicePlaylist[T], ABC):
    """Playlist for APIs where modifications have to be split into mulitple requests.

    Subclass this and implement:
        - _remote_insert_track()     - Add one or multiple track(s)
        - _remote_delete_track()     - Remove one or multiple track(s)
        - _remote_update_metadata()  - Update name/description
        - _track_key()               - Stable identifier for track equality

    This base class handles diff computation, batching consecutive operations,
    and rolling back on failure.
    It also translates the diff between two playlist states into the appropriate
    sequence of remote API calls.

    Use this when the service API needs multiple calls to set a playlist to
    a new state (Most services will need this. For example, adding tracks
    usually has a different endpoint than changing a playlist's description.)
    """

    def _remote_commit(self, before: Snapshot[T], after: Snapshot[T]) -> None:
        """Apply minimal remote operations to match after state from before.

        Computes the diff between before and after states, then translates
        each change into the appropriate sequence of remote API calls.
        Handles metadata updates (name, description) and track operations
        (insert, delete, move) with automatic rollback on failure.
        """
        new_name = after.name if before.name != after.name else None
        new_description = (
            after.description if before.description != after.description else None
        )

        if new_name is not None or new_description is not None:
            self._remote_update_metadata(new_name, new_description)

        operations = list_diff(before.tracks, after.tracks, hash_func=self._track_key)
        for batch in batch_consecutive(operations.iter()):
            # Batch is always nonempty batch of operation
            # including consecutive indexes
            # we can use them here without worry
            if isinstance(batch[0].op, InsertOp):
                self._remote_insert_track(
                    idx=batch[0].op.idx,
                    track=[step.op.item for step in batch],
                    tracks_before=batch[0].list_before,
                )
            elif isinstance(batch[0].op, DeleteOp):
                self._remote_delete_track(
                    idx=batch[0].op.idx,
                    track=[step.op.item for step in batch],
                    tracks_before=batch[0].list_before,
                )
            elif isinstance(batch[0].op, MoveOp):
                # Multi moves at the same time are quite ambiguous
                for step in batch:
                    self._remote_move_track(
                        old_idx=step.op.old_idx,  # type: ignore[attr-defined]
                        new_idx=step.op.new_idx,  # type: ignore[attr-defined]
                        track=step.op.item,
                        tracks_before=step.list_before,
                    )

    @abstractmethod
    def _remote_insert_track(
        self,
        idx: int,
        track: T | list[T],
        tracks_before: list[T],
    ) -> None:
        """Insert track at index on remote service.

        Parameters
        ----------
        idx : int
            Zero-based insertion index (0 <= idx <= current length)
        track : T | list[T]
            Track object(s) to insert
        tracks_before : list[T]
            List of all tracks in the playlist insert is applied.
            We need this argument because the apis of some services do not use indices
            to reference tracks in the playlist (therefore we need this as a helper
            to work with old_ and nex_idx consistently across services)
        """
        ...

    @abstractmethod
    def _remote_delete_track(
        self,
        idx: int,
        track: T | list[T],
        tracks_before: list[T],
    ) -> None:
        """Delete track at index from remote service.

        Parameters
        ----------
        idx : int
            Zero-based index of track to delete
        track : T | list[T]
            Track object(s) to delete
        tracks_before : list[T]
            List of all tracks in the playlist before deletion.
            We need this argument because the apis of some services do not use indices
            to reference tracks in the playlist (therefore we need this as a helper
            to work with old_ and nex_idx consistently across services)
        """
        ...

    def _remote_move_track(
        self,
        old_idx: int,
        new_idx: int,
        track: T,
        tracks_before: list[T],
    ) -> None:
        """Move track from old_idx to new_idx remotely.

        Does not support batch operations, since it would be unclear in which order
        moves should be undertaken.

        Default: delete then insert. Subclasses may optimize.

        Parameters
        ----------
        old_idx : int
            Source index
        new_idx : int
            Destination index
        track : T
            Track being moved
        tracks_before : list[T]
            List of all tracks in the playlist before move was applied.
            We need this argument because the apis of some services do not use indices
            to reference tracks in the playlist (therefore we need this as a helper
            to work with old_ and nex_idx consistently across services)
        """
        # Remove from old position
        self._remote_delete_track(
            idx=old_idx,
            track=track,
            tracks_before=tracks_before,
        )
        tracks_before.pop(old_idx)
        # Insert at new position (note: new_idx may have shifted due to pop)
        adjusted_new_idx = new_idx if new_idx > old_idx else new_idx
        self._remote_insert_track(
            idx=adjusted_new_idx,
            track=track,
            tracks_before=tracks_before,
        )
        tracks_before.insert(adjusted_new_idx, track)

    @abstractmethod
    def _remote_update_metadata(
        self, new_name: str | None = None, new_description: str | None = None
    ) -> None:
        """Update playlist metadata on remote service.

        Only changed fields passed (None = no change).

        Parameters
        ----------
        new_name : str, optional
            New name
        new_description : str, optional
            New description
        """

    @staticmethod
    @abstractmethod
    def _track_key(track: T) -> Hashable:
        """Return stable track identifier for equality comparisons.

        Used by list_diff() to match tracks between snapshots. Must be consistent
        across service lifetime (track ID, URI, etc).
        """
        ...
