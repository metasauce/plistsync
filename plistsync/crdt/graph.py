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

    Maintains the full-order and live-order lists incrementally so that
    ``full_order()``, ``order()``, ``nth_live()`` and ``__len__`` are all
    O(1).  Subtree sizes are computed lazily and cached — they are only
    needed for non-append inserts.
    """

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
        # Subtree sizes are computed lazily; 1 means "leaf, may have children".
        self._subtree_sizes: dict[NodeID, int] = {}

    # ------------------------------------------------------------------
    # mutation
    # ------------------------------------------------------------------

    def add(self, node: Node) -> None:
        """Insert *node* into the tree at its declared parent/side.

        Computes the insertion position from the tree structure *before*
        linking, then updates the order lists incrementally.
        """
        if node.id in self._nodes:
            return

        self._nodes[node.id] = node
        self._subtree_sizes[node.id] = 1

        if node.side is Side.RIGHT:
            full_pos = self._insert_right(node.parent_id, node)
        else:
            full_pos = self._insert_left(node.parent_id, node)

        self._full_order.insert(full_pos, node.id)
        self._live_order.insert(full_pos, node.id)
        # Lazy invalidation: just bump the version.  Subtree sizes are
        # checked against this on query; no ancestor walk needed.
        self._global_version += 1

    def fast_append(self, node: Node) -> None:
        """O(1) fast path: append *node* at the end of the list.

        The caller guarantees that *node* is a right child of the current
        last element (or root), has ``right_of_id=None``, and has no
        siblings to sort against.  Skips all positional lookups, subtree-
        size tracking, and cache invalidation.
        """
        if node.id in self._nodes:
            return
        self._nodes[node.id] = node

        if self._full_order:
            pid = self._full_order[-1]
        else:
            pid = NodeID.root()

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

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._live_order)

    def order(self) -> list[NodeID]:
        """Live NodeIDs in in-order traversal."""
        return self._live_order

    def full_order(self) -> list[NodeID]:
        """All NodeIDs in traversal order, including tombstones."""
        return self._full_order

    def has_right(self, node_id: NodeID) -> bool:
        """Return True if *node_id* has any right children."""
        return bool(self._right[node_id])

    def nth_live(self, index: int) -> NodeID:
        """NodeID of the *index*-th live element (0-based)."""
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

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _index(self, nid: NodeID) -> int:
        """Position of *nid* in ``_full_order`` (C-level ``list.index``)."""
        return self._full_order.index(nid)

    def _index_or(self, nid: NodeID | None, default: int) -> int:
        """Like ``_index``, but returns *default* for ``None`` or absent keys."""
        if nid is None:
            return default
        try:
            return self._full_order.index(nid)
        except ValueError:
            return default

    def _subtree_size(self, nid: NodeID) -> int:
        """Number of nodes in the subtree rooted at *nid* (lazy, cached).

        Only called during non-append inserts (rare); for appends this is
        never invoked, so the ancestor-chain invalidation in ``add()`` is
        the only cost.
        """
        sz = self._subtree_sizes.get(nid)
        if (
            sz is not None
            and self._subtree_versions.get(nid, -1) == self._global_version
        ):
            return sz
        # Iterative post-order DFS to avoid recursion-depth issues.
        stack: list[tuple[NodeID, bool]] = [(nid, False)]
        while stack:
            pid, done = stack.pop()
            if not done:
                stack.append((pid, True))
                for cid in reversed(self._right.get(pid, ())):
                    if self._subtree_versions.get(cid, -1) != self._global_version:
                        stack.append((cid, False))
                for cid in reversed(self._left.get(pid, ())):
                    if self._subtree_versions.get(cid, -1) != self._global_version:
                        stack.append((cid, False))
            else:
                size = 1
                for cid in self._left.get(pid, ()):
                    size += self._subtree_sizes.get(cid, 0)
                for cid in self._right.get(pid, ()):
                    size += self._subtree_sizes.get(cid, 0)
                self._subtree_sizes[pid] = size
                self._subtree_versions[pid] = self._global_version
        return self._subtree_sizes[nid]

    def _insert_left(self, pid: NodeID, node: Node) -> int:
        """Insert *node* as a left child of *pid*, returning full-order position."""
        children = self._left[pid]
        i = 0
        while i < len(children) and children[i] < node.id:
            i += 1

        if i == 0:
            anchor = pid
        else:
            anchor = children[i - 1]

        if anchor == NodeID.root():
            full_pos = 0
        else:
            base = self._index(anchor)
            if anchor == pid:
                full_pos = base
            else:
                full_pos = base + self._subtree_size(anchor)

        children.insert(i, node.id)
        return full_pos

    def _insert_right(self, pid: NodeID, node: Node) -> int:
        """Insert *node* as a right child of *pid*, returning full-order position."""
        children = self._right[pid]

        my_ro = self._index_or(node.right_of_id, _END)
        my_ro = (
            positions.get(node.right_of_id, -1)
            if node.right_of_id is not None
            else _END
        )
        i = 0
        while i < len(children):
            child = self._nodes[children[i]]
            their_ro = self._index_or(child.right_of_id, _END)
            if my_ro > their_ro or (my_ro == their_ro and node.id < children[i]):
                break
            i += 1

        if pid == NodeID.root():
            base = -1
        else:
            base = self._index(pid)
        full_pos = base + 1
        for j in range(i):
            full_pos += self._subtree_size(children[j])

        children.insert(i, node.id)
        return full_pos

    # ------------------------------------------------------------------
    # legacy
    # ------------------------------------------------------------------

    def _iter_live(self) -> Iterator[Node]:
        """Iterator over live nodes."""
        for nid in self._live_order:
            yield self._nodes[nid]
