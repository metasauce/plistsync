"""Tests for the Fugue serializer layer."""

from __future__ import annotations

import json
from typing import Any, Literal, cast, TYPE_CHECKING

import pytest

from plistsync.services.sync.crdt.fugue import Fugue
from plistsync.services.sync.crdt.graph import NodeID, Side
from plistsync.services.sync.crdt.lww import LWWRegister
from plistsync.services.sync.crdt.serialize import (
    FugueSerializer,
    FugueState,
    LWWSerializer,
    NodeIDState,
    NodeSerializer,
    OpStateDelete,
    OpStateInsert,
)
from plistsync.utils.serializer import DummySerializer

if TYPE_CHECKING:
    from plistsync.services.sync.crdt.serialize import (
        LWWRegisterState,
    )


class TestNodeID:
    @pytest.mark.parametrize(
        ("replica_id", "counter"),
        [(0, 0), (1, 42), (255, 65535)],
    )
    def test_roundtrip(self, replica_id: int, counter: int) -> None:
        nid = NodeID(replica_id, counter)

        # Serialize
        state = NodeSerializer().dump(nid)
        assert state == {"replica_id": replica_id, "counter": counter}

        # Deserialize
        n_nid = NodeSerializer().load(json.loads(json.dumps(state)))

        # Assert
        assert isinstance(n_nid, NodeID)
        assert isinstance(n_nid.replica_id, int)
        assert isinstance(n_nid.counter, int)
        assert n_nid == nid


class TestSide:
    @pytest.mark.parametrize("side", [Side.LEFT, Side.RIGHT])
    def test_roundtrip(self, side: Side) -> None:
        # Serialize
        state = FugueSerializer.dump_side(side)
        assert state in (0, 1)

        # Deserialize
        n_side = FugueSerializer.load_side(json.loads(json.dumps(state)))

        # Assert
        assert isinstance(n_side, Side)
        assert n_side == side


class TestFugue:
    @pytest.mark.parametrize(
        "values",
        [[], ["a"], ["x", "y", "z"]],
    )
    def test_roundtrip(self, s: FugueSerializer[str, str], values: list[str]) -> None:
        fu = _fugue(*values)

        # Serialize
        state = s.dump(fu)
        assert state["values"] == values

        # Deserialize
        n_fu = s.load(json.loads(json.dumps(state)))

        # Assert
        assert isinstance(n_fu, Fugue)
        assert list(n_fu) == values
        assert n_fu.replica_id == fu.replica_id
        assert n_fu._counters == fu._counters
        assert all(isinstance(k, int) for k in n_fu._counters)

    def test_roundtrip_with_delete(self, s: FugueSerializer[str, str]) -> None:
        fu = _fugue("keep", "drop")
        fu.delete(1)

        # Serialize
        state = s.dump(fu)
        assert state["values"] == ["keep", "drop"]

        # Deserialize
        n_fu = s.load(json.loads(json.dumps(state)))

        # Assert
        assert isinstance(n_fu, Fugue)
        assert list(n_fu) == ["keep"]


class TestLWWRegister:
    @pytest.mark.parametrize(
        "assignments",
        [
            [],
            [("name", "Mix")],
            [("name", "Mix"), ("description", "Desc")],
            [("name", "A"), ("name", "B")],  # last write wins
        ],
    )
    def test_roundtrip(self, assignments: list[tuple[str, str]]) -> None:
        reg = LWWRegister(replica_id=0)
        for key, value in assignments:
            reg.assign(key, value)

        # Serialize
        state: LWWRegisterState[Any] = LWWSerializer().dump(reg)
        assert state["version"] == 1
        assert set(state) == {"version", "counter", "replica_id", "ops"}
        assert len(state["ops"]) == len(assignments)
        for op in state["ops"]:
            assert set(op) == {"node_id", "value", "key"}

        # Deserialize
        n_reg = LWWSerializer().load(json.loads(json.dumps(state)))

        # Assert
        assert isinstance(n_reg, LWWRegister)
        assert dict(n_reg) == dict(reg)
        assert n_reg.replica_id == reg.replica_id
        assert n_reg._counter == reg._counter

    def test_roundtrip_preserves_history(self) -> None:
        reg = LWWRegister(replica_id=1)
        reg.assign("name", "A")
        reg.assign("name", "B")

        # Serialize / Deserialize
        n_reg = LWWSerializer().load(json.loads(json.dumps(LWWSerializer().dump(reg))))

        # Assert
        assert n_reg["name"] == "B"
        assert [op.value for op in n_reg.history("name")] == ["A", "B"]


