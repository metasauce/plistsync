"""Synchronisation primitives for cross-service playlist management."""

from plistsync.services import Service
from plistsync.services.sync.playlist import SyncedPlaylist, SyncedPlaylistID


class SyncService(Service):
    pass


__all__ = [
    "SyncedPlaylist",
    "SyncedPlaylistID",
]
