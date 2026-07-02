"""Tests for the FugueMax replicated list."""

from __future__ import annotations
from typing import Literal

import pytest

from plistsync.crdt import DeleteOp, Fugue, InsertOp
from plistsync.crdt.graph import NodeID


# ── helpers ──────────────────────────────────────────────────────────────


def _sync(src: Fugue[str], dst: Fugue[str]) -> None:
    """Apply all ops from *src* into *dst*."""
    for op in src.ops:
        dst.apply(op)


# ── empty list ───────────────────────────────────────────────────────────


class TestEmpty:
    def test_len_zero(self) -> None:
        assert len(Fugue()) == 0

    def test_iter_empty(self) -> None:
        assert list(Fugue()) == []

    def test_getitem_raises(self) -> None:
        fu: Fugue[int] = Fugue()
        with pytest.raises(IndexError):
            _ = fu[0]
        with pytest.raises(IndexError):
            _ = fu[-1]

    def test_delete_raises(self) -> None:
        with pytest.raises(IndexError):
            Fugue().delete(0)


# ── core operations ──────────────────────────────────────────────────────


class TestCore:
    @pytest.mark.parametrize(
        "operations, expected",
        [
            (
                # empty
                [],
                [],
            ),
            (
                # simple insert
                [
                    (0, "a", None),
                    (1, "b", None),
                    (2, "c", None),
                ],
                ["a", "b", "c"],
            ),
            (
                # prepend
                [
                    (0, "c", None),
                    (0, "b", None),
                    (0, "a", None),
                ],
                ["a", "b", "c"],
            ),
            (
                # insert middle
                [
                    (0, "a", None),
                    (1, "c", None),
                    (1, "b", None),
                ],
                ["a", "b", "c"],
            ),
            (
                # delete middle
                [
                    (0, "a", None),
                    (1, "b", None),
                    (2, "c", None),
                    (1, None, True),
                ],
                ["a", "c"],
            ),
            (
                # delete from front
                [
                    (0, "a", None),
                    (1, "b", None),
                    (2, "c", None),
                    (0, None, True),
                ],
                ["b", "c"],
            ),
            (
                # delete from back
                [
                    (0, "a", None),
                    (1, "b", None),
                    (2, "c", None),
                    (2, None, True),
                ],
                ["a", "b"],
            ),
            (
                # delete multiple consecutive
                [
                    (0, "a", None),
                    (1, "b", None),
                    (2, "c", None),
                    (3, "d", None),
                    (1, None, True),  # deletes "b", shifting "c","d" left
                    (1, None, True),  # now deletes "c"
                ],
                ["a", "d"],
            ),
            (
                # delete then insert at same position
                [
                    (0, "a", None),
                    (1, "b", None),
                    (0, None, True),
                    (0, "x", None),
                ],
                ["x", "b"],
            ),
            (
                # append via len()
                [
                    (0, "a", None),
                    (1, "b", None),
                    (2, "c", None),
                ],
                ["a", "b", "c"],
            ),
            (
                # insert at end, then prepend
                [
                    (0, "z", None),
                    (1, "y", None),
                    (0, "x", None),
                ],
                ["x", "z", "y"],
            ),
        ],
    )
    def test_ops(
        self,
        operations: list[tuple[int, str | None, Literal[True] | None]],
        expected: list[str],
    ) -> None:
        fu: Fugue[str] = Fugue()
        for index, value, delete in operations:
            if value is not None:
                fu.insert(index, value)
            if delete is not None:
                fu.delete(index)
        assert list(fu) == expected

    def test_getitem(self) -> None:
        fu: Fugue[str] = Fugue()
        for ch in "xyz":
            fu.insert(len(fu), ch)
        assert fu[0] == "x"
        assert fu[-1] == "z"
        with pytest.raises(IndexError):
            _ = fu[3]

    def test_insert_oob(self) -> None:
        with pytest.raises(IndexError):
            Fugue().insert(1, 42)

    def test_iter(self) -> None:
        fu: Fugue[int] = Fugue()
        for i in range(5):
            fu.insert(i, i)
        assert list(fu) == [0, 1, 2, 3, 4]

    def test_len_tracks_live_elements(self) -> None:
        fu: Fugue[int] = Fugue()
        assert len(fu) == 0
        fu.insert(0, 1)
        fu.insert(1, 2)
        assert len(fu) == 2
        fu.delete(0)
        assert len(fu) == 1
        fu.delete(0)
        assert len(fu) == 0

    def test_negative_index_delete(self) -> None:
        fu: Fugue[str] = Fugue()
        for ch in "abc":
            fu.insert(len(fu), ch)
        fu.delete(-1)  # deletes "c"
        assert list(fu) == ["a", "b"]
        fu.delete(-2)  # deletes "a"
        assert list(fu) == ["b"]

    def test_negative_getitem_after_delete(self) -> None:
        fu: Fugue[str] = Fugue()
        for ch in "abcd":
            fu.insert(len(fu), ch)
        fu.delete(1)  # delete "b" → ["a", "c", "d"]
        assert fu[-1] == "d"
        assert fu[-2] == "c"


