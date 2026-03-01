import pytest

from plistsync.core.diff import DeleteOp, InsertOp, MoveOp, Operations, list_diff


class TestPlaylistDiff:
    """Test suif for the playlist_diff function."""

    # fmt: off
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
            # Delets
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
    )
    def test_playlist_diff(self, old, new, expected):
        """Comprehensive test suite for playlist_diff."""
        ops = list_diff(old, new, lambda x: x)
        assert list(ops) == expected, f"Expected {expected}, got {ops}"

        # Verify round-trip
        playlist = old.copy()
        for op in list(ops):
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

    # fmt: on

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
        applied_ops = list(ops)
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
