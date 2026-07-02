from plistsync.crdt.graph import Graph, Node, NodeID, Side


def _node(counter: int, parent: NodeID, side: Side) -> Node:
    return Node(id=NodeID(0, counter), parent_id=parent, side=side)


class TestGraph:
    def test_empty(self) -> None:
        g = Graph()
        assert g.order() == []
        assert len(g) == 0

    def test_add_and_traverse(self) -> None:
        g = Graph()
        g.add(_node(0, NodeID.root(), Side.RIGHT))
        g.add(_node(1, NodeID(0, 0), Side.RIGHT))
        assert g.order() == [NodeID(0, 0), NodeID(0, 1)]
        assert g.node_count == 2

    def test_delete(self) -> None:
        g = Graph()
        g.add(_node(0, NodeID.root(), Side.RIGHT))
        g.add(_node(1, NodeID(0, 0), Side.RIGHT))
        g.delete(NodeID(0, 0))
        assert g.order() == [NodeID(0, 1)]

    def test_full_order_includes_tombstones(self) -> None:
        g = Graph()
        g.add(_node(0, NodeID.root(), Side.RIGHT))
        g.add(_node(1, NodeID(0, 0), Side.RIGHT))
        g.delete(NodeID(0, 0))
        assert len(g.full_order()) == 2
        assert NodeID(0, 0) in g.full_order()

    def test_has_right(self) -> None:
        g = Graph()
        g.add(_node(0, NodeID.root(), Side.RIGHT))
        g.add(_node(1, NodeID(0, 0), Side.RIGHT))
        assert g.has_right(NodeID(0, 0))
