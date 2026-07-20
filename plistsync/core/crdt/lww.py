"""Op-based Last-Writer-Wins Register CRDT.

Same design as the Fugue: an append-only log of operations whose
current value is *derived* by folding the log.

Used to synchronise playlist metadata (name, description) with the
same replica-versioned clock as the Fugue.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar

from .graph import NodeID

if TYPE_CHECKING:
    from collections.abc import Iterator

T = TypeVar("T")


def _lww_key(version: NodeID) -> tuple[int, int]:
    """Lamport ordering key: logical counter first, replica id as tie-breaker.

    ``NodeID`` orders by ``(replica_id, counter)`` (replica id first), which
    is what the Fugue wants for sibling placement but is *not* Lamport order.
    Comparing by this key keeps last-writer-wins semantics independent of the
    Fugue's structural ordering.
    """
    return (version.counter, version.replica_id)


@dataclass(frozen=True)
class RegisterOp(Generic[T]):
    """A single assignment to one field of the register."""

    key: str
    value: T
    version: NodeID


class LWWRegister(Mapping[str, Any]):
    """Op-based last-writer-wins register for named fields.

    Each field stores the value associated with the operation having the
    highest NodeID version. Versions are ordered by Lamport timestamp
    semantics (counter first, replica id as a tie-breaker), ensuring that
    concurrent updates converge to the same winner across replicas.

    The register keeps the full operation history so replicas can merge by
    replaying operations they have not seen yet.

    Fields are heterogeneous, so the register is accessed like a mapping::

        reg = LWWRegister(replica_id=0)
        reg["name"] = "Mix"  # creates an op for field "name"
        reg.assign("description", "Desc")
        dict(reg)  # current field values
    """

    def __init__(self, replica_id: int = 0) -> None:
        # Replica identity is used to create globally unique operation versions.
        self.replica_id: int = replica_id

        # Scalar Lamport clock. Advanced in exactly one place (apply) to one
        # past the highest counter observed, so versions stay unique and
        # causally ordered. ``assign`` timestamps from the current value.
        self._counter: int = 0

        # Keep operation history so replicas can merge by replaying operations.
        self._ops: list[RegisterOp[Any]] = []

        # Current winning version and value for each field.
        self._winners: dict[str, NodeID] = {}
        self._values: dict[str, Any] = {}

        # Prevent applying the same operation more than once.
        self._seen_versions: set[NodeID] = set()

    def apply(self, op: RegisterOp[Any]) -> bool:
        """Apply local or remote op; return True if it wins."""
        if op.version in self._seen_versions:
            return False

        self._seen_versions.add(op.version)
        self._ops.append(op)

        # Lamport receive rule: advance past the highest counter observed,
        # regardless of which replica the op came from.
        self._counter = max(self._counter, op.version.counter + 1)

        cur = self._winners.get(op.key)
        if cur is None or _lww_key(op.version) > _lww_key(cur):
            self._winners[op.key] = op.version
            self._values[op.key] = op.value
            return True
        return False

    def assign(self, field_name: str, value: Any) -> RegisterOp[Any]:
        """Create and apply a local op.

        The op is timestamped with the current Lamport clock; ``apply`` then
        advances the clock, so the first local op gets counter 0 and each
        subsequent op a strictly higher counter.
        """
        version = NodeID(self.replica_id, self._counter)
        op = RegisterOp(key=field_name, value=value, version=version)
        self.apply(op)
        return op

    def history(self, field_name: str) -> list[RegisterOp[Any]]:
        return [op for op in self._ops if op.key == field_name]

    def last_op_by(self, field_name: str, replica_id: int) -> RegisterOp[Any] | None:
        """Return the most recent op written to *field_name* by *replica_id*.

        Returns None if that replica has never written to the field. Used as
        the per-replica baseline when diffing snapshot-based replicas: only
        their own last write is meaningful (the current winner may come from
        another replica).
        """
        for op in reversed(self._ops):
            if op.key == field_name and op.version.replica_id == replica_id:
                return op
        return None

    def __getitem__(self, field_name: str) -> Any:
        """Return the current value for *field_name*.

        Raise KeyError if it has never been assigned.
        """
        try:
            return self._values[field_name]
        except KeyError:
            raise KeyError(f"no value for field {field_name!r}") from None

    def __setitem__(self, field_name: str, value: Any) -> None:
        """Assign *value* to *field_name*; shorthand for :meth:`assign`."""
        self.assign(field_name, value)

    def __delitem__(self, field_name: str) -> None:
        # Fields cannot be deleted: the op log is append-only, so removal
        # has no CRDT semantics (it would require tombstones).
        raise TypeError(f"{type(self).__name__} does not support field deletion")

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def fork(self, replica_id: int) -> Self:
        """Return an independent copy with a new *replica_id*."""
        new = deepcopy(self)
        new.replica_id = replica_id
        return new

    def merge(self, other: LWWRegister) -> None:
        """Merge operations from another register into this one."""
        for op in other._ops:
            self.apply(op)

    def version(self) -> NodeID:
        """Return the current Lamport clock as a NodeID."""
        return NodeID(self.replica_id, self._counter)

    def time_travel(self, version: NodeID) -> Self:
        """Return a new register containing only ops causally before *version*."""
        new = type(self)(replica_id=self.replica_id)
        for op in self._ops:
            if _lww_key(op.version) < _lww_key(version):
                new.apply(op)
        return new
