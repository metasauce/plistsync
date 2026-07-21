"""Tests for the op-based LWW Register CRDT."""

from __future__ import annotations

import pytest

from plistsync.core.crdt.graph import NodeID
from plistsync.core.crdt.lww import LWWRegister, RegisterOp


def _new_register(replica_id: int = 0) -> LWWRegister:
    return LWWRegister(replica_id)


def _op(field: str, value: object, replica: int = 0, counter: int = 0) -> RegisterOp:
    return RegisterOp(field, value, NodeID(replica, counter))


def _op_count(reg: LWWRegister) -> int:
    """Total number of ops in *reg*, via the public history API."""
    return sum(len(reg.history(field)) for field in reg)


class TestMapping:
    """Read-only Mapping protocol over current field values."""

    @pytest.mark.parametrize(
        ("field", "value"),
        [("name", "Playlist"), ("description", "Desc"), ("empty", ""), ("none", None)],
    )
    def test_assign_and_get(self, field, value):
        reg = _new_register()
        reg.assign(field, value)
        assert reg[field] == value

    def test_getitem_missing_raises(self):
        with pytest.raises(KeyError):
            _new_register()["missing"]

    def test_get_with_default(self):
        reg = _new_register()
        assert reg.get("missing") is None
        assert reg.get("missing", "fallback") == "fallback"
        reg.assign("name", "A")
        assert reg.get("name", "fallback") == "A"

    def test_len_contains_iteration(self):
        reg = _new_register()
        assert len(reg) == 0 and "name" not in reg

        reg.assign("name", "A")
        reg.assign("desc", "B")

        assert len(reg) == 2 and "name" in reg
        assert set(reg) == {"name", "desc"}

    def test_views_and_equality(self):
        reg = _new_register()
        reg.assign("name", "A")
        reg.assign("desc", "B")

        assert set(reg.items()) == {("name", "A"), ("desc", "B")}
        assert set(reg.keys()) == {"name", "desc"}
        assert set(reg.values()) == {"A", "B"}

        other = _new_register()
        other.assign("name", "A")
        assert other == {"name": "A"}
        assert other != {"name": "B"}

    def test_setitem_assigns(self):
        reg = _new_register()
        reg["name"] = "A"

        assert reg["name"] == "A"
        assert [op.key for op in reg.history("name")] == ["name"]

    def test_fields_cannot_be_deleted(self):
        reg = _new_register()
        reg.assign("name", "A")
        with pytest.raises(TypeError):
            del reg["name"]  # type: ignore[attr-defined]


class TestOpsAndClock:
    """Op creation, history, and the Lamport clock."""

    def test_assign_creates_valid_op(self):
        op = _new_register(5).assign("name", "A")
        assert (op.key, op.value, op.version) == ("name", "A", NodeID(5, 0))

    def test_first_op_uses_counter_zero(self):
        reg = _new_register(3)
        assert reg.assign("name", "A").version == NodeID(3, 0)
        assert reg.version() == NodeID(3, 1)

    def test_version_reflects_clock(self):
        reg = _new_register(2)
        assert reg.version() == NodeID(2, 0)

        reg.assign("name", "A")
        reg.assign("name", "B")
        assert reg.version() == NodeID(2, 2)

        reg.apply(_op("name", "C", replica=7, counter=41))
        assert reg.version().counter == 42

    def test_clock_advances_past_remote_ops(self):
        reg = _new_register()
        reg.apply(_op("name", "remote", replica=1, counter=41))

        # Local op must be timestamped strictly after the observed remote op.
        assert reg.assign("name", "local").version.counter > 41
        assert reg["name"] == "local"

    def test_history(self):
        reg = _new_register()
        for value in ("A", "B"):
            reg.assign("name", value)

        assert [op.value for op in reg.history("name")] == ["A", "B"]

    def test_last_op_by(self):
        a, b = _new_register(0), _new_register(1)
        a.assign("name", "A1")
        a.assign("name", "A2")
        b.assign("name", "B1")
        a.merge(b)

        assert a.last_op_by("name", 0).value == "A2"  # type: ignore[union-attr]
        assert a.last_op_by("name", 1).value == "B1"  # type: ignore[union-attr]

    def test_last_op_by_unknown_field_or_replica(self):
        reg = _new_register(0)
        reg.assign("name", "A")

        assert reg.last_op_by("other-field", 0) is None
        assert reg.last_op_by("name", 7) is None

    def test_register_op_is_frozen(self):
        v = NodeID(0, 0)
        assert RegisterOp("a", 1, v) == RegisterOp("a", 1, v)
        assert RegisterOp("a", 1, v) != RegisterOp("a", 2, v)
        with pytest.raises(Exception):
            RegisterOp("a", 1, v).value = 2  # type: ignore[misc]


