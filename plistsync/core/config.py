"""Service configuration base classes.

Defines :class:`ServiceConfig`, the dataclass base services subclass to declare
their settings, and :class:`ConfigLoader`, which loads those settings and
persists their authentication tokens.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from plistsync.services.registry import Registry

T = TypeVar("T", bound="ServiceConfig")
D = TypeVar("D")


class DataIO(ABC, Generic[D]):
    """Abstract base class for data input/output operations.

    Used for generalized loading and saving of data, such as authentication tokens or
    potential other lazy loaded configurations fields.
    """

    # Think wrapper around data
    _data: D | None = None

    @abstractmethod
    def load(self) -> D:
        """Load the data from the source."""

    @abstractmethod
    def save(self) -> None:
        """Save the data to the source."""

    def __set__(self, data: D) -> None:
        """Set the data and save it to the source."""
        self._data = data
        self.save()

    def __get__(self) -> D:
        """Get the cached data, if any or loaded."""
        if self._data is not None:
            return self._data
        self._data = self.load()
        return self._data

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> Any:
        """Treat :class:`DataIO` fields as opaque for pydantic validation."""
        from pydantic_core import core_schema

        return core_schema.any_schema()


class ConfigIO(ABC):
    """Loads service configs.

    Used for generalized loading and saving of service configurations.
    """

    @abstractmethod
    def load(self, service_config_cls: type[T]) -> T:
        """Load ``service_config_cls`` and attach this loader to it."""

    @abstractmethod
    def save(self, service_config: ServiceConfig) -> None:
        """Save the authentication token of ``service_config``."""


@dataclass
class ServiceConfig(ABC, Registry):
    """Base class for service configurations.

    Subclasses declare their settings as dataclass fields and are automatically
    registered for inclusion in the configuration schema.

    Fields holding a :class:`DataIO` (e.g. a token) are transparent: reading the
    attribute returns the loaded data, assigning to it stores and persists it.
    """

    def __getattribute__(self, name: str) -> Any:
        value = object.__getattribute__(self, name)
        return value.__get__() if isinstance(value, DataIO) else value

    def __setattr__(self, name: str, value: Any) -> None:
        current = self.__dict__.get(name)
        if isinstance(current, DataIO):
            current.__set__(value)
        else:
            object.__setattr__(self, name, value)
