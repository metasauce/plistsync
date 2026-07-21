from __future__ import annotations

from abc import abstractmethod
from typing import Generic, Literal, Protocol, TypedDict, TypeVar, cast

from .fugue import DeleteOp, Fugue, InsertOp, InsertPos
from .graph import NodeID, Side

T = TypeVar("T")
S = TypeVar("S")


class Serializer(Protocol, Generic[T, S]):
    @abstractmethod
    def dump(self, value: T) -> S:
        """Serialize a Fugue instance to a string."""
        raise NotImplementedError

    @abstractmethod
    def load(self, data: S) -> T:
        """Deserialize a Fugue instance from a string."""
        raise NotImplementedError


class NodeIDState(TypedDict):
    """Snapshot format for a Fugue node ID.

    Used for serialization and deserialization.
    """

    replica_id: int
    """Unique identifier for the replica that produced this node ID."""

    counter: int
    """Counter value for the node ID."""


class OpStateInsert(TypedDict):
    """Snapshot format for a Fugue operation.

    Used for serialization and deserialization.
    """

    node_id: NodeIDState
    """Index at which the operation is applied."""

    parent_id: NodeIDState
    """Parent index for the operation (if applicable, in inserts)."""

    side: Literal[0, 1]
    """Side of the parent for the operation (if applicable, in inserts).
    0 for left, 1 for right."""

    right_of_id: NodeIDState | None
    """Reference to the node ID that this operation is to the right of
    (if applicable, in inserts)."""

    value_ref: int
    """Reference to the serialized items index (if applicable, in inserts).
    See values list below."""


class OpStateDelete(TypedDict):
    """Snapshot format for a Fugue operation.

    Used for serialization and deserialization.
    """

    node_id: NodeIDState
    """Index at which the operation is applied."""


class FugueState(TypedDict, Generic[S]):
    version: int
    """Version of the serialized state. Used for compatibility checks."""

    replica_id: int
    """Unique identifier for the replica that produced this state."""

    counters: dict[int, int]
    """Mapping of replica IDs to their respective counters."""

    ops: list[OpStateInsert | OpStateDelete]
    """List of operations (insertions and deletions) in the Fugue."""

    values: list[S]
    """Mapping of value IDs to their respective values."""


class FugueSerializer(Serializer[Fugue[T], FugueState[S]], Generic[T, S]):
    """Serializer for Fugue instances, using a provided serializer for the values."""

    serializer: Serializer[T, S]

    def __init__(self, serializer: Serializer[T, S]) -> None:
        self.serializer = serializer

    def dump(self, value: Fugue[T]) -> FugueState[S]:
        values: list[S] = []
        ops: list[OpStateInsert | OpStateDelete] = []

        for op in value.ops:
            if isinstance(op, InsertOp):
                values.append(self.serializer.dump(op.value))
                ops.append(
                    OpStateInsert(
                        node_id=self.dump_node_id(op.pos.id),
                        parent_id=self.dump_node_id(op.pos.parent_id),
                        side=self.dump_side(op.pos.side),
                        right_of_id=self.dump_node_id(op.pos.right_of_id)
                        if op.pos.right_of_id
                        else None,
                        value_ref=len(values) - 1,
                    )
                )
            else:
                ops.append(
                    OpStateDelete(
                        node_id=self.dump_node_id(op.node_id),
                    )
                )

        return FugueState(
            version=1,
            replica_id=value.replica_id,
            counters=value._counters,
            ops=ops,
            values=values,
        )

    def load(self, data: FugueState[S]) -> Fugue[T]:
        fugue = Fugue[T](replica_id=data["replica_id"])
        fugue._counters = dict(data["counters"])
        values = data["values"]
        for op in data["ops"]:
            if "value_ref" in op:  # insert
                ins = cast("OpStateInsert", op)
                value = self.serializer.load(values[ins["value_ref"]])
                fugue.apply(
                    InsertOp(
                        pos=InsertPos(
                            id=self.load_node_id(ins["node_id"]),
                            parent_id=self.load_node_id(ins["parent_id"]),
                            side=self.load_side(ins["side"]),
                            right_of_id=self.load_node_id(ins["right_of_id"])
                            if ins["right_of_id"]
                            else None,
                        ),
                        value=value,
                    )
                )
            else:  # delete
                fugue.apply(
                    DeleteOp(
                        node_id=self.load_node_id(op["node_id"]),
                    )
                )

        return fugue

    @staticmethod
    def dump_node_id(node_id: NodeID) -> NodeIDState:
        return NodeIDState(
            replica_id=node_id.replica_id,
            counter=node_id.counter,
        )

    @staticmethod
    def load_node_id(node_id: NodeIDState) -> NodeID:
        return NodeID(
            replica_id=node_id["replica_id"],
            counter=node_id["counter"],
        )

    @staticmethod
    def dump_side(side: Side) -> Literal[0, 1]:
        return 0 if side == Side.LEFT else 1

    @staticmethod
    def load_side(side: Literal[0, 1]) -> Side:
        return Side.LEFT if side == 0 else Side.RIGHT
