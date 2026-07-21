"""Performance benchmarks for the Fugue CRDT — scaling behaviour.

Run with::

    python -m pytest tests/crdt/test_fugue_bench.py -v --benchmark-only

Each operation is parametrised across sizes so the benchmark table
directly shows the O(·) growth curve.
"""

from __future__ import annotations

import pytest

from plistsync.core.crdt import Fugue


# append: should be O(1) amortised
@pytest.mark.parametrize("n", [100, 500, 2_000, 10_000])
def test_append_scale(benchmark, n: int) -> None:
    """Sequential appends (fast path) — µs/op should stay ~constant."""

    def run() -> Fugue[int]:
        fu: Fugue[int] = Fugue()
        for i in range(n):
            fu.insert(i, i)
        return fu

    result = benchmark(run)
    assert len(result) == n


# delete: O(n) per op  →  O(n²) total for n deletes
@pytest.mark.parametrize("n", [100, 300, 600])
def test_delete_half_from_middle(benchmark, n: int) -> None:
    """Delete n/2 elements from the middle of an n-element list."""

    def run() -> Fugue[int]:
        fu: Fugue[int] = Fugue()
        for i in range(n):
            fu.insert(i, i)
        for _ in range(n // 2):
            fu.delete(len(fu) // 2)
        return fu

    result = benchmark(run)
    assert len(result) == n - n // 2


@pytest.mark.parametrize("n", [100, 300, 600])
def test_delete_half_from_front(benchmark, n: int) -> None:
    """Delete n/2 elements from the front — best case for list.remove()."""

    def run() -> Fugue[int]:
        fu: Fugue[int] = Fugue()
        for i in range(n):
            fu.insert(i, i)
        for _ in range(n // 2):
            fu.delete(0)
        return fu

    result = benchmark(run)
    assert len(result) == n - n // 2


# apply / merge — exercises the general add() path (list.index, subtree sizes)
@pytest.mark.parametrize("replicas,ops_per", [(2, 100), (2, 400), (4, 200)])
def test_merge_scale(benchmark, replicas: int, ops_per: int) -> None:
    """Merge *replicas* replicas with *ops_per* sequential appends each."""

    def run() -> Fugue[str]:
        fus = [Fugue[str](replica_id=i) for i in range(replicas)]
        for fu in fus:
            for j in range(ops_per):
                fu.insert(len(fu), f"r{fu.replica_id}-{j}")
        merged: Fugue[str] = Fugue()
        for fu in fus:
            for op in fu.ops:
                merged.apply(op)
        return merged

    total = replicas * ops_per
    result = benchmark(run)
    assert len(result) == total


def test_playlist_edit_session(benchmark) -> None:
    """Build 500 tracks, delete 100, re-add 50, fork 2x, merge all."""

    def run() -> Fugue[str]:
        fu: Fugue[str] = Fugue()
        for i in range(500):
            fu.insert(len(fu), f"track-{i:03d}")
        for _ in range(100):
            fu.delete(len(fu) // 3)
        for i in range(50):
            fu.insert(min(i * 2, len(fu)), f"new-{i}")
        a = fu.fork(replica_id=1)
        b = fu.fork(replica_id=2)
        for i in range(20):
            a.insert(len(a), f"a-extra-{i}")
            b.insert(0, f"b-extra-{i}")
        merged: Fugue[str] = Fugue()
        for op in fu.ops + a.ops + b.ops:
            merged.apply(op)
        return merged

    result = benchmark(run)
    assert len(result) > 0
