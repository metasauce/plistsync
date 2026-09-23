from __future__ import annotations

from typing import TYPE_CHECKING

from plistsync.core import PlaylistID
from plistsync.logger import log

if TYPE_CHECKING:
    from plistsync.core import Library, ServicePlaylist
    from plistsync.services import Service


def parse_playlist_id(value: str, service: Service | None = None) -> PlaylistID | None:
    """Parse a playlist identifier from a string.

    With a service, its registered playlist identifier classes are tried.
    Without one, global serials are resolved via ``PlaylistID.from_serial``.
    """
    if service is not None:
        for id_cls in service.playlist_ids():
            try:
                return id_cls.parse(value)
            except ValueError:
                continue

    return PlaylistID.from_serial(value)


def parse_playlist(value: str, library: Library) -> ServicePlaylist | None:
    """Parse a playlist from a string, using the given library.

    The string can be a playlist name, serial, URL or URI. If a matching playlist
    is found in the library, it is returned. Otherwise, None is returned.
    """
    # Note: playlists are falsy when empty (__len__), so compare to None.
    if (playlist := library.get_playlist(id=value)) is not None:
        return playlist

    return library.get_playlist(name=value)


def autocompletion_playlist(incomplete: str, library: Library) -> list[str]:
    """Autocompletion callback for playlist names and serials."""

    try:
        playlists = list(library.playlists)
    except Exception as e:
        # Completion runs inside the user's shell; never let it hard crash.
        log.debug("Playlist completion failed: %s", e)
        return []

    return [
        value
        for playlist in playlists
        for value in (playlist.name, playlist.id.serial)
        if not incomplete or value.startswith(incomplete)
    ]
