from __future__ import annotations
import pytest

from plistsync.core.diff import (
    DeleteOp,
    InsertOp,
    MoveOp,
    Operations,
    batch_consecutive,
    list_diff,
    list_diff_eq,
)
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plistsync.core.diff import (
        Op,
    )
    from collections.abc import Callable


class TestPlaylistDiff:
    """Test suite for the playlist_diff function."""

    @pytest.mark.parametrize(
        "old, new, expected",
        [
            # Empty / Identical
            pytest.param([], [], [], id="empty_to_empty"),
            pytest.param(["A"], ["A"], [], id="single_identical"),
            pytest.param(["A", "B", "C"], ["A", "B", "C"], [], id="identical_lists"),
            # Inserts
            pytest.param([], ["A"], [InsertOp(idx=0, item="A")], id="insert_single"),
            pytest.param([], ["B", "B"], [InsertOp(idx=0, item="B"), InsertOp(idx=1, item="B")], id="insert_two_duplicates"),
            pytest.param(["A"], ["A", "A"], [InsertOp(idx=1, item="A")], id="insert_duplicate_after"),
            pytest.param(["A", "B", "C"], ["A", "B", "B", "C"], [InsertOp(idx=2, item="B")], id="insert_duplicate_in_middle"),
            # Deletes
            pytest.param(["A"], [], [DeleteOp(idx=0, item="A")], id="delete_single"),
            pytest.param(["A", "A"], ["A"], [DeleteOp(idx=1, item="A")], id="delete_duplicate"),
            pytest.param(["A", "B", "C"], ["A", "C"], [DeleteOp(idx=1, item="B")], id="delete_middle"),
            # Moves
            pytest.param(["A", "B", "C"], ["C", "A", "B"], [MoveOp(old_idx=2, new_idx=0, item="C")], id="move_last_to_front"),
            pytest.param(["A", "B", "C"], ["B", "A", "C"], [MoveOp(old_idx=1, new_idx=0, item="B")], id="move_second_to_front"),
            # Delete + inserts + Move
            pytest.param(["A", "B", "C"], ["X", "A", "C"], [DeleteOp(idx=1, item="B"), InsertOp(idx=0, item="X")], id="delete_middle_insert_front"),
            pytest.param(["A", "B", "C"], ["A", "X", "C"], [DeleteOp(idx=1, item="B"), InsertOp(idx=1, item="X")], id="delete_middle_insert_same_idx"),
            pytest.param(["A", "B", "C"], ["C", "B"], [DeleteOp(idx=0, item="A"),MoveOp(old_idx=1,new_idx=0,item='C')]),
            # Complex reorder
            pytest.param(
                ["A", "B", "C", "D"],
                ["B", "D", "A", "C"],
                [
                    MoveOp(old_idx=1, new_idx=0, item="B"),
                    MoveOp(old_idx=3, new_idx=1, item="D"),
                ],
                id="complex_reorder",
            ),
            # Full mix
            pytest.param(
                ["A", "B", "C", "D", "E", "F"],
                ["B", "G", "D", "A", "F", "H", "C"],
                [
                    DeleteOp(idx=4, item="E"),
                    MoveOp(old_idx=1, new_idx=0, item="B"),
                    InsertOp(idx=1, item="G"),
                    MoveOp(old_idx=4, new_idx=2, item="D"),
                    MoveOp(old_idx=5, new_idx=4, item="F"),
                    InsertOp(idx=5, item="H"),
                ],
                id="complex_mixed",
            ),
            # Edge case
            pytest.param(
                ["A", "A", "A"],
                ["A"],
                [DeleteOp(idx=2, item="A"), DeleteOp(idx=1, item="A")],
                id="delete_two_duplicates",
            ),
            pytest.param(
                ["A"],
                ["A", "A", "A"],
                [InsertOp(idx=1, item="A"), InsertOp(idx=2, item="A")],
                id="insert_two_duplicates",
            ),
            pytest.param(
                ["A", "B"],
                ["B", "A"],
                [MoveOp(old_idx=1, new_idx=0, item="B")],
                id="swap_two",
            ),

        ],

    )  # fmt: skip
    def test_playlist_diff(self, old, new, expected):
        """Comprehensive test suite for playlist_diff."""
        ops = list_diff(old, new, lambda x: x)
        applied_ops = [op.op for op in ops.iter()]
        assert applied_ops == expected, f"Expected {expected}, got {ops}"

        # Verify round-trip
        playlist = old.copy()
        for step in ops.iter():
            op = step.op
            if isinstance(op, DeleteOp):
                # Remove the item at the index
                playlist.pop(op.idx)
            elif isinstance(op, InsertOp):
                # Insert the item at the index
                playlist.insert(op.idx, op.item)
            elif isinstance(op, MoveOp):
                # Move item from old_idx to new_idx
                val = playlist.pop(op.old_idx)
                playlist.insert(op.new_idx, val)
            else:
                raise ValueError(f"Unknown operation: {op}")
        assert playlist == new, f"Failed to reconstruct: {playlist} != {new}"

    @pytest.mark.parametrize(
        "old, ops_list, expected_applied_ops",
        [
            # Redundant inserts/moves/deletes
            (
                ["A", "B", "C"],
                [
                    InsertOp(idx=3, item="D"),  # insert needed
                    InsertOp(idx=3, item="D"),  # insert redundant
                    DeleteOp(idx=2, item="C"),  # delete needed
                    DeleteOp(idx=2, item="C"),  # delete redundant
                ],
                [
                    InsertOp(idx=3, item="D"),
                    DeleteOp(idx=2, item="C"),
                ],
            ),
            # StopIteration branch: move refers to deleted item
            (
                ["A", "B", "C"],
                [
                    DeleteOp(idx=1, item="B"),  # deletes B
                    MoveOp(old_idx=1, new_idx=0, item="B"),  # move after deletion
                ],
                [
                    DeleteOp(idx=1, item="B"),
                ],
            ),
            # Already at target branch: redundant move
            (
                ["A", "B", "C"],
                [
                    MoveOp(old_idx=1, new_idx=1, item="B"),  # item already in place
                ],
                [],
            ),
        ],
    )
    def test_operations_redundant(self, old, ops_list, expected_applied_ops):
        """Test that Operations.__iter__ skips redundant or impossible actions."""
        ops = Operations(ops_list, old_list=old)
        applied_ops = [op.op for op in ops.iter()]
        assert applied_ops == expected_applied_ops

    def test_operations_indexing(self):
        ops = Operations(
            [
                InsertOp(idx=3, item="D"),
                DeleteOp(idx=2, item="C"),
            ],
            old_list=["A", "B", "C", "D"],
        )

        for i, op in enumerate(ops.ops):
            assert ops[i] == op


