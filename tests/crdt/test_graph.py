from plistsync.crdt.graph import Graph, Node, NodeID, Side

import pytest


def _node(counter: int, parent: NodeID, side: Side) -> Node:
    return Node(id=NodeID(0, counter), parent_id=parent, side=side)


def _linear_graph(length: int) -> Graph:
    """Right-linear chain of *length* nodes: 0 → 1 → … → length-1."""
    g = Graph()
    prev = NodeID.root()
    for i in range(length):
        g.add(_node(i, prev, Side.RIGHT))
        prev = NodeID(0, i)
    return g


class TestGraphEmpty:
    def test_initial_state(self) -> None:
        g = Graph()
        assert g.order() == []
        assert g.full_order() == []
        assert len(g) == 0
        assert g.node_count == 0

    @pytest.mark.parametrize("nid", [NodeID(0, 0), NodeID.root()])
    def test_contains_and_has_right(self, nid: NodeID) -> None:
        g = Graph()
        assert nid not in g
        assert not g.has_right(nid)

    def test_nth_live_and_right_origin(self) -> None:
        g = Graph()
        with pytest.raises(IndexError):
            g.nth_live(0)
        assert g.right_origin(NodeID.root()) is None


class TestGraphAdd:
    @pytest.mark.parametrize("side", [Side.LEFT, Side.RIGHT])
    def test_single_root_child(self, side: Side) -> None:
        g = Graph()
        g.add(_node(0, NodeID.root(), side))
        assert g.order() == [NodeID(0, 0)]

    def test_duplicate_idempotent(self) -> None:
        g = Graph()
        n = _node(0, NodeID.root(), Side.RIGHT)
        g.add(n)
        g.add(n)
        g.fast_append(n)
        assert g.order() == [NodeID(0, 0)]
        assert g.node_count == 1

    def test_child_positioning(self) -> None:
        g = Graph()
        g.add(_node(1, NodeID.root(), Side.RIGHT))
        g.add(_node(0, NodeID(0, 1), Side.LEFT))  # left before parent
        assert g.order() == [NodeID(0, 0), NodeID(0, 1)]
        g.add(_node(2, NodeID(0, 1), Side.RIGHT))  # right after parent
        assert g.order() == [NodeID(0, 0), NodeID(0, 1), NodeID(0, 2)]

    def test_fast_append(self) -> None:
        g = Graph()
        for i in range(3):
            g.fast_append(_node(i, NodeID.root(), Side.RIGHT))
        assert g.order() == [NodeID(0, 0), NodeID(0, 1), NodeID(0, 2)]


class TestGraphDelete:
    def test_basic_delete(self) -> None:
        g = _linear_graph(3)
        g.delete(NodeID(0, 1))
        g.delete(NodeID(0, 99))  # non-existent → no-op
        assert g.order() == [NodeID(0, 0), NodeID(0, 2)]

    def test_double_delete_and_contains(self) -> None:
        g = _linear_graph(2)
        g.delete(NodeID(0, 0))
        g.delete(NodeID(0, 0))
        assert g.order() == [NodeID(0, 1)]
        assert NodeID(0, 0) in g  # deleted nodes remain in _nodes
        assert NodeID(0, 99) not in g

    def test_tombstones(self) -> None:
        g = _linear_graph(3)
        g.delete(NodeID(0, 0))
        g.delete(NodeID(0, 2))
        assert g.full_order() == [NodeID(0, 0), NodeID(0, 1), NodeID(0, 2)]
        assert g.order() == [NodeID(0, 1)]
        assert len(g) == 1
        assert g.node_count == 3

    def test_delete_all(self) -> None:
        g = _linear_graph(3)
        for i in range(3):
            g.delete(NodeID(0, i))
        assert g.order() == []
        assert len(g) == 0
        assert g.node_count == 3


