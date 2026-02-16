# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-02-16

### Added

- Collection protocol modernization:
  - `TrackStream` now exposes an explicit `.tracks` property (instead of `__iter__`), and library collections expose `.playlists`.
  - Added default `LocalLookup.find_many_by_local_ids()` batch helper (iterative fallback; services can override for true batching).

- Transactional remote playlist operations:
  - New `PlaylistInfo` unified structure (`name`, `description`, …) shared across services.
  - `PlaylistCollection.remote_edit()` context manager applies a diff on exit and rolls back local state on errors.
  - `PlaylistCollection.remote_create()` scaffolding for creating playlists online before editing.
  - Playlist remote operations are now modeled explicitly via abstract `_remote_*` methods (insert/delete/move/update/create), with a shared diff-driven apply loop.

- Service improvements & new helpers:
  - Spotify: playlist ID extraction from URL/URI (`extract_spotify_playlist_id`) + test coverage.
  - Tidal: playlist ID extraction from URL (`extract_tidal_playlist_id`); added API helper to fetch playlist items (`get_items`).
  - Plex: expanded playlist API wrapper (create/update/delete/add/remove/move/clear) to support richer remote playlist edits.

- Documentation:
  - New service collection notebooks for Spotify and Plex; expanded/rewritten Tidal collections notebook with playlist CRUD + editing examples.
  - Added developer debugging guide (`docs/dev/debug.md`) and wired it into the contribution docs toctree.

### Changed

- Plex authentication flow: Automated token retrieval replaces manual web page searches.
- Config refactoring: Replaced hardcoded YAML defaults with dataclass fields (Note: requires config file recreation).
- Unified CLI authentication: Standardized parameters across Spotify, Tidal, and Plex services.
- Diff algorithm overhaul:
  - Improved handling of duplicates and complex reorders using a “delete extras first” strategy.
  - Operations now track a `live_list` snapshot to support stable index reasoning during remote edits.
- Playlist / collection API updates across the codebase:
  - Examples and services migrated from `for track in pl:` to `for track in pl.tracks`.
  - Library `get_playlist()` is now a kwarg-based resolver (e.g. `name=`, `id=`, `url=`, `uri=` depending on service) with consistent “name returns None, id/url/uri raise” behavior.
- Plex service refactor:
  - `PlexTrack.plex_id` renamed to `.id`.
  - Playlist fetching now uses `PlexLibrarySectionCollection.get_playlist()` and sorted `.playlists`.
- Path rewriting now preserves path types (`PurePosixPath`/`PureWindowsPath`) via generic typing/coercion.
- Track model behavior:
  - Added `Track.__eq__` and `Track.__hash__` for data-based equality/hash semantics.
  - `Track.__repr__` now prints an explicit hash field.
- Tooling: Ruff target-version bumped from Python 3.10 to 3.11.
- Test suite reorganization:
  - Beets and Traktor tests moved under `tests/services/...`; Traktor tests now skip cleanly when optional dependencies are missing.

- Enhanced README, added LICENCE, reformatted CHANGELOG.

## [0.2.0] - 2025-10-30

### Added

- Added changelog reminder as GitHub Action.
- Playlist abstraction layer for easier cross-service syncing.
- Spotify service integration.
- Tidal service integration.
- Example notebooks for Spotify and Tidal usage.

### Changed

- Enabled Ruff in `.ipynb` files.
- Updated `eyeconf` dependency to 0.3.0.
- Updated Spotify and Tidal API implementations for better reliability.
- Updated `eyeconf` dependency.
- Improved test coverage for core modules.

### Other

- Enhanced test coverage for core modules.
- Fixed multiple issues with the documentation build process.

### Fixed

- Documentation build issues.
- ISRC lookup and API scope handling bugs.

---

## [0.1.0] - 2025-09-08

### Added

- Initial release with core abstractions for tracks and collections.
- Integrations with Plex, Traktor, Beets, and Local services.
- Documentation setup and first examples.
- Basic CI/CD workflows.

[0.3.0]: https://github.com/metasauce/plistsync/releases/tag/0.3.0
[0.2.0]: https://github.com/metasauce/plistsync/releases/tag/0.2.0
[0.1.0]: https://github.com/metasauce/plistsync/releases/tag/0.1.0
