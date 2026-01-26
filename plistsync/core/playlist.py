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
from collections.abc import Hashable
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from typing import Generic

from .collection import Collection, TrackStream, TypeVar
from .diff import DeleteOp, InsertOp, MoveOp, list_diff
from .track import Track

T = TypeVar("T", bound=Track)


@dataclass(slots=True, frozen=True)
class Snapshot(Generic[T]):
    """Represents a snapshot of a playlist's state."""

    name: str
    description: str | None
    tracks: list[T]


class PlaylistCollection(Collection, TrackStream[T], ABC):
    """Abstract base class for playlist collections across music services.

    Manages local track state and syncs changes to remote services via concrete
    subclasses. Supports transactional edits through the `edit()` context manager.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the playlist."""
        ...

    @name.setter
    @abstractmethod
    def name(self, value: str):
        """Set the name of the playlist."""
        ...

    @property
    def description(self) -> str | None:
        """The description of the playlist, if available."""
        return None

    @description.setter
    def description(self, value: str | None) -> None:
        """Set playlist description on remote service.

        Parameters
        ----------
        value : str or None
            New playlist description
        """
        return None

    # To get typing compatible with TrackStream
    _tracks: list[T]

    @property
    def tracks(self) -> list[T]:
        return self._tracks

    @tracks.setter
    def tracks(self, value: list[T]) -> None:
        self._tracks = value

    @contextmanager
    def edit(self):
        """Transactional playlist editor with automatic rollback.

        Captures snapshot before entering block. Applies diff to remote service
        on successful exit. Resets local state on error.
        """
        snapshot_before = self.get_snapshot()
        try:
            yield
            snapshot_after = self.get_snapshot()
            self._apply_diff(snapshot_before, snapshot_after)
        except Exception:
            self._tracks = snapshot_before.tracks
            self.name = snapshot_before.name
            self.description = snapshot_before.description
            # TODO: maybe we want a online rollback too
            raise

    def get_snapshot(self) -> Snapshot[T]:
        """Get a snapshot of the current state of the playlist."""
        return Snapshot(
            name=self.name,
            description=self.description,
            tracks=deepcopy(self._tracks),
        )

    @abstractmethod
    def _remote_insert_track(self, idx: int, track: T) -> None:
        """Insert track at index on remote service.

        Parameters
        ----------
        idx : int
            Zero-based insertion index (0 <= idx <= current length)
        track : T
            Track object to insert
        """
        ...

    @abstractmethod
    def _remote_delete_track(self, idx: int, track: T) -> None:
        """Delete track at index from remote service.

        Parameters
        ----------
        idx : int
            Zero-based index of track to delete
        track : T
            Track being deleted
        """
        ...

    def _remote_move_track(self, old_idx: int, new_idx: int, track: T) -> None:
        """Move track from old_idx to new_idx remotely.

        Default: delete then insert. Subclasses may optimize.

        Parameters
        ----------
        old_idx : int
            Source index
        new_idx : int
            Destination index
        track : T
            Track being moved
        """
        self._remote_delete_track(old_idx, track)
        self._remote_insert_track(new_idx, track)

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

    def _apply_diff(self, before: Snapshot[T], after: Snapshot[T]) -> None:
        """Apply minimal remote operations to match after state from before."""
        new_name = after.name if before.name != after.name else None
        new_description = (
            after.description if before.description != after.description else None
        )

        if new_name is not None or new_description is not None:
            self._remote_update_metadata(new_name, new_description)

        operations = list_diff(before.tracks, after.tracks, eq_function=self._track_key)
        for op in operations:
            if isinstance(op, InsertOp):
                self._remote_insert_track(op.idx, op.item)
            elif isinstance(op, DeleteOp):
                self._remote_delete_track(op.idx, op.item)
            elif isinstance(op, MoveOp):
                self._remote_move_track(op.old_idx, op.new_idx, op.item)

    @staticmethod
    @abstractmethod
    def _track_key(track: T) -> Hashable:
        """Return stable track identifier for equality comparisons.

        Used by list_diff() to match tracks between snapshots. Must be consistent
        across service lifetime (track ID, URI, etc).
        """
        ...
