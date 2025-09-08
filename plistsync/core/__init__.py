"""Core components of the plistsync library.

This module provides foundational classes and protocols for managing and matching music
collections. It includes abstract base classes (ABCs) and protocols that define the
expected behaviors of various collection types, as well as utilities for track handling
and path rewriting.
"""

from . import matching
from .collection import Collection, LibraryCollection
from .rewrite import PathRewrite
from .track import GlobalTrackIDs, Track

__all__ = [
    "Collection",
    "LibraryCollection",
    "PathRewrite",
    "Track",
    "GlobalTrackIDs",
    "matching",
]
