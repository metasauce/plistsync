from __future__ import annotations

import bisect
from collections import Counter, defaultdict
from collections.abc import Callable, Hashable, Iterator, Sequence
from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

T = TypeVar("T")


@dataclass(slots=True, frozen=True)
class MoveOp(Generic[T]):
    """Represents a move operation in a list diff."""

    old_idx: int
    """The index of the item in the current (live) list before the move."""

    new_idx: int
    """The target index in the live list after the move."""

    item: T
    """The item to move."""


@dataclass(slots=True, frozen=True)
class InsertOp(Generic[T]):
    """Represents an insertion operation in a list diff."""

    idx: int
    """Live index at which the item should be inserted."""

    item: T
    """The item to insert into the list."""


@dataclass(slots=True, frozen=True)
class DeleteOp(Generic[T]):
    """Represents a deletion operation in a list diff."""

    idx: int
    """Live index of the item to delete."""

    item: T
    """The item to remove from the list."""


Ops: TypeAlias = InsertOp[T] | DeleteOp[T] | MoveOp[T]


@dataclass
class Operations(Generic[T]):
    """Container for a sequence of list diff operations."""

    ops: list[InsertOp[T] | DeleteOp[T] | MoveOp[T]]
    """List of operations to transform old_list into the target list."""
    old_list: list[T]
    """The original list before applying operations."""

    def __iter__(self) -> Iterator[InsertOp[T] | DeleteOp[T] | MoveOp[T]]:
        """Iterate operations with live list snapshots after each step."""
        self._live_list = self.old_list[:]

        for op in self.ops:
            if isinstance(op, MoveOp):
                # Find the exact object to move
                try:
                    current_idx = next(
                        i for i, v in enumerate(self._live_list) if v is op.item
                    )
                except StopIteration:
                    continue  # already deleted
                if current_idx == op.new_idx:
                    continue  # already at target
                val = self._live_list.pop(current_idx)
                self._live_list.insert(op.new_idx, val)
                yield op

            elif isinstance(op, InsertOp):
                if op.idx < len(self._live_list) and self._live_list[op.idx] is op.item:
                    continue  # already inserted
                self._live_list.insert(op.idx, op.item)
                yield op

            elif isinstance(op, DeleteOp):
                # Find the item by identity
                try:
                    current_idx = next(
                        i for i, v in enumerate(self._live_list[:]) if v is op.item
                    )
                except StopIteration:
                    continue  # already deleted
                self._live_list.pop(current_idx)
                yield op

    def __getitem__(self, index: int) -> InsertOp[T] | DeleteOp[T] | MoveOp[T]:
        return self.ops[index]

    @property
    def live_list(self) -> list[T]:
        """Current state of the list after all applied operations."""
        return getattr(self, "_live_list", self.old_list[:])


def list_diff(
    old: Sequence[T],
    new: Sequence[T],
    hash_func: Callable[[T], Hashable],
) -> Operations[T]:
    """Compute minimal insert/delete/move operations between lists.

    Parameters
    ----------
    old : list[T]
        Original track list.
    new : list[T]
        Target track list.
    hash_func : Callable[[T], Hashable]
        Function that returns a hashable key for logical equality.

    Returns
    -------
    Operations[T]
        Minimal operations to transform old into new.

    Qwirks
    ------
    Delete operations are always done first.

    """
    live_list: list[T] = []  # Keep track of the current operations

    old_keys = [hash_func(t) for t in old]
    new_keys = [hash_func(t) for t in new]
    new_counts = Counter(new_keys)

    # 1. Delete excess duplicates (keep first N occurrences of each key)
    indices_to_delete: list[int] = []
    keep_counts: dict[Hashable, int] = {}
    for idx, key in enumerate(old_keys):
        needed = new_counts.get(key, 0)
        kept = keep_counts.get(key, 0)
        if kept < needed:
            keep_counts[key] = kept + 1
        else:
            indices_to_delete.append(idx)

    # Build live_list with survivors (keep first N)
    del_set = set(indices_to_delete)
    for idx, item in enumerate(old):
        if idx not in del_set:
            live_list.append(item)

    # Create DeleteOps in reverse order (largest idx first)
    ops: list[InsertOp[T] | DeleteOp[T] | MoveOp[T]] = []
    for idx in reversed(indices_to_delete):
        ops.append(DeleteOp(idx, old[idx]))

    # Step 2: Match, insert missing items, and move to correct positions
    # Build mapping from hash to list of indices in live_list
    hash_to_indices: dict[Hashable, list[int]] = defaultdict(list)
    unmatched_old_indices = list(range(len(live_list)))
    for idx, item in enumerate(live_list):
        hash_to_indices[hash_func(item)].append(idx)

    def shift_indices(indices: list[int], threshold: int, delta: int) -> None:
        pos = bisect.bisect_left(indices, threshold)
        for i in range(pos, len(indices)):
            indices[i] += delta

    for target_idx, target_item in enumerate(new):
        hash = hash_func(target_item)
        matched_old_idx = None
        # Get first unmatched old item with matching key
        if hash_to_indices[hash]:
            matched_old_idx = hash_to_indices[hash].pop(0)
            # Remove matched index from unmatched_old_indices
            # Since unmatched_old_indices is sorted, we can use binary search
            pos = bisect.bisect_left(unmatched_old_indices, matched_old_idx)
            if (
                pos < len(unmatched_old_indices)
                and unmatched_old_indices[pos] == matched_old_idx
            ):
                del unmatched_old_indices[pos]
        if matched_old_idx is not None:
            # matched an existing item
            if matched_old_idx != target_idx:
                ops.append(
                    MoveOp(matched_old_idx, target_idx, live_list[matched_old_idx])
                )
                val = live_list.pop(matched_old_idx)
                live_list.insert(target_idx, val)
                # shift indices in unmatched_old_indices and key_to_indices
                # First, adjust for removal: indices > matched_old_idx decrease by 1
                shift_indices(unmatched_old_indices, matched_old_idx + 1, -1)
                for lst in hash_to_indices.values():
                    shift_indices(lst, matched_old_idx + 1, -1)
                # Then adjust for insertion: indices >= target_idx increase by 1
                shift_indices(unmatched_old_indices, target_idx, +1)
                for lst in hash_to_indices.values():
                    shift_indices(lst, target_idx, +1)
        else:
            # no matching old item -> insert
            ops.append(InsertOp(target_idx, target_item))
            live_list.insert(target_idx, target_item)
            # shift unmatched indices >= target_idx
            shift_indices(unmatched_old_indices, target_idx, +1)
            for lst in hash_to_indices.values():
                shift_indices(lst, target_idx, +1)

    return Operations(ops, list(old))
