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
from typing import Generic, TypedDict

from .collection import Collection, TrackStream, TypeVar
from .diff import DeleteOp, InsertOp, MoveOp, batch_consecutive, list_diff
from .track import Track


class PlaylistInfo(TypedDict, total=False):
    """Unified information a playlist can have, independent of its service."""

    name: str
    description: str | None
    # TODO: add more unified fields like owner, date_created etc


T = TypeVar("T", bound=Track)


@dataclass(slots=True, frozen=True)
class Snapshot(Generic[T]):
    """Represents a snapshot of a playlist's state."""

    name: str
    description: str | None
    tracks: list[T]


class PlaylistCollection(Generic[T], Collection[T], TrackStream[T], ABC):
    """Abstract base class for playlist collections across music services.

    Manages local track state and syncs changes to remote services via concrete
    subclasses. Supports transactional edits through the `edit()` context manager.
    """

    @property
    @abstractmethod
    def info(self) -> PlaylistInfo:
        """
        Get this playlist's information.

        Subclasses need return a reference, so that the setters for name
        etc. that are defined here, write back.
        """
        ...

    @info.setter
    @abstractmethod
    def info(self, value: PlaylistInfo):
        """Set playlist information."""
        ...

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

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r}, tracks={len(self)})"

    # -------------------------------- Tracks -------------------------------- #

    # Services can decide how to populate this helper
    _tracks: list[T] | None = None

    @property
    def tracks(self) -> list[T]:
        return self._tracks or []

    @tracks.setter
    def tracks(self, value: list[T]) -> None:
        self._tracks = value

    def __len__(self) -> int:
        """Use .tracks, but instances may override to use lookup data."""
        return len(self.tracks)

    # --------------------------- Remote Operations -------------------------- #

    @contextmanager
    def remote_edit(self):
        """Transactional playlist editor with automatic rollback.

        Only callable if the playlist is already linked.
        (.remote_associated == True)

        Captures snapshot before entering block. Applies diff to remote service
        on successful exit. Resets local state on error.
        """
        if not self.remote_associated:
            raise ValueError(
                "remote_edit() is only supported for playlists that have "
                "already been linked to a remote. Call remote_create() first or "
                "use remote_upsert()."
            )

        snapshot_before = self.get_snapshot()
        try:
            yield
            snapshot_after = self.get_snapshot()
            self._apply_diff(snapshot_before, snapshot_after)
        except Exception:
            self.tracks = snapshot_before.tracks
            self.name = snapshot_before.name
            self.description = snapshot_before.description
            # TODO: maybe we want a online rollback too
            raise

    def get_snapshot(self) -> Snapshot[T]:
        """Get a snapshot of the current state of the playlist."""
        return Snapshot(
            name=self.name,
            description=self.description,
            tracks=deepcopy(self.tracks),
        )

    def remote_create(self):
        """
        Create the playlist online.

        - if self.id: raise "is already associated online"
        - Depending on config (TODO config option DEBUG | INFO | WARN | Raise )
          Warn or Raise here if another playlist exists with the same name.
        """
        if self.remote_associated:
            raise ValueError("This playlist is already associated online.")

        return self._remote_create()

    def remote_delete(self):
        """Delete the playlist online."""
        if not self.remote_associated:
            raise ValueError("Can only delete playlists that are associated online.")

        return self._remote_delete()

    def remote_upsert(self):
        """
        Alternate usage pattern, besides playlist.remote_edit().

        - if does not exist, create_online()
        - if exists, then invoke remote_edit() wrapper.
        """
        raise NotImplementedError()

    def _apply_diff(self, before: Snapshot[T], after: Snapshot[T]) -> None:
        """Apply minimal remote operations to match after state from before."""
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
                # FIXME: Implement batched delete
                for step in batch:
                    self._remote_delete_track(
                        idx=step.op.idx,  # type: ignore[attr-defined]
                        track=step.op.item,
                        tracks_before=step.list_before,
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

    # ---------------------- Abstract remote operations ---------------------- #

    @property
    @abstractmethod
    def remote_associated(self) -> bool:
        """Indicate if the playlist is already linked to a remote (online) playlist."""
        ...

    @abstractmethod
    def _remote_create(self):
        """Create the playlist online. Checks are handled in the public version."""
        ...

    @abstractmethod
    def _remote_delete(self):
        """Delete the playlist online."""
        ...

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
        track: T,
        tracks_before: list[T],
    ) -> None:
        """Delete track at index from remote service.

        Parameters
        ----------
        idx : int
            Zero-based index of track to delete
        track : T
            Track being deleted
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
        self._remote_delete_track(old_idx, track, tracks_before)
        tracks_before.pop(old_idx)
        # Insert at new position (note: new_idx may have shifted due to pop)
        adjusted_new_idx = new_idx if new_idx > old_idx else new_idx
        self._remote_insert_track(adjusted_new_idx, track, tracks_before)
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
