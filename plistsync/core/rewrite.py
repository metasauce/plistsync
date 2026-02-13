"""Path rewriting utilities.

This module provides utilities for rewriting file paths in a consistent manner.
"""

from __future__ import annotations

from pathlib import Path, PurePath
from typing import NamedTuple, TypeVar, cast

T = TypeVar("T", bound=PurePath | Path)


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

    def apply(self, path: T) -> T:
        """Apply the rewrite rule to a given path.

        Parameters
        ----------
        path : PurePath
            The path to be rewritten.
        """

        old = self.old
        new = self.new
        if isinstance(path, Path):
            old = Path(self.old)
            new = Path(self.new)

        res = path
        if path == old:
            res = new
        elif old in path.parents:
            res = new / path.relative_to(old)

        return cast(T, res)

    @property
    def invert(self) -> PathRewrite:
        """Invert the rewrite rule."""
        return PathRewrite(self.new, self.old)
