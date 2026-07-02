"""Graph topology for Fugue — in-order tree with left/right children.

Maintains full-order and live-order lists incrementally so that
``full_order()``, ``order()``, ``nth_live()`` and ``__len__`` are O(1).
Subtree sizes are computed lazily with versioned caching.
"""

from __future__ import annotations

from collections import defaultdict
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
        return cls(-1, -1)


class Side(Enum):
    LEFT = auto()
    RIGHT = auto()


@dataclass
class Node:
    """Structural node — topology only, no payload."""

    id: NodeID
    parent_id: NodeID
    side: Side
    right_of_id: NodeID | None = None
    _deleted: bool = False


class Graph:
    """In-order tree with FugueMax sibling ordering."""

    __slots__ = (
        "_full_order",
        "_global_version",
        "_left",
        "_live_order",
        "_nodes",
        "_right",
        "_subtree_sizes",
        "_subtree_versions",
    )

    def __init__(self) -> None:
        self._nodes: dict[NodeID, Node] = {}
        self._left: defaultdict[NodeID, list[NodeID]] = defaultdict(list)
        self._right: defaultdict[NodeID, list[NodeID]] = defaultdict(list)
        self._full_order: list[NodeID] = []
        self._live_order: list[NodeID] = []
        self._subtree_sizes: dict[NodeID, int] = {}
        self._subtree_versions: dict[NodeID, int] = {}
        self._global_version = 0

    def add(self, node: Node) -> None:
        """Insert *node* at its declared parent/side (general path)."""
        if node.id in self._nodes:
            return

        self._nodes[node.id] = node
        self._subtree_sizes[node.id] = 1

        full_pos = (
            self._insert_right(node.parent_id, node)
            if node.side is Side.RIGHT
            else self._insert_left(node.parent_id, node)
        )

        self._full_order.insert(full_pos, node.id)
        self._live_order.insert(full_pos, node.id)
        self._global_version += 1

    def fast_append(self, node: Node) -> None:
        """O(1) append — caller guarantees right child of last element, no siblings."""
        if node.id in self._nodes:
            return
        self._nodes[node.id] = node

        pid = self._full_order[-1] if self._full_order else NodeID.root()
        self._right[pid].append(node.id)
        self._full_order.append(node.id)
        self._live_order.append(node.id)
        self._global_version += 1

    def delete(self, node_id: NodeID) -> None:
        """Mark *node_id* as deleted (tombstone)."""
        try:
            n = self._nodes[node_id]
        except KeyError:
            return
        if not n._deleted:
            n._deleted = True
            self._live_order.remove(node_id)

    def __contains__(self, node_id: NodeID) -> bool:
        return node_id in self._nodes

    def __len__(self) -> int:
        return len(self._live_order)

    def order(self) -> list[NodeID]:
        return self._live_order

    def full_order(self) -> list[NodeID]:
        return self._full_order

    def has_right(self, node_id: NodeID) -> bool:
        return bool(self._right[node_id])

    def nth_live(self, index: int) -> NodeID:
        return self._live_order[index]

    def right_origin(self, left_id: NodeID) -> NodeID | None:
        """NodeID immediately after *left_id* in full traversal."""
        full = self._full_order
        if left_id == NodeID.root():
            return full[0] if full else None
        try:
            i = full.index(left_id)
            return full[i + 1] if i + 1 < len(full) else None
        except ValueError:
            return None

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def ancestor_closure(self, nid: NodeID) -> frozenset[NodeID]:
        """Return *nid* and all its ancestors (transitive parent chain)."""
        nodes = self._nodes
        root = NodeID.root()
        result: set[NodeID] = set()
        cur = nid
        while cur != root and cur not in result:
            result.add(cur)
            cur = nodes[cur].parent_id
        return frozenset(result)

    @staticmethod
    def _ro_pos(full: list[NodeID], right_of_id: NodeID | None) -> int:
        """Right-origin position, or ``_END`` if absent."""
        if right_of_id is None:
            return _END
        try:
            return full.index(right_of_id)
        except ValueError:
            return -1

    def _subtree_size(self, nid: NodeID) -> int:
        """Return the subtree node count for *nid* (iterative, version-cached)."""
        ver = self._subtree_versions.get(nid, -1)
        if ver == self._global_version:
            return self._subtree_sizes[nid]

        cur = self._global_version
        stack: list[tuple[NodeID, bool]] = [(nid, False)]
        while stack:
            pid, done = stack.pop()
            if not done:
                stack.append((pid, True))
                for cid in reversed(self._right.get(pid, ())):
                    if self._subtree_versions.get(cid, -1) != cur:
                        stack.append((cid, False))
                for cid in reversed(self._left.get(pid, ())):
                    if self._subtree_versions.get(cid, -1) != cur:
                        stack.append((cid, False))
            else:
                size = 1
                for cid in self._left.get(pid, ()):
                    size += self._subtree_sizes.get(cid, 0)
                for cid in self._right.get(pid, ()):
                    size += self._subtree_sizes.get(cid, 0)
                self._subtree_sizes[pid] = size
                self._subtree_versions[pid] = cur
        return self._subtree_sizes[nid]

    def _insert_left(self, pid: NodeID, node: Node) -> int:
        """Insert *node* as left child of *pid*; return full-order position."""
        children = self._left[pid]
        i = 0
        while i < len(children) and children[i] < node.id:
            i += 1

        anchor = pid if i == 0 else children[i - 1]

        if anchor == NodeID.root():
            full_pos = 0
        else:
            base = self._full_order.index(anchor)
            full_pos = base if anchor == pid else base + self._subtree_size(anchor)

        children.insert(i, node.id)
        return full_pos

    def _insert_right(self, pid: NodeID, node: Node) -> int:
        """Insert *node* as right child of *pid*; return full-order position."""
        children = self._right[pid]
        full = self._full_order

        my_ro = self._ro_pos(full, node.right_of_id)
        i = 0
        while i < len(children):
            child = self._nodes[children[i]]
            their_ro = self._ro_pos(full, child.right_of_id)
            if my_ro > their_ro or (my_ro == their_ro and node.id < children[i]):
                break
            i += 1

        base = -1 if pid == NodeID.root() else full.index(pid)
        full_pos = base + 1 + sum(self._subtree_size(children[j]) for j in range(i))

        children.insert(i, node.id)
        return full_pos