class TrackStub:
    """Minimal stub for testing partial matching by ID."""

    def __init__(self, track_id: str, title: str = "") -> None:
        self.track_id = track_id
        self.title = title

    def __repr__(self) -> str:
        return f"TrackStub({self.track_id!r}, {self.title!r})"


class TestListDiffEq:
    """Tests for list_diff_eq with equality-based partial matching."""

    @staticmethod
    def _ops_equal(
        actual: list[Op],
        expected: list[Op],
        eq_func: Callable[[object, object], bool],
    ) -> bool:
        """Compare operation lists using eq_func for item fields."""
        if len(actual) != len(expected):
            return False
        for a, e in zip(actual, expected):
            if type(a) is not type(e):
                return False
            if isinstance(a, DeleteOp) and isinstance(e, DeleteOp):
                if a.idx != e.idx or not eq_func(a.item, e.item):
                    return False
            elif isinstance(a, InsertOp) and isinstance(e, InsertOp):
                if a.idx != e.idx or not eq_func(a.item, e.item):
                    return False
            elif isinstance(a, MoveOp) and isinstance(e, MoveOp):
                if (
                    a.old_idx != e.old_idx
                    or a.new_idx != e.new_idx
                    or not eq_func(a.item, e.item)
                ):
                    return False
            else:
                return False
        return True

    @staticmethod
    def _round_trip(
        old: list,
        new: list,
        ops: Operations,
        eq_func: Callable[[object, object], bool],
    ) -> None:
        """Verify that applying operations reconstructs the target list."""
        playlist = old.copy()
        for step in ops.iter():
            op = step.op
            if isinstance(op, DeleteOp):
                playlist.pop(op.idx)
            elif isinstance(op, InsertOp):
                playlist.insert(op.idx, op.item)
            elif isinstance(op, MoveOp):
                val = playlist.pop(op.old_idx)
                playlist.insert(op.new_idx, val)
            else:
                raise ValueError(f"Unknown operation: {op}")
        assert len(playlist) == len(new), (
            f"Length mismatch: {len(playlist)} != {len(new)}"
        )
        for a, b in zip(playlist, new):
            assert eq_func(a, b), f"Item mismatch: {a!r} != {b!r}"

    @pytest.mark.parametrize(
        "old, new, expected",
        [
            # --- Parity with list_diff (eq_func == equality) ---
            pytest.param([], [], [], id="empty_to_empty"),
            pytest.param(["A"], ["A"], [], id="single_identical"),
            pytest.param(["A", "B", "C"], ["A", "B", "C"], [], id="identical_lists"),
            pytest.param([], ["A"], [InsertOp(idx=0, item="A")], id="insert_single"),
            pytest.param(["A"], [], [DeleteOp(idx=0, item="A")], id="delete_single"),
            pytest.param(
                ["A", "A"], ["A"], [DeleteOp(idx=1, item="A")], id="delete_duplicate"
            ),
            pytest.param(
                ["A"], ["A", "A"], [InsertOp(idx=1, item="A")], id="insert_duplicate"
            ),
            pytest.param(
                ["A", "B", "C"],
                ["C", "A", "B"],
                [MoveOp(old_idx=2, new_idx=0, item="C")],
                id="move_last_to_front",
            ),
            pytest.param(
                ["A", "B"],
                ["B", "A"],
                [MoveOp(old_idx=1, new_idx=0, item="B")],
                id="swap_two",
            ),
            pytest.param(
                ["A", "B", "C", "D"],
                ["B", "D", "A", "C"],
                [
                    MoveOp(old_idx=1, new_idx=0, item="B"),
                    MoveOp(old_idx=3, new_idx=1, item="D"),
                ],
                id="complex_reorder",
            ),
            # --- Partial matching: match by ID, different title ---
            pytest.param(
                [TrackStub("1", "Old Title")],
                [TrackStub("1", "New Title")],
                [],
                id="partial_match_same_id_different_title",
            ),
            # --- Partial matching: IDs determine moves ---
            pytest.param(
                [TrackStub("1"), TrackStub("2")],
                [TrackStub("2"), TrackStub("1")],
                [MoveOp(old_idx=1, new_idx=0, item=TrackStub("2"))],
                id="partial_swap_by_id",
            ),
            # --- Partial matching: delete unmatched, insert new ---
            pytest.param(
                [TrackStub("1"), TrackStub("2"), TrackStub("3")],
                [TrackStub("2"), TrackStub("4")],
                [
                    DeleteOp(idx=2, item=TrackStub("3")),
                    DeleteOp(idx=0, item=TrackStub("1")),
                    InsertOp(idx=1, item=TrackStub("4")),
                ],
                id="partial_delete_and_insert",
            ),
            # --- Partial matching: keep first occurrence when duplicates ---
            pytest.param(
                [TrackStub("1", "a"), TrackStub("1", "b")],
                [TrackStub("1", "c")],
                [DeleteOp(idx=1, item=TrackStub("1", "b"))],
                id="partial_duplicate_keep_first",
            ),
            # --- Full mix with partial matching ---
            pytest.param(
                [
                    TrackStub("1", "foo"),
                    TrackStub("2", "bar"),
                    TrackStub("3", "baz"),
                    TrackStub("4", "qux"),
                ],
                [
                    TrackStub("3", "baz-new"),
                    TrackStub("5", "new"),
                    TrackStub("1", "foo-new"),
                    TrackStub("2", "bar"),
                ],
                [
                    DeleteOp(idx=3, item=TrackStub("4", "qux")),
                    MoveOp(old_idx=2, new_idx=0, item=TrackStub("3", "baz")),
                    InsertOp(idx=1, item=TrackStub("5", "new")),
                ],
                id="partial_full_mix",
            ),
        ],
    )
    def test_list_diff_eq(self, old, new, expected):
        """Test list_diff_eq with both simple values and partial matching."""
        if old and isinstance(old[0], TrackStub):

            def eq_func(a, b):
                return a.track_id == b.track_id
        else:

            def eq_func(a, b):
                return a == b

        ops = list_diff_eq(old, new, eq_func)
        applied_ops = [op.op for op in ops.iter()]
        assert self._ops_equal(applied_ops, expected, eq_func), (
            f"Expected {expected}, got {applied_ops}"
        )
        self._round_trip(old, new, ops, eq_func)