class TestGraphTraversal:
    @pytest.mark.parametrize(
        "nid, expected",
        [
            (NodeID.root(), True),  # root has n0 as right child
            (NodeID(0, 0), True),  # n0 has n1 as right child
            (NodeID(0, 1), False),  # n1 is a leaf
        ],
    )
    def test_has_right(self, nid: NodeID, expected: bool) -> None:
        assert _linear_graph(2).has_right(nid) is expected

    def test_nth_live(self) -> None:
        g = _linear_graph(5)
        assert g.nth_live(0) == NodeID(0, 0)
        assert g.nth_live(4) == NodeID(0, 4)
        assert g.nth_live(-1) == NodeID(0, 4)
        with pytest.raises(IndexError):
            g.nth_live(5)

    @pytest.mark.parametrize(
        "size, query, expected",
        [
            (3, NodeID.root(), NodeID(0, 0)),  # first element
            (3, NodeID(0, 1), NodeID(0, 2)),  # middle → next
            (2, NodeID(0, 1), None),  # last element
            (2, NodeID(0, 99), None),  # unknown
        ],
    )
    def test_right_origin(
        self, size: int, query: NodeID, expected: NodeID | None
    ) -> None:
        assert _linear_graph(size).right_origin(query) == expected


class TestGraphAncestors:
    def test_ancestor_closure(self) -> None:
        g = _linear_graph(3)
        assert g.ancestor_closure(NodeID(0, 2)) == frozenset(
            {NodeID(0, 0), NodeID(0, 1), NodeID(0, 2)}
        )
        assert g.ancestor_closure(NodeID(0, 0)) == frozenset({NodeID(0, 0)})
        assert NodeID.root() not in g.ancestor_closure(NodeID(0, 1))


class TestGraphComplex:
    def test_forked_order(self) -> None:
        g = Graph()
        g.add(_node(0, NodeID.root(), Side.LEFT))
        g.add(_node(1, NodeID.root(), Side.RIGHT))
        g.add(_node(2, NodeID(0, 1), Side.RIGHT))
        assert g.order() == [NodeID(0, 1), NodeID(0, 2), NodeID(0, 0)]

    @pytest.mark.parametrize("side", [Side.LEFT, Side.RIGHT])
    @pytest.mark.parametrize(
        "counters",
        [
            (1, 0),  # higher first, then lower → lower sorts before
            (0, 1),  # lower first, then higher → higher sorts after
        ],
    )
    def test_sibling_ordering(self, side: Side, counters: tuple[int, int]) -> None:
        """Siblings with equal right_of_id (None) are ordered by NodeID."""
        first, second = counters
        g = Graph()
        g.add(_node(first, NodeID.root(), side))
        g.add(_node(second, NodeID.root(), side))
        assert g.order() == [NodeID(0, 0), NodeID(0, 1)]

    def test_three_right_siblings(self) -> None:
        g = Graph()
        g.add(_node(0, NodeID.root(), Side.RIGHT))
        g.add(_node(2, NodeID.root(), Side.RIGHT))
        g.add(_node(1, NodeID.root(), Side.RIGHT))
        assert g.order() == [NodeID(0, 0), NodeID(0, 1), NodeID(0, 2)]

    def test_right_of_id(self) -> None:
        g = Graph()
        g.add(_node(1, NodeID.root(), Side.RIGHT))
        n0 = Node(
            id=NodeID(0, 0),
            parent_id=NodeID.root(),
            side=Side.RIGHT,
            right_of_id=NodeID(0, 1),
        )
        g.add(n0)
        assert g.order() == [NodeID(0, 1), NodeID(0, 0)]

    def test_subtree_with_left_and_right_children(self) -> None:
        g = Graph()
        g.add(_node(0, NodeID.root(), Side.RIGHT))
        g.add(_node(1, NodeID(0, 0), Side.LEFT))
        g.add(_node(2, NodeID(0, 0), Side.RIGHT))
        g.add(_node(3, NodeID.root(), Side.RIGHT))
        assert g.order() == [NodeID(0, 1), NodeID(0, 0), NodeID(0, 2), NodeID(0, 3)]

    def test_node_count(self) -> None:
        g = _linear_graph(5)
        g.delete(NodeID(0, 2))
        assert g.node_count == 5

    def test_insert_after_delete_uses_correct_live_position(self) -> None:
        """Adding a node after a deletion must land at the correct live index."""
        g = _linear_graph(4)
        g.delete(NodeID(0, 1))
        # Insert right child of NodeID(0,2): full_pos lands at 4,
        # but live_order has only 3 elements after the deletion.
        # The old bug would crash with IndexError on live_order.insert(4, _).
        g.add(_node(4, NodeID(0, 2), Side.RIGHT))
        assert g.order() == [NodeID(0, 0), NodeID(0, 2), NodeID(0, 3), NodeID(0, 4)]