# ── operation recording ──────────────────────────────────────────────────


class TestOpsRecording:
    def test_ops_records_inserts(self) -> None:
        fu: Fugue[int] = Fugue()
        op0 = fu.insert(0, 10)
        op1 = fu.insert(1, 20)
        assert fu.ops == [op0, op1]

    def test_ops_records_deletes(self) -> None:
        fu: Fugue[int] = Fugue()
        fu.insert(0, 10)
        op_del = fu.delete(0)
        assert fu.ops[-1] is op_del
        assert isinstance(op_del, DeleteOp)

    def test_ops_records_remote_applies(self) -> None:
        a: Fugue[str] = Fugue(replica_id=1)
        b: Fugue[str] = Fugue(replica_id=2)
        op = a.insert(0, "x")
        b.apply(op)
        assert len(b.ops) == 1
        assert b.ops[0] == op

    def test_ops_not_duplicated_on_reapply(self) -> None:
        """apply() appends the op to _ops even if the node already exists."""
        fu: Fugue[int] = Fugue()
        op = fu.insert(0, 42)
        initial_len = len(fu.ops)
        # applying the same op again appends it but doesn't duplicate the element
        fu.apply(op)
        assert len(fu.ops) == initial_len + 1
        assert fu._graph.node_count == 1
        assert list(fu) == [42]

    def test_ops_type_union(self) -> None:
        fu: Fugue[str] = Fugue()
        fu.insert(0, "a")
        fu.delete(0)
        ops = fu.ops
        assert isinstance(ops[0], InsertOp)
        assert isinstance(ops[1], DeleteOp)


# ── version & counter ────────────────────────────────────────────────────


class TestVersioning:
    def test_version_initial(self) -> None:
        fu: Fugue[str] = Fugue(replica_id=3)
        v = fu.version()
        assert v.replica_id == 3
        assert v.counter == 0

    def test_version_after_inserts(self) -> None:
        fu: Fugue[str] = Fugue(replica_id=1)
        fu.insert(0, "a")
        fu.insert(1, "b")
        v = fu.version()
        assert v.replica_id == 1
        assert v.counter == 2  # used IDs: 0, 1 → next would be 2

    def test_version_after_remote_apply(self) -> None:
        a: Fugue[str] = Fugue(replica_id=5)
        b: Fugue[str] = Fugue(replica_id=7)
        op = a.insert(0, "x")
        b.apply(op)
        # b's own counter unaffected by remote ops
        assert b.version().counter == 0

    def test_initial_counter_parameter(self) -> None:
        fu: Fugue[str] = Fugue(replica_id=0, initial_counter=10)
        assert fu.version() == NodeID(0, 10)
        fu.insert(0, "a")
        assert fu.version() == NodeID(0, 11)

    def test_counter_independent_per_replica(self) -> None:
        a: Fugue[str] = Fugue(replica_id=1)
        b: Fugue[str] = Fugue(replica_id=2)
        a.insert(0, "a1")
        b.insert(0, "b1")
        b.insert(1, "b2")
        assert a.version() == NodeID(1, 1)
        assert b.version() == NodeID(2, 2)
        # merging doesn't clobber local counters
        _sync(b, a)
        assert a.version() == NodeID(1, 1)


# ── fork ─────────────────────────────────────────────────────────────────


