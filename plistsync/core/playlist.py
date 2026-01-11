"""Playlist collections.

This module defines the `PlaylistCollection` class, which represents a collection of tracks
as a playlist. To support playlist management on different platforms, we define a number of
protocols which each service-specific implementation may adhere to.

The main idea here is to have an abstraction to allow updates/edit playlist in a generic way.

Usage Example:
--------------
Create a custom playlist collection by subclassing `PlaylistCollection` and implementing the
required methods.

.. code-block:: python

    class MyPlaylistCollection(PlaylistCollection):


"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import (
    Callable,
    Generic,
    Iterator,
    Literal,
)

from .collection import Collection, TrackStream, TypeVar
from .track import Track

T = TypeVar("T", bound=Track)


@dataclass
class Snapshot(Generic[T]):
    """Represents a snapshot of a playlist's state."""

    name: str | None
    description: str | None
    tracks: list[T]

    def copy(self) -> Snapshot[T]:
        """Create a deep copy of the snapshot."""
        return Snapshot(
            name=self.name,
            description=self.description,
            tracks=deepcopy(self.tracks),
        )


OPCODE = tuple[Literal["replace", "delete", "insert", "equal"], int, int, int, int]


@dataclass
class PlaylistChanges(Generic[T]):
    """Represents changes to be made to a single playlist's metadata."""

    snapshot_before: Snapshot[T]
    snapshot_after: Snapshot[T]

    def new_name(self) -> str | None:
        """Get the new name if it has changed, otherwise None."""
        if self.snapshot_before.name != self.snapshot_after.name:
            return self.snapshot_after.name
        return None

    def new_description(self) -> str | None:
        """Get the new description if it has changed, otherwise None."""
        if self.snapshot_before.description != self.snapshot_after.description:
            return self.snapshot_after.description
        return None

    def track_operations(self, eq_function: Callable[[T], str]) -> list[OPCODE]:
        """Get the list of operations to transform the original track list.

        To apply these operations, use the reverse of the operations to omit
        index shifting issues.
        """
        sm = SequenceMatcher(
            a=list(map(eq_function, self.snapshot_before.tracks)),
            b=list(map(eq_function, self.snapshot_after.tracks)),
        )
        return sm.get_opcodes()


class PlaylistCollection(Collection, TrackStream[T], ABC):
    """Represents a collection of tracks in a playlist.

    This class serves as a base for playlist collections across diverse services.
    It provides a framework for managing tracks within a playlist, allowing each service
    to implement its specifics.
    """

    _tracks: list[T]

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the playlist."""
        ...

    @property
    def description(self) -> str | None:
        """The description of the playlist, if available."""
        return None

    @contextmanager
    def edit(self):
        # Get snapshot of current state
        snapshot_before = self.get_snapshot()
        yield
        snapshot_after = self.get_snapshot()
        changes = PlaylistChanges(snapshot_before, snapshot_after)
        self.apply_changes(changes)

    def get_snapshot(self) -> Snapshot[T]:
        """Get a snapshot of the current state of the playlist."""
        return Snapshot(
            name=self.name,
            description=self.description,
            tracks=deepcopy(self._tracks),
        )

    @abstractmethod
    def apply_changes(self, playlist_changes: PlaylistChanges[T]) -> None:
        """Apply the given changes to the playlist.

        This method should handle updating the playlist's metadata and tracks
        according to the provided `PlaylistChanges` object.
        """
        ...

    def __len__(self) -> int:
        return len(self._tracks)

    def __getitem__(self, index: int) -> T:
        return self._tracks[index]

    def __iter__(self) -> Iterator[T]:
        return iter(self._tracks)