class TestResolution:
    """Last-writer-wins semantics under Lamport ordering."""

    @pytest.mark.parametrize(
        "ops, expected",
        [
            ([_op("name", "A", counter=0)], "A"),
            ([_op("name", "A", counter=0), _op("name", "B", counter=1)], "B"),
            ([_op("name", "A", 0, 1), _op("name", "B", 1, 1)], "B"),
            # Fresher low-replica write beats stale high-replica write
            # (counter first, replica id only as tie-breaker).
            ([_op("name", "fresh", 0, 100), _op("name", "stale", 1, 0)], "fresh"),
            ([_op("name", "stale", 1, 0), _op("name", "fresh", 0, 100)], "fresh"),
            # Equal counters: replica id breaks the tie.
            ([_op("name", "A", 0, 5), _op("name", "B", 1, 5)], "B"),
        ],
    )
    def test_lww_ordering(self, ops, expected):
        reg = _new_register()
        for op in ops:
            reg.apply(op)
        assert reg["name"] == expected

    def test_apply_is_idempotent(self):
        reg = _new_register()
        op = _op("name", "A")

        assert reg.apply(op)
        assert not reg.apply(op)
        assert reg["name"] == "A"

    def test_apply_order_independent(self):
        ops = [_op("name", v, counter=i) for i, v in enumerate("ABC")]
        a, b = _new_register(), _new_register()

        for op in ops:
            a.apply(op)
        for op in reversed(ops):
            b.apply(op)

        assert a["name"] == b["name"] == "C"

    def test_fields_are_independent(self):
        reg = _new_register()
        reg.apply(_op("name", "A"))
        reg.apply(_op("desc", "B", counter=1))

        assert reg["name"] == "A"
        assert reg["desc"] == "B"


class TestMerge:
    def test_merge(self):
        a, b = _new_register(0), _new_register(1)
        a.assign("name", "A")
        b.assign("desc", "B")

        a.merge(b)

        assert a["name"] == "A"
        assert a["desc"] == "B"

    def test_conflict_converges(self):
        a, b = _new_register(0), _new_register(1)
        a.assign("name", "A")
        b.assign("name", "B")

        a.merge(b)
        b.merge(a)

        assert a["name"] == b["name"] == "B"
        assert len(a.history("name")) == 2

    def test_concurrent_writes_converge(self):
        # Replica 0 is causally later (higher counter) and must win everywhere.
        a, b = _new_register(0), _new_register(1)
        for _ in range(5):
            a.assign("name", "from-a")
        b.assign("name", "from-b")

        a.merge(b)
        b.merge(a)

        assert a["name"] == b["name"] == "from-a"

    def test_duplicate_ops_ignored(self):
        a, b = _new_register(), _new_register()
        op = _op("name", "A")
        a.apply(op)
        b.apply(op)

        a.merge(b)
        a.merge(b)

        assert len(a.history("name")) == 1

    def test_associative_and_commutative(self):
        a, b, c = _new_register(0), _new_register(1), _new_register(2)
        a.assign("name", "A")
        b.assign("name", "B")
        b.assign("desc", "b-desc")
        c.assign("name", "C")

        def merged(sources: tuple[LWWRegister, ...]) -> LWWRegister:
            r = _new_register(9)
            for src in sources:
                r.merge(src)
            return r

        r1, r2 = merged((a, b, c)), merged((c, a, b))
        assert r1["name"] == r2["name"]
        assert r1["desc"] == r2["desc"] == "b-desc"
        assert _op_count(r1) == _op_count(r2)


class TestForkAndTimeTravel:
    def test_fork_creates_independent_replica(self):
        a = _new_register(0)
        a.assign("name", "A")

        b = a.fork(replica_id=1)

        assert b.replica_id == 1
        assert b["name"] == "A"

        b.assign("name", "B")
        assert a["name"] == "A"
        assert b["name"] == "B"
        assert b.history("name")[-1].version.replica_id == 1

    def test_time_travel_excludes_later_ops(self):
        reg = _new_register(0)
        reg.assign("name", "first")
        cutoff = reg.version()  # causally after "first"
        reg.assign("name", "second")

        past = reg.time_travel(cutoff)

        assert past["name"] == "first"
        assert reg["name"] == "second"
        assert len(reg.history("name")) == 2

    def test_time_travel_respects_lamport_causality(self):
        # Ops with a counter below the cutoff are included; later concurrent
        # ops are excluded.
        reg = _new_register(0)
        reg.apply(_op("name", "early", replica=1, counter=1))
        reg.apply(_op("name", "late", replica=1, counter=50))

        assert reg.time_travel(NodeID(0, 10))["name"] == "early"


class TestMisc:
    @pytest.mark.parametrize("value", [None, "", "value", 123])
    def test_values_can_be_any_type(self, value):
        reg = _new_register()
        reg.assign("field", value)
        assert reg["field"] == value

    def test_large_update_sequence(self):
        reg = _new_register()
        for i in range(1000):
            reg.assign("name", i)

        assert reg["name"] == 999
        assert len(reg.history("name")) == 1000
