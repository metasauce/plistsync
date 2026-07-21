"""Fugue — a list CRDT with interleaving of concurrent operations.

Inspired by *The Art of the Fugue* by Weidner & Kleppmann.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from .graph import Graph, Node, NodeID, Side

if TYPE_CHECKING:
    from collections.abc import Iterator

T = TypeVar("T")


@dataclass(frozen=True)
class InsertPos:
    """Positional info needed to reconstruct a Node on a remote replica."""

    id: NodeID
    parent_id: NodeID
    side: Side
    right_of_id: NodeID | None = None


@dataclass(frozen=True)
class InsertOp(Generic[T]):
    """Serialisable insert — structural pos + value."""

    pos: InsertPos
    value: T

    @classmethod
    def from_node(cls, node: Node, value: T) -> InsertOp[T]:
        """Construct an InsertOp from a Node and value."""
        return cls(
            pos=InsertPos(
                id=node.id,
                parent_id=node.parent_id,
                side=node.side,
                right_of_id=node.right_of_id,
            ),
            value=value,
        )


@dataclass(frozen=True)
class DeleteOp:
    """Serialisable delete."""

    node_id: NodeID


class Ops(Generic[T]):
    """Operation list with value lookup."""

    _ops: list[InsertOp[T] | DeleteOp]

    # Refrence to the values for each node_id, for fast lookup during iteration.
    _values: dict[NodeID, T]

    def __init__(self) -> None:
        self._ops = []
        self._values = {}

    def get_value(self, node_id: NodeID) -> T:
        """Return the value for a given node_id."""
        try:
            return self._values[node_id]
        except KeyError:
            raise IndexError(node_id) from None

    def __getitem__(self, index: int) -> InsertOp[T] | DeleteOp:
        return self._ops[index]

    def __len__(self) -> int:
        return len(self._ops)

    def __iter__(self) -> Iterator[InsertOp[T] | DeleteOp]:
        return iter(self._ops)

    def append(self, op: InsertOp[T] | DeleteOp) -> None:
        self._ops.append(op)
        if isinstance(op, InsertOp):
            self._values[op.pos.id] = op.value

    def __add__(self, other: Ops[T]) -> Ops[T]:
        result: Ops[T] = Ops()
        for op in self:
            result.append(op)
        for op in other:
            result.append(op)
        return result

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Ops):
            return self._ops == other._ops
        if isinstance(other, list):
            return self._ops == other
        return NotImplemented

    __slot__ = ("_ops", "_values")


class Fugue(Generic[T]):
    """Replicatable list with non-interleaving concurrent operations."""

    # Holds all the data, order does not matter
    # we use graph as causal history to determine order of operations.
    ops: Ops[T]

    # The graph of nodes, used to determine order of operations.
    _graph: Graph

    # The id of this replica, used to generate unique node IDs.
    # TODO: Maybe we want to switch to strings here
    replica_id: int

    # List of replicas and their latest ingested counters. replicatid -> counter
    _counters: dict[int, int]

    def __init__(self, replica_id: int = 0, initial_counter: int = 0) -> None:
        self.replica_id = replica_id
        self._counters = {replica_id: initial_counter}
        self.ops = Ops()
        self._graph = Graph()

    def __len__(self) -> int:
        return len(self._graph)

    def __getitem__(self, index: int) -> T:
        if index < 0:
            index += len(self)
        return self.ops.get_value(self._graph.nth_live(index))

    def __iter__(self) -> Iterator[T]:
        for node_id in self._graph.order():
            yield self.ops.get_value(node_id)

    def insert(self, index: int, value: T) -> InsertOp[T]:
        if not 0 <= index <= len(self):
            raise IndexError(index)

        return self.__insert(index, value)

    def delete(self, index: int) -> DeleteOp:
        if not 0 <= index < len(self):
            raise IndexError(index)

        node_id = self._graph.nth_live(index)
        self._graph.delete(node_id)

        op = DeleteOp(node_id)
        self.ops.append(op)
        return op

    def apply(self, op: InsertOp[T] | DeleteOp) -> None:
        """Apply a remote operation to this replica."""
        if isinstance(op, InsertOp):
            if op.pos.id not in self._graph:
                rid = op.pos.id.replica_id
                self._counters[rid] = max(
                    self._counters.get(rid, -1), op.pos.id.counter + 1
                )
                self._graph.add(
                    Node(
                        id=op.pos.id,
                        parent_id=op.pos.parent_id,
                        side=op.pos.side,
                        right_of_id=op.pos.right_of_id,
                    )
                )
        else:
            self._graph.delete(op.node_id)

        self.ops.append(op)

    def version(self) -> NodeID:
        c = self._counters.get(self.replica_id, 0)
        return NodeID(self.replica_id, c)

    def fork(self, replica_id: int) -> Fugue[T]:
        """Return an independent copy with a new *replica_id*."""
        new = deepcopy(self)
        new.replica_id = replica_id
        return new

    def time_travel(self, version: NodeID) -> Fugue[T]:
        """Return a new replica containing only operations causally before *version*."""
        visible: set[NodeID] = set()
        root = NodeID.root()
        nodes = self._graph._nodes
        for nid in nodes:
            if nid.replica_id == version.replica_id and nid.counter < version.counter:
                cur = nid
                while cur != root and cur not in visible:
                    visible.add(cur)
                    cur = nodes[cur].parent_id

        new = Fugue[T](replica_id=self.replica_id)
        for op in self.ops:
            if isinstance(op, InsertOp):
                if op.pos.id in visible:
                    new.apply(op)
            elif op.node_id in visible:
                new.apply(op)
        return new

    def _next_id(self) -> NodeID:
        """Return the next unique NodeID for this replica."""
        c = self._counters.get(self.replica_id, 0)
        self._counters[self.replica_id] = c + 1
        return NodeID(self.replica_id, c)

    def __insert(self, index: int, value: T) -> InsertOp[T]:
        """Insert into graph and ops list."""
        node_id = self._next_id()
        g = self._graph

        if index == len(g):
            # Fast path: append (also covers the first element, len==0).
            left = g._full_order[-1] if g._full_order else NodeID.root()
            node = Node(
                id=node_id,
                parent_id=left,
                side=Side.RIGHT,
                right_of_id=None,
            )
            g.fast_append(node)
        else:
            # Slow path: insert at index (may be in the middle of the list).
            left = NodeID.root() if index == 0 else g.nth_live(index - 1)
            right = g.right_origin(left)

            if not g.has_right(left):
                node = Node(
                    id=node_id,
                    parent_id=left,
                    side=Side.RIGHT,
                    right_of_id=right,
                )
            elif right is None:
                raise RuntimeError("right_origin is None but left has right children")
            else:
                node = Node(id=node_id, parent_id=right, side=Side.LEFT)

            g.add(node)

        # Create operation and insert
        op = InsertOp.from_node(node, value)
        self.ops.append(op)
        return op
