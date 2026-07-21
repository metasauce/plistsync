from __future__ import annotations

from abc import abstractmethod
from typing import Generic, Protocol, TypeVar, cast

T = TypeVar("T")
S = TypeVar("S")


class Serializer(Protocol, Generic[T, S]):
    @abstractmethod
    def dump(self, value: T) -> S:
        """Serialize a Fugue instance to a string."""
        raise NotImplementedError

    @abstractmethod
    def load(self, data: S) -> T:
        """Deserialize a Fugue instance from a string."""
        raise NotImplementedError


class DummySerializer(Serializer[T, S]):
    """A dummy serializer that does nothing."""

    def dump(self, value: T) -> S:
        return cast(S, value)

    def load(self, data: S) -> T:
        return cast(T, data)
