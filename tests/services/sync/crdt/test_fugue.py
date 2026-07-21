"""Tests for the FugueMax replicated list."""

from __future__ import annotations
from typing import Literal

import pytest

from plistsync.services.sync.crdt import DeleteOp, Fugue, InsertOp, InsertPos
from plistsync.services.sync.crdt.fugue import Ops
from plistsync.services.sync.crdt.graph import NodeID, Side


def _sync(src: Fugue[str], dst: Fugue[str]) -> None:
    """Apply all ops from *src* into *dst*."""
    for op in src.ops:
        dst.apply(op)


class TestCore:
    @pytest.mark.parametrize(
        "operations, expected",
        [
            # empty
            ([], []),
            # simple insert
            (
                [(0, "a", None), (1, "b", None), (2, "c", None)],
                ["a", "b", "c"],
            ),
            # prepend
            (
                [(0, "c", None), (0, "b", None), (0, "a", None)],
                ["a", "b", "c"],
            ),
            # insert middle
            (
                [(0, "a", None), (1, "c", None), (1, "b", None)],
                ["a", "b", "c"],
            ),
            # delete middle
            (
                [(0, "a", None), (1, "b", None), (2, "c", None), (1, None, True)],
                ["a", "c"],
            ),
            # delete from front
            (
                [(0, "a", None), (1, "b", None), (2, "c", None), (0, None, True)],
                ["b", "c"],
            ),
            # delete from back
            (
                [(0, "a", None), (1, "b", None), (2, "c", None), (2, None, True)],
                ["a", "b"],
            ),
            # delete multiple consecutive
            (
                [
                    (0, "a", None),
                    (1, "b", None),
                    (2, "c", None),
                    (3, "d", None),
                    (1, None, True),
                    (1, None, True),
                ],
                ["a", "d"],
            ),
            # delete then insert at same position
            (
                [(0, "a", None), (1, "b", None), (0, None, True), (0, "x", None)],
                ["x", "b"],
            ),
            # append via len()
            (
                [(0, "a", None), (1, "b", None), (2, "c", None)],
                ["a", "b", "c"],
            ),
            # insert at end, then prepend
            (
                [(0, "z", None), (1, "y", None), (0, "x", None)],
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
            Fugue[int]().insert(1, 42)

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

    def test_negative_getitem_after_delete(self) -> None:
        fu: Fugue[str] = Fugue()
        for ch in "abcd":
            fu.insert(len(fu), ch)
        fu.delete(1)
        assert fu[-1] == "d"
        assert fu[-2] == "c"

    def test_insert_when_left_neighbor_has_no_right_children(self) -> None:
        """Insert between elements where the left neighbor is a leaf node."""
        fu: Fugue[str] = Fugue()
        fu.insert(0, "a")
        fu.insert(0, "b")  # b becomes LEFT child of a → b is a leaf
        fu.insert(1, "c")  # index 1: left=b (leaf), so c is RIGHT child of b
        assert list(fu) == ["b", "c", "a"]


class TestOpsRecording:
    def test_ops_records_inserts_and_deletes(self) -> None:
        fu: Fugue[int] = Fugue()
        ins = fu.insert(0, 10)
        assert fu.ops == [ins]
        op_del = fu.delete(0)
        assert fu.ops == [ins, op_del]
        assert isinstance(op_del, DeleteOp)

    def test_ops_records_remote_applies(self) -> None:
        a: Fugue[str] = Fugue(replica_id=1)
        b: Fugue[str] = Fugue(replica_id=2)
        op = a.insert(0, "x")
        b.apply(op)
        assert len(b.ops) == 1
        assert b.ops[0] == op

    def test_ops_not_duplicated_on_reapply(self) -> None:
        fu: Fugue[int] = Fugue()
        op = fu.insert(0, 42)
        initial_len = len(fu.ops)
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


class TestVersioning:
    def test_version_tracks_local_counter(self) -> None:
        fu: Fugue[str] = Fugue(replica_id=3)
        assert fu.version() == NodeID(3, 0)
        fu.insert(0, "a")
        fu.insert(1, "b")
        assert fu.version() == NodeID(3, 2)

    def test_version_after_remote_apply(self) -> None:
        a: Fugue[str] = Fugue(replica_id=5)
        b: Fugue[str] = Fugue(replica_id=7)
        op = a.insert(0, "x")
        b.apply(op)
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
        _sync(b, a)
        assert a.version() == NodeID(1, 1)


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
        assert list(base) == ["x", "z"]
        assert list(fork) == ["x", "y"]

    def test_fork_keeps_ops_history(self) -> None:
        base: Fugue[str] = Fugue(replica_id=0)
        base.insert(0, "a")
        fork = base.fork(replica_id=1)
        assert len(fork.ops) == len(base.ops)
        assert fork.ops == base.ops

    def test_fork_version_preserved(self) -> None:
        base: Fugue[str] = Fugue(replica_id=0, initial_counter=5)
        fork = base.fork(replica_id=9)
        assert fork.version() == NodeID(9, 0)
        assert base.version() == NodeID(0, 5)

    def test_fork_from_empty(self) -> None:
        base: Fugue[int] = Fugue()
        fork = base.fork(replica_id=42)
        assert len(fork) == 0
        assert fork.replica_id == 42


class TestApply:
    def test_apply_remote_insert(self) -> None:
        local: Fugue[str] = Fugue(replica_id=1)
        remote: Fugue[str] = Fugue(replica_id=2)
        op = remote.insert(0, "hello")
        local.apply(op)
        assert list(local) == ["hello"]

    def test_apply_remote_delete(self) -> None:
        a: Fugue[str] = Fugue(replica_id=1)
        b: Fugue[str] = Fugue(replica_id=2)
        b.insert(0, "x")
        op_del = b.delete(0)
        a.apply(b.ops[0])
        assert list(a) == ["x"]
        a.apply(op_del)
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
        fu.apply(op)
        assert list(fu) == []

    def test_apply_foreign_delete_before_local_insert(self) -> None:
        remote: Fugue[str] = Fugue(replica_id=9)
        remote.insert(0, "gone")
        op_del = remote.delete(0)
        local: Fugue[str] = Fugue(replica_id=1)
        local.apply(op_del)
        assert list(local) == []

    def test_apply_mixed_ops_order_independent(self) -> None:
        ops_a: list[InsertOp[str] | DeleteOp] = []
        ops_b: list[InsertOp[str] | DeleteOp] = []
        a: Fugue[str] = Fugue(replica_id=1)
        b: Fugue[str] = Fugue(replica_id=2)
        for ch in "ab":
            ops_a.append(a.insert(len(a), ch))
        for ch in "xy":
            ops_b.append(b.insert(len(b), ch))
        ops_a.append(a.delete(0))
        ops_b.append(b.delete(0))

        r1: Fugue[str] = Fugue()
        for op in ops_a + ops_b:
            r1.apply(op)
        r2: Fugue[str] = Fugue()
        for op in ops_b + ops_a:
            r2.apply(op)
        assert list(r1) == list(r2)

    def test_apply_preserves_node_count(self) -> None:
        fu: Fugue[int] = Fugue()
        op = fu.insert(0, 1)
        assert fu._graph.node_count == 1
        fu.apply(op)
        assert fu._graph.node_count == 1


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
        a.delete(1)
        a.delete(2)

        for ch in "wxyz":
            b.insert(len(b), ch)
        b.delete(0)
        b.delete(2)

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
        merged = Fugue[str]()
        for fu in r:
            _sync(fu, merged)
        assert len(merged) == 3


class TestConcurrency:
    def test_concurrent_insert_same_position_two_replicas(self) -> None:
        a: Fugue[str] = Fugue(replica_id=1)
        b: Fugue[str] = Fugue(replica_id=2)
        op_a = a.insert(0, "A")
        op_b = b.insert(0, "B")

        merged: Fugue[str] = Fugue()
        merged.apply(op_a)
        merged.apply(op_b)
        assert set(merged) == {"A", "B"}
        assert len(merged) == 2

    def test_concurrent_insert_delete_same_element(self) -> None:
        base: Fugue[str] = Fugue(replica_id=0)
        base.insert(0, "shared")

        a = base.fork(replica_id=1)
        b = base.fork(replica_id=2)
        a.delete(0)
        b.insert(1, "extra")

        merged: Fugue[str] = Fugue()
        for op in base.ops + a.ops + b.ops:
            merged.apply(op)
        assert "shared" not in list(merged)
        assert "extra" in list(merged)

    def test_many_concurrent_appends(self) -> None:
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
        assert len(set(merged)) == 6


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
        fu.insert(0, "x")
        fu.insert(1, "y")
        assert list(fu) == ["x", "y"]

    def test_insert_after_delete_at_end(self) -> None:
        fu: Fugue[str] = Fugue()
        fu.insert(0, "a")
        fu.insert(1, "b")
        fu.delete(1)
        fu.insert(1, "c")
        assert list(fu) == ["a", "c"]

    def test_insert_after_delete_at_beginning(self) -> None:
        fu: Fugue[str] = Fugue()
        fu.insert(0, "a")
        fu.insert(1, "b")
        fu.delete(0)
        fu.insert(0, "x")
        assert list(fu) == ["x", "b"]

    def test_large_sequence(self) -> None:
        fu: Fugue[int] = Fugue()
        n = 200
        for i in range(n):
            fu.insert(i, i)
        assert list(fu) == list(range(n))
        assert fu[n // 2] == n // 2
        for _ in range(n // 2):
            fu.delete(n // 2)
        assert len(fu) == n // 2

    def test_delete_then_getitem_negative(self) -> None:
        fu: Fugue[str] = Fugue()
        for ch in "abcde":
            fu.insert(len(fu), ch)
        fu.delete(1)
        assert fu[-1] == "e"
        assert fu[-3] == "c"

    def test_all_same_value(self) -> None:
        fu: Fugue[str] = Fugue()
        for _ in range(5):
            fu.insert(len(fu), "dup")
        assert list(fu) == ["dup"] * 5


class TestTimeTravel:
    def test_empty(self) -> None:
        fu: Fugue[str] = Fugue(replica_id=0)
        past = fu.time_travel(fu.version())
        assert list(past) == []

    def test_to_mid_history(self) -> None:
        fu: Fugue[str] = Fugue(replica_id=0)
        fu.insert(0, "a")  # counter 0
        fu.insert(1, "b")  # counter 1
        fu.insert(2, "c")  # counter 2 — version() → (0, 3)
        past = fu.time_travel(NodeID(0, 1))
        assert list(past) == ["a"]

    def test_to_current_version(self) -> None:
        fu: Fugue[str] = Fugue(replica_id=0)
        fu.insert(0, "a")
        fu.insert(1, "b")
        past = fu.time_travel(fu.version())
        assert list(past) == ["a", "b"]

    def test_before_any_ops(self) -> None:
        fu: Fugue[str] = Fugue(replica_id=0, initial_counter=5)
        fu.insert(0, "a")  # counter 5
        past = fu.time_travel(NodeID(0, 5))
        assert list(past) == []

    def test_with_deletes(self) -> None:
        fu: Fugue[str] = Fugue(replica_id=0)
        fu.insert(0, "a")  # counter 0
        fu.insert(1, "b")  # counter 1
        fu.insert(2, "c")  # counter 2
        fu.delete(1)  # delete "b" (targets NodeID with counter 1)
        # Travel to (0, 2): "a" (0) and "b" (1) visible; delete applies to "b"
        past = fu.time_travel(NodeID(0, 2))
        assert list(past) == ["a"]
        # Travel to (0, 1): only "a" visible; delete targets "b" (not visible → skipped)
        past2 = fu.time_travel(NodeID(0, 1))
        assert list(past2) == ["a"]

    def test_preserves_replica_id(self) -> None:
        fu: Fugue[str] = Fugue(replica_id=7)
        fu.insert(0, "x")
        past = fu.time_travel(fu.version())
        assert past.replica_id == 7

    def test_multi_replica_causal_snapshot(self) -> None:
        a: Fugue[str] = Fugue(replica_id=1)
        a.insert(0, "a1")  # (1, 0)
        a.insert(1, "a2")  # (1, 1)
        b: Fugue[str] = Fugue(replica_id=2)
        b.insert(0, "b1")  # (2, 0)
        _sync(b, a)  # a now has a1, a2, b1
        past = a.time_travel(NodeID(1, 2))
        assert "a1" in list(past)
        assert "a2" in list(past)

    def test_remote_op_after_snapshot_is_excluded(self) -> None:
        """Remote ops that arrive after version() are not causally before it."""
        a: Fugue[str] = Fugue(replica_id=1)
        b: Fugue[str] = Fugue(replica_id=2)
        a.insert(0, "a1")
        v = a.version()
        a.apply(b.insert(0, "b1"))  # arrives after snapshot
        past = a.time_travel(v)
        assert list(past) == ["a1"]

    def test_does_not_mutate_original(self) -> None:
        """The returned replica is independent of the original."""
        fu: Fugue[str] = Fugue(replica_id=1)
        fu.insert(0, "a")
        v = fu.version()
        fu.insert(1, "b")
        past = fu.time_travel(v)
        past.insert(1, "x")
        assert list(fu) == ["a", "b"]
        assert list(past) == ["a", "x"]

    def test_forked_replica(self) -> None:
        """time_travel on a fork excludes later operations on that fork."""
        base: Fugue[str] = Fugue(replica_id=0)
        base.insert(0, "shared")
        a = base.fork(replica_id=1)
        a.insert(1, "a1")
        v = a.version()
        a.insert(2, "a2")
        past = a.time_travel(v)
        assert list(past) == ["shared", "a1"]

    def test_remote_arrives_after_later_local_op(self) -> None:
        """Remote op causally before version but logged after it must be included."""
        a: Fugue[str] = Fugue(replica_id=1)
        b: Fugue[str] = Fugue(replica_id=2)
        a.insert(0, "a1")
        v = a.version()  # NodeID(1, 1)
        a.insert(1, "a2")  # (1, 1) — after snapshot
        a.apply(b.insert(0, "b1"))  # concurrent with (1, 0), arrives late
        past = a.time_travel(v)
        assert set(past) == {"a1"}

    def test_concurrent_inserts_arrive_late(self) -> None:
        """Three replicas — ops arrive in arbitrary order."""
        r: list[Fugue[str]] = [Fugue[str](replica_id=i) for i in range(3)]
        r[0].insert(0, "r0-a")
        v = r[0].version()  # NodeID(0, 1)
        r[0].insert(1, "r0-b")
        r[0].insert(2, "r0-c")
        r[0].apply(r[1].insert(0, "r1-a"))
        r[0].apply(r[2].insert(0, "r2-a"))
        past = r[0].time_travel(v)
        assert list(past) == ["r0-a"]

    def test_causal_snapshot_mid_merge(self) -> None:
        """Snapshot before receiving a batch of remote ops excludes them all."""
        a: Fugue[str] = Fugue(replica_id=1)
        b: Fugue[str] = Fugue(replica_id=2)
        a.insert(0, "a1")
        v = a.version()
        for ch in "bcd":
            b.insert(len(b), ch)
        for op in b.ops:
            a.apply(op)
        past = a.time_travel(v)
        assert list(past) == ["a1"]


class TestOpDataclasses:
    def test_insert_op_frozen(self) -> None:
        op = InsertOp[str](
            pos=InsertPos(
                id=NodeID(0, 0),
                parent_id=NodeID.root(),
                side=Side.RIGHT,
            ),
            value="test",
        )
        assert op.value == "test"
        with pytest.raises(Exception):
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
        assert op1 == op2
        with pytest.raises(Exception):
            op1.pos = InsertPos(  # type: ignore[misc]  # pyright: ignore[reportAttributeAccessIssue]
                id=NodeID(9, 9), parent_id=NodeID.root(), side=Side.LEFT
            )

    def test_ops_eq_with_non_ops(self) -> None:
        ops: Ops[int] = Ops()
        assert not (ops == "not ops")  # NotImplemented path

    def test_ops_get_value_missing_raises(self) -> None:
        ops: Ops[int] = Ops()
        with pytest.raises(IndexError):
            ops.get_value(NodeID(99, 99))


class TestDeleteOOB:
    def test_delete_oob_empty(self) -> None:
        with pytest.raises(IndexError):
            Fugue[int]().delete(0)

    def test_delete_oob_after_insert(self) -> None:
        fu: Fugue[int] = Fugue()
        fu.insert(0, 1)
        with pytest.raises(IndexError):
            fu.delete(1)


class TestGraphCoverage:
    """Hit the remaining uncovered lines in graph.py."""

    def test_ancestors_missing_node_returns_empty(self) -> None:
        from plistsync.services.sync.crdt.graph import Graph

        g = Graph()
        assert g.ancestor_closure(NodeID(99, 99)) == frozenset({NodeID(99, 99)})

    def test_subtree_size_cache_hit(self) -> None:
        """Calling _subtree_size twice with same version hits the cache."""
        fu: Fugue[int] = Fugue()
        fu.insert(0, 1)
        fu.insert(1, 2)
        g = fu._graph
        root = NodeID.root()
        s1 = g._subtree_size(root)
        s2 = g._subtree_size(root)
        assert s1 == s2

    def test_subtree_size_child_already_cached(self) -> None:
        """Parent recompute with right child already at current version."""
        fu: Fugue[int] = Fugue()
        fu.insert(0, 1)
        fu.insert(1, 2)
        g = fu._graph
        # Bump global version by inserting at end (creates right child of last node)
        fu.insert(len(fu), 3)
        # The last inserted node is the rightmost leaf; cache it at current version
        last = fu._graph._full_order[-1]
        g._subtree_size(last)
        # Recompute root — the cached child should skip stacking
        s = g._subtree_size(NodeID.root())
        assert s >= 3

    def test_subtree_size_left_child_already_cached(self) -> None:
        """Parent recompute with left child already at current version."""
        fu: Fugue[int] = Fugue()
        fu.insert(0, 1)
        g = fu._graph
        # Bump global version by inserting at beginning (creates left child of first node)
        fu.insert(0, 2)
        # Cache the left child (node 2 is left child of node 1)
        first = fu._graph._full_order[0]
        g._subtree_size(first)
        # Recompute root — the cached left child should skip stacking
        s = g._subtree_size(NodeID.root())
        assert s >= 2
