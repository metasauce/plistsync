"""Synchronisation primitives for cross-service playlist management."""

from plistsync.services import Service
from plistsync.services.sync.playlist import (
    RegisterMode,
    SyncedPlaylist,
    SyncedPlaylistID,
)


class SyncService(Service):
    pass


__all__ = [
    "RegisterMode",
    "SyncedPlaylist",
    "SyncedPlaylistID",
]