class TestFork:
    def test_fork_preserves_state(self) -> None:
        base: Fugue[str] = Fugue(replica_id=0)
        for ch in "abc":
            base.insert(len(base), ch)
        fork: Fugue[str] = base.fork(replica_id=1)
        assert list(fork) == ["a", "b", "c"]
        assert fork.replica_id == 1

    def test_fork_is_independent(self) -> None:
        base: Fugue[str] = Fugue(replica_id=0)
        base.insert(0, "x")
        fork = base.fork(replica_id=1)
        fork.insert(1, "y")
        base.insert(1, "z")
        # base and fork diverge
        assert list(base) == ["x", "z"]
        assert list(fork) == ["x", "y"]

    def test_fork_keeps_ops_history(self) -> None:
        base: Fugue[str] = Fugue(replica_id=0)
        base.insert(0, "a")
        fork = base.fork(replica_id=1)
        assert len(fork.ops) == len(base.ops)
        assert fork.ops == base.ops

    def test_fork_version_preserved(self) -> None:
        """Fork starts with counter 0 for the *new* replica_id."""
        base: Fugue[str] = Fugue(replica_id=0, initial_counter=5)
        fork = base.fork(replica_id=9)
        # counters are per-replica; the new replica starts fresh
        assert fork.version() == NodeID(9, 0)
        # the old replica's counter is unaffected
        assert base.version() == NodeID(0, 5)

    def test_fork_from_empty(self) -> None:
        base: Fugue[int] = Fugue()
        fork = base.fork(replica_id=42)
        assert len(fork) == 0
        assert fork.replica_id == 42


# ── apply (remote operations) ────────────────────────────────────────────


class TestApply:
    def test_apply_remote_insert(self) -> None:
        local: Fugue[str] = Fugue(replica_id=1)
        remote: Fugue[str] = Fugue(replica_id=2)
        op = remote.insert(0, "hello")
        local.apply(op)
        assert list(local) == ["hello"]

    def test_apply_remote_delete(self) -> None:
        """A DeleteOp targets a specific NodeID — only that node is deleted."""
        a: Fugue[str] = Fugue(replica_id=1)
        b: Fugue[str] = Fugue(replica_id=2)
        # b inserts and deletes locally
        b.insert(0, "x")
        op_del = b.delete(0)
        # a applies the same insert first, then the delete
        a.apply(b.ops[0])  # InsertOp from b
        assert list(a) == ["x"]
        a.apply(op_del)  # DeleteOp from b
        assert list(a) == []

    def test_apply_duplicate_insert_is_idempotent(self) -> None:
        fu: Fugue[int] = Fugue()
        op = fu.insert(0, 42)
        node_count_before = fu._graph.node_count
        fu.apply(op)
        assert fu._graph.node_count == node_count_before
        assert list(fu) == [42]

    def test_apply_duplicate_delete_is_harmless(self) -> None:
        fu: Fugue[int] = Fugue()
        fu.insert(0, 99)
        op = fu.delete(0)
        fu.apply(op)  # second application
        assert list(fu) == []

    def test_apply_foreign_delete_before_local_insert(self) -> None:
        """Apply a delete whose NodeID was never inserted locally."""
        remote: Fugue[str] = Fugue(replica_id=9)
        remote.insert(0, "gone")
        op_del = remote.delete(0)
        local: Fugue[str] = Fugue(replica_id=1)
        local.apply(op_del)  # should not raise
        assert list(local) == []

    def test_apply_mixed_ops_order_independent(self) -> None:
        ops_a = []
        ops_b = []
        a: Fugue[str] = Fugue(replica_id=1)
        b: Fugue[str] = Fugue(replica_id=2)
        for ch in "ab":
            ops_a.append(a.insert(len(a), ch))
        for ch in "xy":
            ops_b.append(b.insert(len(b), ch))
        ops_a.append(a.delete(0))  # delete "a"
        ops_b.append(b.delete(0))  # delete "x"

        r1: Fugue[str] = Fugue()
        for op in ops_a + ops_b:
            r1.apply(op)
        r2: Fugue[str] = Fugue()
        for op in ops_b + ops_a:
            r2.apply(op)
        assert list(r1) == list(r2)

    def test_apply_preserves_node_count(self) -> None:
        """Re-applying the same ops should not grow the node graph."""
        fu: Fugue[int] = Fugue()
        op = fu.insert(0, 1)
        assert fu._graph.node_count == 1
        fu.apply(op)
        assert fu._graph.node_count == 1


# ── non-interleaving / convergence ───────────────────────────────────────


