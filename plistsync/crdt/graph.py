"""Graph topology for Fugue.

The :class:`Graph` is an in-order tree with left/right children and
FugueMax sibling ordering.  It knows nothing about payloads, replicas,
counters, or operation logs.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum, auto
from functools import cache

_END = 2**63  # sentinel for "no right origin"


@dataclass(frozen=True, order=True)
class NodeID:
    """Globally unique element ID, ordered lexicographically."""

    replica_id: int
    counter: int

    @classmethod
    @cache
    def root(cls) -> NodeID:
        """Return a NodeID that is less than any other NodeID."""
        return cls(-1, -1)


class Side(Enum):
    LEFT = auto()
    RIGHT = auto()


@dataclass
class Node:
    """A structural node — topology only, no value."""

    id: NodeID
    parent_id: NodeID
    side: Side
    right_of_id: NodeID | None = None
    _deleted: bool = False


class Graph:
    """In-order tree with left/right children and FugueMax sibling ordering.

    Knows nothing about values, replicas, counters, or operation logs —
    just node topology and traversal order.
    """

    _nodes: dict[NodeID, Node]
    _left: defaultdict[NodeID, list[NodeID]]
    _right: defaultdict[NodeID, list[NodeID]]
    __slots__ = ("_nodes", "_left", "_right")

    def __init__(self) -> None:
        self._nodes = {}
        self._left = defaultdict(list)
        self._right = defaultdict(list)

    def add(self, node: Node) -> None:
        """Insert *node* into the tree at its declared parent/side."""
        if node.id in self._nodes:
            return
        self._nodes[node.id] = node
        if node.side is Side.RIGHT:
            self._insert_right(node.parent_id, node)
        else:
            self._insert_left(node.parent_id, node)

    def delete(self, node_id: NodeID) -> None:
        """Mark *node_id* as deleted (tombstone)."""
        try:
            self._nodes[node_id]._deleted = True
        except KeyError:
            pass

    def order(self) -> list[NodeID]:
        """Live NodeIDs in in-order traversal."""
        out: list[NodeID] = []
        self._traverse(NodeID.root(), out)
        return out

    def __len__(self) -> int:
        return sum(1 for _ in self._iter_live())

    def full_order(self) -> list[NodeID]:
        """All NodeIDs in traversal order, including tombstones."""
        out: list[NodeID] = []
        self._traverse_full(NodeID.root(), out)
        return out

    def has_right(self, node_id: NodeID) -> bool:
        """Return True if *node_id* has any right children."""
        return bool(self._right[node_id])

    def nth_live(self, index: int) -> NodeID:
        """NodeID of the *index*-th live element (0-based)."""
        for i, n in enumerate(self._iter_live()):
            if i == index:
                return n.id
        raise IndexError(index)

    def right_origin(self, left_id: NodeID) -> NodeID | None:
        """NodeID immediately after *left_id* in full traversal."""
        full = self.full_order()
        try:
            if left_id == NodeID.root():
                return full[0] if full else None
            i = full.index(left_id)
            return full[i + 1] if i + 1 < len(full) else None
        except (ValueError, IndexError):
            return None

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def _traverse(self, parent: NodeID, out: list[NodeID]) -> None:
        for cid in self._left[parent]:
            self._traverse(cid, out)
        if parent != NodeID.root() and not self._nodes[parent]._deleted:
            out.append(parent)
        for cid in self._right[parent]:
            self._traverse(cid, out)

    def _iter_live(self) -> Iterator[Node]:
        yield from self._iter_subtree(NodeID.root())

    def _iter_subtree(self, parent: NodeID) -> Iterator[Node]:
        for cid in self._left[parent]:
            yield from self._iter_subtree(cid)
        if parent != NodeID.root():
            n = self._nodes[parent]
            if not n._deleted:
                yield n
        for cid in self._right[parent]:
            yield from self._iter_subtree(cid)

    def _traverse_full(self, parent: NodeID, out: list[NodeID]) -> None:
        for cid in self._left[parent]:
            self._traverse_full(cid, out)
        if parent != NodeID.root():
            out.append(parent)
        for cid in self._right[parent]:
            self._traverse_full(cid, out)

    def _insert_left(self, pid: NodeID, node: Node) -> None:
        children = self._left[pid]
        # left-side siblings: lexicographic by ID
        i = 0
        while i < len(children) and children[i] < node.id:
            i += 1
        children.insert(i, node.id)

    def _insert_right(self, pid: NodeID, node: Node) -> None:
        children = self._right[pid]
        # FugueMax: descending right-origin position, then ID
        positions = self._positions()
        my_ro = (
            positions.get(node.right_of_id, -1)
            if node.right_of_id is not None
            else _END
        )
        i = 0
        while i < len(children):
            child = self._nodes[children[i]]
            their_ro = (
                positions.get(child.right_of_id, -1)
                if child.right_of_id is not None
                else _END
            )
            if my_ro > their_ro or (my_ro == their_ro and node.id < children[i]):
                break
            i += 1
        children.insert(i, node.id)

    def _positions(self) -> dict[NodeID, int]:
        """Map every element ID to its position in the full traversal."""
        return {nid: i for i, nid in enumerate(self.full_order())}
