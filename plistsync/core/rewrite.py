from __future__ import annotations

from pathlib import Path, PurePath
from typing import NamedTuple


class PathRewrite(NamedTuple):
    old: PurePath
    new: PurePath

    @classmethod
    def from_str(cls, old: str, new: str) -> PathRewrite:
        return cls(Path(old), Path(new))

    def apply(self, path: PurePath) -> PurePath:
        """Apply the rewrite rule to a given path."""

        if self.old in path.parents:
            return self.new / path.relative_to(self.old)
        return path

    @property
    def invert(self) -> PathRewrite:
        """Invert the rewrite rule."""
        return PathRewrite(self.new, self.old)