class TestNonInterleaving:
    def test_interleaving(self) -> None:
        base = Fugue[str](replica_id=0)
        a = base.fork(replica_id=1)
        b = base.fork(replica_id=2)

        ops_a = []
        for ch in "hello ":
            op = a.insert(len(a), ch)
            ops_a.append(op)

        ops_b = []
        for ch in "world":
            op = b.insert(len(b), ch)
            ops_b.append(op)

        # Ordering should be by replica id on conflict
        for op in ops_b + ops_a:
            base.apply(op)

        assert "".join(base) == "hello world"

    def test_convergence(self) -> None:
        a = Fugue[str](replica_id=1)
        b = Fugue[str](replica_id=2)

        for ch in "abc":
            a.insert(len(a), ch)
        for ch in "xyz":
            b.insert(len(b), ch)

        m1 = Fugue[str]()
        for op in a.ops + b.ops:
            m1.apply(op)
        m2 = Fugue[str]()
        for op in b.ops + a.ops:
            m2.apply(op)
        assert list(m1) == list(m2)

    def test_idempotent(self) -> None:
        lst = Fugue[int]()
        op = lst.insert(0, 42)
        lst.apply(op)
        assert list(lst) == [42]
        assert lst._graph.node_count == 1

    def test_convergence_with_deletes(self) -> None:
        a = Fugue[str](replica_id=1)
        b = Fugue[str](replica_id=2)

        for ch in "abcd":
            a.insert(len(a), ch)
        a.delete(1)  # delete "b"
        a.delete(2)  # delete "d" (after "b" removal, index 2 is "d")

        for ch in "wxyz":
            b.insert(len(b), ch)
        b.delete(0)  # delete "w"
        b.delete(2)  # delete "y" (after "w" removal)

        m1 = Fugue[str]()
        for op in a.ops + b.ops:
            m1.apply(op)
        m2 = Fugue[str]()
        for op in b.ops + a.ops:
            m2.apply(op)
        assert list(m1) == list(m2)

    def test_convergence_three_replicas(self) -> None:
        r: list[Fugue[str]] = [Fugue[str](replica_id=i) for i in range(3)]
        for i, fu in enumerate(r):
            fu.insert(0, str(i))
        # Merge all into a fresh replica in every permutation
        merged = Fugue[str]()
        for fu in r:
            _sync(fu, merged)
        assert len(merged) == 3


# ── concurrency stress / edge cases ──────────────────────────────────────


class TestConcurrency:
    def test_concurrent_insert_same_position_two_replicas(self) -> None:
        """Two replicas inserting at index 0 concurrently."""
        a: Fugue[str] = Fugue(replica_id=1)
        b: Fugue[str] = Fugue(replica_id=2)
        op_a = a.insert(0, "A")
        op_b = b.insert(0, "B")

        merged: Fugue[str] = Fugue()
        merged.apply(op_a)
        merged.apply(op_b)
        # Both elements should be present; exact order depends on replica id
        assert set(merged) == {"A", "B"}
        assert len(merged) == 2

    def test_concurrent_insert_delete_same_element(self) -> None:
        """One replica inserts, another deletes that same element concurrently."""
        base: Fugue[str] = Fugue(replica_id=0)
        op_ins = base.insert(0, "shared")

        a = base.fork(replica_id=1)
        b = base.fork(replica_id=2)
        a.delete(0)  # deletes "shared"
        b.insert(1, "extra")

        merged: Fugue[str] = Fugue()
        for op in base.ops + a.ops + b.ops:
            merged.apply(op)
        # "shared" is deleted; "extra" is present
        assert "shared" not in list(merged)
        assert "extra" in list(merged)

    def test_many_concurrent_appends(self) -> None:
        """Many replicas appending concurrently should all be preserved."""
        n = 10
        replicas = [Fugue[str](replica_id=i) for i in range(n)]
        ops_all: list[InsertOp[str]] = []
        for i, fu in enumerate(replicas):
            ops_all.append(fu.insert(0, f"r{i}"))

        merged: Fugue[str] = Fugue()
        for op in ops_all:
            merged.apply(op)
        assert len(merged) == n
        assert {f"r{i}" for i in range(n)} == set(merged)

    def test_interleaved_inserts_from_three_replicas(self) -> None:
        a: Fugue[str] = Fugue(replica_id=1)
        b: Fugue[str] = Fugue(replica_id=2)
        c: Fugue[str] = Fugue(replica_id=3)

        a.insert(0, "a1")
        b.insert(0, "b1")
        c.insert(0, "c1")

        a.insert(1, "a2")
        b.insert(1, "b2")
        c.insert(1, "c2")

        merged: Fugue[str] = Fugue()
        for fu in (a, b, c):
            _sync(fu, merged)
        assert len(merged) == 6
        # no duplicates
        assert len(set(merged)) == 6


