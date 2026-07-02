"""Fugue — a list CRDT with interleaving of concurrent operations.

Based on *The Art of the Fugue* by Weidner & Kleppmann.
"""

from __future__ import annotations

from collections.abc import Iterator
from copy import deepcopy
from dataclasses import dataclass
from typing import Generic, TypeVar

from plistsync.crdt.graph import Graph, Node, NodeID, Side

T = TypeVar("T")


@dataclass(frozen=True)
class InsertOp(Generic[T]):
    """Serialisable insert — structural node + value."""

    node: Node
    value: T


@dataclass(frozen=True)
class DeleteOp:
    """Serialisable delete."""

    node_id: NodeID


class Fugue(Generic[T]):
    """Replicatable list with non-interleaving concurrent operations."""

    def __init__(self, replica_id: int = 0, initial_counter: int = 0) -> None:
        self.replica_id = replica_id
        self._counters: dict[int, int] = {replica_id: initial_counter}
        self._ops: list[InsertOp[T] | DeleteOp] = []
        self._values: dict[NodeID, T] = {}
        self._graph = Graph()

    def __len__(self) -> int:
        return len(self._graph)

    def __getitem__(self, index: int) -> T:
        if index < 0:
            index += len(self)
        return self._values[self._graph.nth_live(index)]

    def __iter__(self) -> Iterator[T]:
        for nid in self._graph.order():
            yield self._values[nid]

    @property
    def ops(self) -> list[InsertOp[T] | DeleteOp]:
        return self._ops

    def insert(self, index: int, value: T) -> InsertOp[T]:
        if not 0 <= index <= len(self):
            raise IndexError(index)
        op = self._make_insert(index, value)
        self._ops.append(op)
        return op

    def delete(self, index: int) -> DeleteOp:
        if index < 0:
            index += len(self)
        nid = self._graph.nth_live(index)
        self._graph.delete(nid)
        op = DeleteOp(node_id=nid)
        self._ops.append(op)
        return op

    def apply(self, op: InsertOp[T] | DeleteOp) -> None:
        """Apply a remote operation to this replica."""
        if isinstance(op, InsertOp):
            if op.node.id not in self._graph:
                rid = op.node.id.replica_id
                self._counters[rid] = max(
                    self._counters.get(rid, -1), op.node.id.counter + 1
                )
                self._graph.add(
                    Node(
                        id=op.node.id,
                        parent_id=op.node.parent_id,
                        side=op.node.side,
                        right_of_id=op.node.right_of_id,
                        _deleted=op.node._deleted,
                    )
                )
                self._values[op.node.id] = op.value
        else:
            self._graph.delete(op.node_id)
        self._ops.append(op)

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
        for op in self._ops:
            if isinstance(op, InsertOp):
                if op.node.id in visible:
                    new.apply(op)
            elif op.node_id in visible:
                new.apply(op)
        return new

    def _next_id(self) -> NodeID:
        c = self._counters.get(self.replica_id, 0)
        self._counters[self.replica_id] = c + 1
        return NodeID(self.replica_id, c)

    def _make_insert(self, index: int, value: T) -> InsertOp[T]:
        nid = self._next_id()
        g = self._graph

        if index == len(g):
            # Fast path: append (also covers the first element, len==0).
            left = g._full_order[-1] if g._full_order else NodeID.root()
            node = Node(id=nid, parent_id=left, side=Side.RIGHT, right_of_id=None)
            g.fast_append(node)
        else:
            left = NodeID.root() if index == 0 else g.nth_live(index - 1)
            right = g.right_origin(left)

            if not g.has_right(left):
                node = Node(id=nid, parent_id=left, side=Side.RIGHT, right_of_id=right)
            elif right is None:
                raise RuntimeError("right_origin is None but left has right children")
            else:
                node = Node(id=nid, parent_id=right, side=Side.LEFT)

            g.add(node)

        self._values[nid] = value
        return self._op(node, value)

    @staticmethod
    def _op(node: Node, value: T) -> InsertOp[T]:
        """Build a serialisable InsertOp (strips internal ``_deleted``)."""
        return InsertOp(
            node=Node(
                id=node.id,
                parent_id=node.parent_id,
                side=node.side,
                right_of_id=node.right_of_id,
            ),
            value=value,
        )
