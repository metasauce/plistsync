"""Tests for the FugueMax replicated list."""

from __future__ import annotations
from typing import Literal

import pytest

from plistsync.crdt import Fugue


class TestCore:
    @pytest.mark.parametrize(
        "operations, expected",
        [
            (
                # empty
                [],
                [],
            ),
            (
                # simple insert
                [
                    (0, "a", None),
                    (1, "b", None),
                    (2, "c", None),
                ],
                ["a", "b", "c"],
            ),
            (
                # prepend
                [
                    (0, "c", None),
                    (0, "b", None),
                    (0, "a", None),
                ],
                ["a", "b", "c"],
            ),
            (
                # insert middle
                [
                    (0, "a", None),
                    (1, "c", None),
                    (1, "b", None),
                ],
                ["a", "b", "c"],
            ),
            (
                # delete
                [
                    (0, "a", None),
                    (1, "b", None),
                    (2, "c", None),
                    (1, None, True),
                ],
                ["a", "c"],
            ),
        ],
    )
    def test_ops(
        self,
        operations: list[tuple[int, str | None, Literal[True] | None]],
        expected: list[str],
    ) -> None:
        fu: Fugue[str] = Fugue()
        for index, value, delete in operations:
            if value:
                fu.insert(index, value)
            if delete is not None:
                fu.delete(index)
        assert list(fu) == expected

    def test_getitem(self) -> None:
        fu: Fugue[str] = Fugue()
        for ch in "xyz":
            fu.insert(len(fu), ch)
        assert fu[0] == "x"
        assert fu[-1] == "z"
        with pytest.raises(IndexError):
            _ = fu[3]

    def test_insert_oob(self) -> None:
        with pytest.raises(IndexError):
            Fugue().insert(1, 42)

    def test_iter(self) -> None:
        fu: Fugue[int] = Fugue()
        for i in range(5):
            fu.insert(i, i)
        assert list(fu) == [0, 1, 2, 3, 4]


class TestNonInterleaving:
    def test_interleaving(self) -> None:
        base = Fugue[str](replica_id=0)
        a = base.fork(replica_id=1)
        b = base.fork(replica_id=2)

        # Concurrent edit
        ops_a = []
        for ch in "hello ":
            op = a.insert(len(a), ch)
            ops_a.append(op)

        ops_b = []
        for ch in "world":
            op = b.insert(len(b), ch)
            ops_b.append(op)

        # Ordering should be by replica id on conflict
        for op in ops_b + ops_a:
            base.apply(op)

        assert "".join(base) == "hello world"

    def test_convergence(self) -> None:
        a = Fugue[str](replica_id=1)
        b = Fugue[str](replica_id=2)

        for ch in "abc":
            a.insert(len(a), ch)
        for ch in "xyz":
            b.insert(len(b), ch)

        # Independent of the order we should arrive at the some final state
        m1 = Fugue[str]()
        for op in a.ops + b.ops:
            m1.apply(op)
        m2 = Fugue[str]()
        for op in b.ops + a.ops:
            m2.apply(op)
        assert list(m1) == list(m2)

    def test_idempotent(self) -> None:
        lst = Fugue[int]()
        op = lst.insert(0, 42)
        lst.apply(op)
        assert list(lst) == [42]
        assert lst._graph.node_count == 1
