"""Spotify wiring for the shared collections scenario."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from plistsync.core.ids import ISRC
from plistsync.services.spotify import SpotifyConfig, SpotifyLibrary, SpotifyTrackID
from tests_integration.abc import build_scenario

if TYPE_CHECKING:
    from tests_integration.abc import CollectionsScenario


@pytest.fixture(scope="session")
def scenario() -> CollectionsScenario:
    """Track identifiers used by the Spotify collections scenario."""
    return build_scenario(
        SpotifyLibrary,
        SpotifyConfig,
        tracks=(
            # First track is looked up by both identifiers; they must match.
            (SpotifyTrackID("6fzwardfFs6sVfNA5R1ypt"), ISRC("GBBZH9601601")),
            (ISRC("GBXJH1000082"),),
        ),
    )