def _fugue(*values: str, replica_id: int = 0) -> Fugue[str]:
    fu = Fugue[str](replica_id=replica_id)
    for v in values:
        fu.insert(len(fu), v)
    return fu


def _nids(replica_id: int = 0, counter: int = 0) -> NodeIDState:
    return NodeIDState(replica_id=replica_id, counter=counter)


def _roundtrip(s: FugueSerializer[str, str], fu: Fugue[str]) -> Fugue[str]:
    return s.load(s.dump(fu))


@pytest.fixture
def s() -> FugueSerializer[str, str]:
    return FugueSerializer(DummySerializer())


class TestDump:
    def test_shape(self, s: FugueSerializer[str, str]) -> None:
        state = s.dump(_fugue("a"))
        assert state["version"] == 1
        assert set(state) == {"version", "replica_id", "counters", "ops", "values"}

    def test_delete_op(self, s: FugueSerializer[str, str]) -> None:
        fu = _fugue("keep", "drop")
        fu.delete(1)
        state = s.dump(fu)
        assert len(state["ops"]) == 3
        assert "value_ref" in state["ops"][0]
        assert "value_ref" in state["ops"][1]
        assert set(state["ops"][2]) == {"node_id"}

    def test_insert_op_shape(self, s: FugueSerializer[str, str]) -> None:
        fu = _fugue("x")
        op = cast("OpStateInsert", s.dump(fu)["ops"][0])
        for k in ("node_id", "parent_id", "side", "right_of_id", "value_ref"):
            assert k in op
        assert op["side"] in (0, 1)
        assert op["value_ref"] == 0

    @pytest.mark.parametrize(
        ("replica_id", "expected_counters"),
        [
            (0, {0: 2}),
            (7, {7: 2}),
        ],
    )
    def test_counters(
        self,
        s: FugueSerializer[str, str],
        replica_id: int,
        expected_counters: dict[int, int],
    ) -> None:
        fu = _fugue("a", "b", replica_id=replica_id)
        state = s.dump(fu)

        assert state["replica_id"] == replica_id
        assert isinstance(state["counters"], dict)
        for rid, counter in state["counters"].items():
            assert isinstance(rid, int)
            assert isinstance(counter, int)
        assert state["counters"] == expected_counters

    def test_multi_replica_counters(self, s: FugueSerializer[str, str]) -> None:
        a = _fugue("x", replica_id=1)
        b = _fugue(replica_id=2)
        b.apply(a.ops[0])
        state = s.dump(b)
        assert state["counters"] == {1: 1, 2: 0}

    def test_right_of_id_handling(self, s: FugueSerializer[str, str]) -> None:
        fu = _fugue("a", "b")
        fu.insert(1, "c")  # insert between a and b
        state = s.dump(fu)
        # right_of_id faithfully reproduced across roundtrip
        restate = s.dump(_roundtrip(s, fu))
        for o, r in zip(state["ops"], restate["ops"]):
            if "right_of_id" in o:
                assert (
                    cast("OpStateInsert", o)["right_of_id"]
                    == cast("OpStateInsert", r)["right_of_id"]
                )


def _state(
    *ops: OpStateInsert | OpStateDelete,
    replica_id: int = 0,
    counters: dict[int, int] | None = None,
    values: list[str] | None = None,
) -> FugueState[str]:
    return FugueState(
        version=1,
        replica_id=replica_id,
        counters=counters or {replica_id: 0},
        ops=list(ops),
        values=values or [],
    )


def _root() -> NodeIDState:
    return _nids(-1, -1)


def _insert(
    nid: NodeIDState,
    parent: NodeIDState | None = None,
    side: Literal[0, 1] = 1,
    right_of_id: NodeIDState | None = None,
    value_ref: int = 0,
) -> OpStateInsert:
    return OpStateInsert(
        node_id=nid,
        parent_id=parent or _root(),
        side=side,
        right_of_id=right_of_id,
        value_ref=value_ref,
    )


def _delete(nid: NodeIDState) -> OpStateDelete:
    return OpStateDelete(node_id=nid)


