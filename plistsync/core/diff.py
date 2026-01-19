from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Hashable, Iterator
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


Ops: TypeAlias = InsertOp | DeleteOp | MoveOp


@dataclass
class Operations(Generic[T]):
    """Container for a sequence of list diff operations."""

    ops: list[InsertOp[T] | DeleteOp[T] | MoveOp[T]]
    """List of operations to transform old_list into the target list."""
    old_list: list[T]
    """The original list before applying operations."""

    def __iter__(self) -> Iterator[InsertOp | DeleteOp | MoveOp]:
        """Iterate operations, skipping redundant actions."""
        live_list = self.old_list[:]

        for op in self.ops:
            if isinstance(op, MoveOp):
                # Find the exact object to move
                try:
                    current_idx = next(
                        i for i, v in enumerate(live_list) if v is op.item
                    )
                except StopIteration:
                    continue  # already deleted
                if current_idx == op.new_idx:
                    continue  # already at target
                val = live_list.pop(current_idx)
                live_list.insert(op.new_idx, val)
                yield op

            elif isinstance(op, InsertOp):
                if op.idx < len(live_list) and live_list[op.idx] is op.item:
                    continue  # already inserted
                live_list.insert(op.idx, op.item)
                yield op

            elif isinstance(op, DeleteOp):
                # Find the item by identity
                try:
                    current_idx = next(
                        i for i, v in enumerate(live_list) if v is op.item
                    )
                except StopIteration:
                    continue  # already deleted
                live_list.pop(current_idx)
                yield op


def list_diff(
    old: list[T],
    new: list[T],
    eq_function: Callable[[T], Hashable],
) -> Operations[T]:
    """Compute minimal insert/delete/move operations between lists.

    Parameters
    ----------
    old : list[T]
        Original track list.
    new : list[T]
        Target track list.
    eq_function : Callable[[T], Hashable]
        Function that returns a hashable key for logical equality.

    Returns
    -------
    Operations[T]
        Minimal operations to transform old into new.
    """
    old_keys = [eq_function(t) for t in old]
    new_keys = [eq_function(t) for t in new]
    old_counts = Counter(old_keys)
    new_counts = Counter(new_keys)
    # Track items with original positions to handle duplicates
    live_list = old[:]
    ops: list[InsertOp[T] | DeleteOp[T] | MoveOp[T]] = []

    # Step 1: delete excess duplicates
    for idx in reversed(range(len(live_list))):
        if old_counts[old_keys[idx]] > new_counts.get(old_keys[idx], 0):
            ops.append(DeleteOp(idx, live_list[idx]))
            live_list.pop(idx)
            old_counts[old_keys[idx]] -= 1

    # Step 2: insert missing items
    current_counts = Counter([eq_function(t) for t in live_list])
    for idx, item in enumerate(new):
        key = eq_function(item)
        if current_counts.get(key, 0) == 0:
            ops.append(InsertOp(idx, item))
            live_list.insert(idx, item)
            current_counts[key] = 1
        else:
            current_counts[key] -= 1

    # Step 3: move remaining items to match target
    used_old_indices: set[int] = set()
    for target_idx, target_item in enumerate(new):
        key = eq_function(target_item)

        # Skip if this position is already correct
        if target_idx < len(live_list) and eq_function(live_list[target_idx]) == key:
            used_old_indices.add(target_idx)
            continue

        # Find the first unused old item matching the target key
        for old_idx, old_item in enumerate(live_list):
            if old_idx in used_old_indices:
                continue
            if eq_function(old_item) == key:
                # Found a match → move it
                if old_idx != target_idx:
                    ops.append(MoveOp(old_idx, target_idx, live_list[old_idx]))
                    val = live_list.pop(old_idx)
                    live_list.insert(target_idx, val)
                used_old_indices.add(target_idx)
                break

    return Operations(ops, old)
