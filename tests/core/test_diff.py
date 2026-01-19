import pytest

from plistsync.core.diff import DeleteOp, InsertOp, MoveOp, Operations, list_diff


class TestPlaylistDiff:
    """Test suif for the playlist_diff function."""

    @pytest.mark.parametrize(
        "old, new, expected",
        [
            pytest.param([], [], [], id="empty_lists"),
            pytest.param(["A", "B", "C"], ["A", "B", "C"], [], id="identical_lists"),
            pytest.param(["A"], [], [DeleteOp(idx=0, item="A")], id="simple_delete"),
            pytest.param([], ["A"], [InsertOp(idx=0, item="A")], id="simple_insert"),
            pytest.param(
                ["A", "B", "C"],
                ["C", "A", "B"],
                [MoveOp(old_idx=2, new_idx=0, item="C")],
                id="move_last_to_front",
            ),
            pytest.param(
                ["A", "B", "C"],
                ["X", "A", "C"],
                [
                    DeleteOp(idx=1, item="B"),
                    InsertOp(idx=0, item="X"),
                ],
                id="delete_middle_insert_front",
            ),
            pytest.param(
                ["A", "B", "C"],
                ["A", "B", "B", "C"],
                [InsertOp(idx=2, item="B")],
                id="duplicate_delete",
            ),
            pytest.param(
                ["A", "A"],
                ["A"],
                [DeleteOp(idx=1, item="A")],
                id="duplicate_delete",
            ),
            pytest.param(
                ["A"],
                ["A", "A"],
                [InsertOp(idx=1, item="A")],
                id="duplicate_insert",
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
            pytest.param(
                ["A", "B", "C", "D", "E", "F"],
                ["B", "G", "D", "A", "F", "H", "C"],
                [
                    DeleteOp(idx=4, item="E"),
                    InsertOp(idx=1, item="G"),
                    InsertOp(idx=5, item="H"),
                    MoveOp(old_idx=2, new_idx=0, item="B"),
                    MoveOp(old_idx=2, new_idx=1, item="G"),
                    MoveOp(old_idx=4, new_idx=2, item="D"),
                    MoveOp(old_idx=6, new_idx=4, item="F"),
                    MoveOp(old_idx=6, new_idx=5, item="H"),
                ],
                id="complex",
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
