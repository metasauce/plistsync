from __future__ import annotations

import bisect
from abc import ABC
from collections import Counter, defaultdict
from collections.abc import Callable, Hashable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

T = TypeVar("T")


@dataclass(slots=True, frozen=True)
class BaseOp(Generic[T], ABC):
    """Base class for all diff operations."""

    item: T
    """The item involved in the operation."""


@dataclass(slots=True, frozen=True)
class MoveOp(BaseOp[T]):
    """Represents a move operation in a list diff."""

    old_idx: int
    """The index of the item in the current (live) list before the move."""

    new_idx: int
    """The target index in the live list after the move."""


@dataclass(slots=True, frozen=True)
class InsertOp(BaseOp[T]):
    """Represents an insertion operation in a list diff."""

    idx: int
    """Live index at which the item should be inserted."""


@dataclass(slots=True, frozen=True)
class DeleteOp(BaseOp[T]):
    """Represents a deletion operation in a list diff."""

    idx: int
    """Live index of the item to delete."""


Op: TypeAlias = BaseOp[T]


@dataclass(slots=True, frozen=True)
class Step(Generic[T]):
    """Represents a single operation applied to a list."""

    op: Op[T]
    """The single operation to apply."""

    list_before: list[T]
    """The list state before this operation was applied."""


Ops: TypeAlias = MoveOp[T] | InsertOp[T] | DeleteOp[T]


@dataclass
class Operations(Generic[T]):
    """Container for a sequence of list diff operations."""

    ops: list[Ops[T]]
    """List of operations to transform old_list into the target list."""
    old_list: list[T]
    """The original list before applying operations."""

    def iter(self) -> Iterator[Step[T]]:
        """Iterate operations as Step objects."""
        # Yield each operation individually
        working_list = self.old_list.copy()
        for op in self.ops:
            list_before = working_list.copy()
            if self._apply_op_to_list(op, working_list):
                yield Step(op=op, list_before=list_before)

    def _apply_op_to_list(self, op: Ops[T], working_list: list[T]) -> bool:
        """Apply operation to target list, returns whether operation was applied."""
        if isinstance(op, MoveOp):
            try:
                current_idx = next(
                    i for i, v in enumerate(working_list) if v is op.item
                )
            except StopIteration:
                return False  # already deleted
            if current_idx == op.new_idx:
                return False  # already at target

            val = working_list.pop(current_idx)
            working_list.insert(op.new_idx, val)

        elif isinstance(op, InsertOp):
            if op.idx < len(working_list) and working_list[op.idx] is op.item:
                return False  # already inserted
            working_list.insert(op.idx, op.item)

        elif isinstance(op, DeleteOp):
            try:
                current_idx = next(
                    i for i, v in enumerate(working_list) if v is op.item
                )
            except StopIteration:
                return False  # already deleted
            working_list.pop(current_idx)

        return True

    def __getitem__(self, index: int) -> Op[T]:
        return self.ops[index]


def batch_consecutive(
    ops: Iterable[Step[T]],
) -> Iterator[list[Step[T]]]:
    """
    Yield batches of consecutive operations of the same type.

    - Consecutive inserts -> single batch
    - Non-consecutive inserts -> separate batches
    - Consecutive deletes -> single batch
    - Different types -> separate batches
    - Moves -> each in own batch

    Note:
    This is optimized for common api support, e.g. spotify and tidal only support
    batch operations for consecutive indices
    """
    ops = list(ops)
    if not ops:
        return
    batch = [ops[0]]
    for step in ops[1:]:
        prev_op = batch[-1].op
        curr_op = step.op

        # Different type -> new batch
        if type(prev_op) is not type(curr_op):
            yield batch
            batch = [step]
            continue

        # Check consecutiveness
        is_consecutive = False
        if isinstance(prev_op, InsertOp) and isinstance(curr_op, InsertOp):
            is_consecutive = curr_op.idx == prev_op.idx + 1
        elif isinstance(prev_op, DeleteOp) and isinstance(curr_op, DeleteOp):
            is_consecutive = curr_op.idx == prev_op.idx - 1

        if is_consecutive:
            batch.append(step)
        else:
            yield batch
            batch = [step]

    if batch:
        yield batch


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
        ops.append(DeleteOp(item=old[idx], idx=idx))

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
                    MoveOp(
                        old_idx=matched_old_idx,
                        new_idx=target_idx,
                        item=live_list[matched_old_idx],
                    )
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
            ops.append(InsertOp(idx=target_idx, item=target_item))
            live_list.insert(target_idx, target_item)
            # shift unmatched indices >= target_idx
            shift_indices(unmatched_old_indices, target_idx, +1)
            for lst in hash_to_indices.values():
                shift_indices(lst, target_idx, +1)
    return Operations(ops, list(old))