class TestLoad:
    def test_empty(self, s: FugueSerializer[str, str]) -> None:
        fu = s.load(_state())
        assert list(fu) == []
        assert len(fu) == 0

    def test_single_insert(self, s: FugueSerializer[str, str]) -> None:
        fu = s.load(_state(_insert(_nids()), values=["x"], counters={0: 1}))
        assert list(fu) == ["x"]

    def test_linear_chain(self, s: FugueSerializer[str, str]) -> None:
        fu = s.load(
            _state(
                _insert(_nids(0, 0), value_ref=0),
                _insert(_nids(0, 1), parent=_nids(0, 0), value_ref=1),
                _insert(_nids(0, 2), parent=_nids(0, 1), value_ref=2),
                values=["x", "y", "z"],
                counters={0: 3},
            )
        )
        assert list(fu) == ["x", "y", "z"]

    def test_insert_then_delete(self, s: FugueSerializer[str, str]) -> None:
        fu = s.load(
            _state(
                _insert(_nids(0, 0), value_ref=0),
                _insert(_nids(0, 1), parent=_nids(0, 0), value_ref=1),
                _delete(_nids(0, 0)),
                values=["a", "b"],
                counters={0: 2},
            )
        )
        assert list(fu) == ["b"]

    def test_left_child(self, s: FugueSerializer[str, str]) -> None:
        fu = s.load(
            _state(
                _insert(_nids(0, 1), value_ref=0),
                _insert(_nids(0, 0), parent=_nids(0, 1), side=0, value_ref=1),
                values=["parent", "child"],
                counters={0: 2},
            )
        )
        assert list(fu) == ["child", "parent"]

    def test_preserves_metadata(self, s: FugueSerializer[str, str]) -> None:
        fu = s.load(_state(replica_id=99, counters={1: 3, 2: 0}))
        assert fu.replica_id == 99
        assert fu._counters == {1: 3, 2: 0}


class TestRoundtrip:
    @pytest.mark.parametrize(
        "values",
        [
            [],
            ["a"],
            ["x", "y", "z"],
            ["c", "b", "a"],
            ["🎵", "  ", "\n", ""],
        ],
    )
    def test_preserves_order(
        self, s: FugueSerializer[str, str], values: list[str]
    ) -> None:
        fu = _fugue(*values)
        assert list(_roundtrip(s, fu)) == values

    @pytest.mark.parametrize(
        ("values", "deletes"),
        [
            (["a", "b", "c"], [1]),
            (["a", "b", "c", "d", "e"], [1, 2]),
            (["a", "b", "c"], [0, 0, 0]),
            (["x", "y"], [0]),
        ],
    )
    def test_with_deletes(
        self, s: FugueSerializer[str, str], values: list[str], deletes: list[int]
    ) -> None:
        fu = _fugue(*values)
        for idx in deletes:
            fu.delete(idx)
        assert list(_roundtrip(s, fu)) == list(fu)

    def test_large_sequence(self, s: FugueSerializer[str, str]) -> None:
        fu = Fugue[str]()
        for i in range(100):
            fu.insert(len(fu) if i % 10 else 0, str(i))
        restored = _roundtrip(s, fu)
        assert list(restored) == list(fu)
        assert len(restored) == len(fu)

    def test_idempotent(self, s: FugueSerializer[str, str]) -> None:
        fu = _fugue("a", "b")
        fu.delete(0)
        r1 = _roundtrip(s, fu)
        r2 = _roundtrip(s, r1)
        assert list(r2) == list(r1)

    def test_does_not_mutate(self, s: FugueSerializer[str, str]) -> None:
        fu = _fugue("a", "b")
        before = list(fu)
        _roundtrip(s, fu)
        assert list(fu) == before

    def test_unused_values_preserved_in_dump(
        self, s: FugueSerializer[str, str]
    ) -> None:
        """Deleted values remain in the values list (value_ref is still stable)."""
        fu = _fugue("a")
        fu.delete(0)
        fu.insert(0, "b")
        state = s.dump(fu)
        assert len(state["values"]) == 2

    def test_delete_only_state_is_valid(self, s: FugueSerializer[str, str]) -> None:
        fu = s.load(_state(_delete(_nids(1, 0))))
        assert list(fu) == []


class TestMultiReplica:
    def test_concurrent_inserts_converge(self, s: FugueSerializer[str, str]) -> None:
        a = _fugue("a", replica_id=1)
        b = _fugue("b", replica_id=2)
        for op in b.ops:
            a.apply(op)
        for op in a.ops:
            b.apply(op)
        assert list(_roundtrip(s, a)) == list(_roundtrip(s, b))

    def test_forked_survives_roundtrip(self, s: FugueSerializer[str, str]) -> None:
        fu = _fugue("a", "b", replica_id=1).fork(2)
        fu.insert(2, "c")
        restored = _roundtrip(s, fu)
        assert list(restored) == ["a", "b", "c"]
        assert restored.replica_id == 2

    def test_serialize_then_extend(self, s: FugueSerializer[str, str]) -> None:
        a = _fugue("hello", replica_id=1)
        b = _roundtrip(s, a)
        b.insert(1, "world")
        c: Fugue[str] = Fugue(replica_id=1)
        for op in b.ops:
            c.apply(op)
        assert list(c) == ["hello", "world"]
