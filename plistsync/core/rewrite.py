"""Path rewriting utilities.

This module provides utilities for rewriting file paths in a consistent manner.
"""

from __future__ import annotations

from pathlib import Path, PurePath
from typing import NamedTuple


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
        return cls(Path(old), Path(new))

    def apply(self, path: PurePath) -> PurePath:
        """Apply the rewrite rule to a given path.

        Parameters
        ----------
        path : PurePath
            The path to be rewritten.
        """
        if path == self.old:
            return self.new

        if self.old in path.parents:
            return self.new / path.relative_to(self.old)
        return path

    @property
    def invert(self) -> PathRewrite:
        """Invert the rewrite rule."""
        return PathRewrite(self.new, self.old)
