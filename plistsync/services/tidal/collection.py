from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable, Iterator, Self

import nest_asyncio

from plistsync.core import GlobalTrackIDs
from plistsync.core.collection import (
    Collection,
    GlobalLookup,
    LibraryCollection,
    TrackStream,
)
from plistsync.logger import log

nest_asyncio.apply()

class TidalLibraryCollection(LibraryCollection, GlobalLookup):
    """A collection of Tidal library items."""

    @property
    def playlists(self) -> Iterable[TidalPlaylistCollection]:
