"""Path rewriting utilities.

This module provides utilities for rewriting file paths in a consistent manner.
"""

from __future__ import annotations

from pathlib import PurePath
from typing import NamedTuple, TypeVar, cast

T = TypeVar("T", bound=PurePath)


class PathRewrite(NamedTuple):
    """A tuple for managing and applying path rewriting rules."""

    old: PurePath
    new: PurePath

    @classmethod
    def from_str(cls, old: str, new: str) -> PathRewrite:
        """Create a PathRewrite instance from string representations of paths.

        Parameters
        ----------
        old : str
            The old path prefix to be replaced.
        new : str
            The new path prefix to replace with.
        """
        return cls(PurePath(old), PurePath(new))

    def _coerce_like(self, template: T, p: PurePath) -> T:
        """Coerce `p` into the same concrete path class as `template`."""
        path_cls = cast(type[T], template.__class__)
        return path_cls(str(p))

    def apply(self, path: T) -> T:
        """Apply the rewrite rule to a given path.

        Parameters
        ----------
        path : PurePath
            The path to be rewritten.
        """
        old = self._coerce_like(path, self.old)
        new = self._coerce_like(path, self.new)

        if path == old:
            return new
        if old in path.parents:
            return new / path.relative_to(old)
        return path

    @property
    def invert(self) -> PathRewrite:
        """Invert the rewrite rule."""
        return PathRewrite(self.new, self.old)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(old='{str(self.old)}', new='{str(self.new)}')"