class TestBatchConsecutive:
    @pytest.mark.parametrize(
        ["old", "new", "expected_batches"],
        [
            # Consecutive inserts -> single batch
            (
                ["A", "B"],
                ["A", "B", "C", "D"],
                [
                    [InsertOp("C", 2), InsertOp("D", 3)],
                ],
            ),
            # Non-consecutive inserts -> separate batches
            (
                ["A", "B"],
                ["A", "C", "B", "D"],
                [
                    [InsertOp("C", 1)],
                    [InsertOp("D", 3)],
                ],
            ),
            # Consecutive deletes -> single batch
            (
                ["A", "B", "C"],
                [],
                [
                    [DeleteOp("C", 2), DeleteOp("B", 1), DeleteOp("A", 0)],
                ],
            ),
            # Different types -> separate batches
            (
                ["A", "B", "C"],
                ["A", "D", "C"],
                [
                    [DeleteOp("B", 1)],
                    [InsertOp("D", 1)],
                ],
            ),
            # Moves -> each in own batch
            (
                ["A", "B", "C"],
                ["B", "A", "C"],
                [
                    [MoveOp(old_idx=1, new_idx=0, item="B")],
                ],
            ),
            # No changes
            (
                ["A", "B"],
                ["A", "B"],
                [],
            ),
        ],
    )
    def test_batch(self, old, new, expected_batches):
        ops = list_diff(old, new, lambda x: x)
        batch_steps = list(batch_consecutive(ops.iter()))
        batch_ops = list(map(lambda x: [i.op for i in x], batch_steps))
        assert batch_ops == expected_batches
