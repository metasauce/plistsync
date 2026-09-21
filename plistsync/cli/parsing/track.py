"""Track identifier parsing for CLI input."""

from __future__ import annotations

from typing import TYPE_CHECKING

from plistsync.core import TrackID

if TYPE_CHECKING:
    from plistsync.services import Service


def parse_track_id(value: str, service: Service | None = None) -> TrackID | None:
    """Parse a track identifier from a string.

    With a service, its registered track identifier classes are tried first.
    Unmatched values fall back to global serials via ``TrackID.from_serial``.
    """
    if service is not None:
        for id_cls in service.track_ids():
            try:
                return id_cls.parse(value)
            except ValueError:
                continue

    return TrackID.from_serial(value)