# ── edge cases ───────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_single_element_lifecycle(self) -> None:
        fu: Fugue[int] = Fugue()
        fu.insert(0, 1)
        assert len(fu) == 1
        assert fu[0] == 1
        fu.delete(0)
        assert len(fu) == 0
        with pytest.raises(IndexError):
            _ = fu[0]

    def test_delete_all_then_reinsert(self) -> None:
        fu: Fugue[str] = Fugue()
        for ch in "abc":
            fu.insert(len(fu), ch)
        while len(fu) > 0:
            fu.delete(0)
        assert list(fu) == []
        # reinsert after all deleted
        fu.insert(0, "x")
        fu.insert(1, "y")
        assert list(fu) == ["x", "y"]

    def test_insert_after_delete_at_end(self) -> None:
        fu: Fugue[str] = Fugue()
        fu.insert(0, "a")
        fu.insert(1, "b")
        fu.delete(1)  # delete "b"
        fu.insert(1, "c")  # insert at the end
        assert list(fu) == ["a", "c"]

    def test_insert_after_delete_at_beginning(self) -> None:
        fu: Fugue[str] = Fugue()
        fu.insert(0, "a")
        fu.insert(1, "b")
        fu.delete(0)  # delete "a"
        fu.insert(0, "x")
        assert list(fu) == ["x", "b"]

    def test_large_sequence(self) -> None:
        fu: Fugue[int] = Fugue()
        n = 200
        for i in range(n):
            fu.insert(i, i)
        assert list(fu) == list(range(n))
        assert fu[n // 2] == n // 2
        # delete half
        for _ in range(n // 2):
            fu.delete(n // 2)
        assert len(fu) == n // 2

    def test_delete_then_getitem_negative(self) -> None:
        fu: Fugue[str] = Fugue()
        for ch in "abcde":
            fu.insert(len(fu), ch)
        fu.delete(1)  # delete "b" → ["a", "c", "d", "e"]
        assert fu[-1] == "e"
        assert fu[-3] == "c"

    def test_all_same_value(self) -> None:
        """Multiple insertions of the same value should all be kept."""
        fu: Fugue[str] = Fugue()
        for _ in range(5):
            fu.insert(len(fu), "dup")
        assert list(fu) == ["dup"] * 5

    def test_time_travel_returns_fugue_instance(self) -> None:
        """Basic smoke test — time_travel is a stub, but shouldn't crash."""
        fu: Fugue[str] = Fugue(replica_id=1)
        fu.insert(0, "a")
        past = fu.time_travel(NodeID(1, 0))
        assert isinstance(past, Fugue)
        assert past.replica_id == 1


# ── InsertOp / DeleteOp dataclasses ──────────────────────────────────────


class TestOpDataclasses:
    def test_insert_op_frozen(self) -> None:
        op = InsertOp[str](
            node=__import__("plistsync.crdt.graph", fromlist=["Node"]).Node(
                id=NodeID(0, 0),
                parent_id=NodeID.root(),
                side=__import__("plistsync.crdt.graph", fromlist=["Side"]).Side.RIGHT,
            ),
            value="test",
        )
        assert op.value == "test"
        with pytest.raises(Exception):  # frozen → TypeError or FrozenInstanceError
            op.value = "changed"  # type: ignore[misc]

    def test_delete_op_frozen(self) -> None:
        op = DeleteOp(node_id=NodeID(7, 3))
        assert op.node_id == NodeID(7, 3)
        with pytest.raises(Exception):
            op.node_id = NodeID(0, 0)  # type: ignore[misc]

    def test_ops_equality(self) -> None:
        a: Fugue[int] = Fugue(replica_id=0, initial_counter=0)
        op1 = a.insert(0, 1)
        b: Fugue[int] = Fugue(replica_id=0, initial_counter=0)
        op2 = b.insert(0, 1)
        # structurally identical ops from same initial state should be equal
        assert op1 == op2
        # InsertOp is frozen but contains a mutable Node, so it is unhashable
        with pytest.raises(TypeError):
            hash(op1)
