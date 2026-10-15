"""Scenario construction for the live collections tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from plistsync.cli.config import UserDirConfigIO
from plistsync.errors import InvalidTokenError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from plistsync.core import Library, Track, TrackID
    from plistsync.core.config import ServiceConfig


@dataclass(frozen=True)
class CollectionsScenario:
    """A live service under test and the tracks the scenario works with."""

    service: str
    library: Library[Any, Any, Any]
    tracks: tuple[tuple[TrackID, ...], ...]
    """At least two tracks, each described by one or more identifiers."""

    def find_track(self, track_id: TrackID) -> Track | None:
        """Look up a single track via the service library."""
        find_by_ids = getattr(self.library, "find_by_ids", None)
        if find_by_ids is None:
            pytest.skip(f"{self.service} library does not support find_by_ids().")
        return find_by_ids([track_id])


def build_scenario(
    library_cls: type[Library[Any, Any, Any]],
    config_cls: type[ServiceConfig],
    *,
    tracks: Sequence[tuple[TrackID, ...]],
) -> CollectionsScenario:
    """Build a live scenario, skipping when the service is not usable.

    ``tracks`` must contain at least two samples, each with at least one
    identifier. The service name is derived from the config class, the config is
    loaded from the real user/CI config directory!
    """
    if len(tracks) < 2:
        raise ValueError("The collections scenario needs at least two tracks.")
    if any(not sample for sample in tracks):
        raise ValueError("Every track sample needs at least one identifier.")

    service = config_cls.service()

    config = UserDirConfigIO().load(config_cls)
    if getattr(config, "token", None) is None:
        pytest.skip(
            f"{service} is not authenticated. Run `plistsync {service} auth` first."
        )

    try:
        library = library_cls.from_config(config)
    except InvalidTokenError as exc:
        pytest.skip(f"{service} authentication is invalid: {exc}")

    return CollectionsScenario(
        service=service,
        library=library,
        tracks=tuple(tracks),
    )
