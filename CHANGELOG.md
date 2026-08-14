# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Upcoming

### Breaking Changes

- Service configuration is now dynamic and extensible. Instead of a static config schema with hardcoded service fields, the schema is built at runtime from registered `ServiceConfig` subclasses. Each service ships its own config class in `plistsync/services/<service>/config.py` (`BeetsConfig`, `PlexConfig`, `SpotifyConfig`, `TidalConfig`, `TraktorConfig`), which enables easier addition of new services and more flexible validation.
  - Removed the hardcoded service accessors on `Config` (`Config.beets`, `Config.plex`, `Config.spotify`, `Config.tidal`, `Config.traktor`). Use `Config.get_service_config("<service>")` or the convenience classmethod on the service's config class (e.g. `PlexConfig.get()`) instead.
  - Removed the per-service `enabled` flag (the `OptionalService` base class is gone); a service config is now always part of the schema once its config class is registered. The `enabled` key is no longer accepted in service sections and must be removed from existing config files.
  - The config file is now loaded from `config.yaml` instead of `config.yml`. Rename existing config files; otherwise a fresh default config is generated.
  - Removed the `enabled` flag from the `logging` section. Logging is always initialized when the CLI starts, so the key is no longer supported and must be removed from existing config files.

### Added

- Added `match_many` method to `Collection` base to allow matching multiple tracks at once, improving performance for large collections as it avoids repeated api calls for each track.
- Added the `ServiceConfig` base class, which auto-registers a service's config schema and automatically includes it in the main config schema.
- Added `Config.get_service_config()` which lazily discovers a service, rebuilds the config schema, reloads and validates the config file, and returns the service's config instance.
- Added the `plistsync sync` CLI subcommands (`create`, `remove`, `list`, `register`, `show`, `run`) for managing and running synced playlists.
- Added `Service.config()` for resolving a service's registered config class and the `ServiceConfig.get()` classmethod (e.g. `PlexConfig.get()`) for direct access to the service config instance.
- Moved each service's configuration into the service package, including token handling (`SpotifyConfig.load_token()`, `TidalConfig.load_token()`, `PlexConfig.token_path`).

### Changes

- The generated default config file now includes all discoverable services, making it easier to see which services are available and how to configure them.
- Logging is now initialized when the CLI starts instead of at import time. This makes logging configuration more predictable, avoids side effects for library consumers, and improves support for applications managing their own logging configuration. (#107)
- Updated eyconf dependency to 0.8.0, we now use `pydantic` for config validation and schema generation instead of `jsonschema`.

## [0.7.0] - 2026-07-21

### Breaking Changes

- Refactored track identifier handling across the codebase by replacing service-specific `TrackIds` dictionaries with strongly typed, immutable `TrackID` dataclasses for each service (e.g. Spotify, Plex).
- Refactored playlist identifier handling across the codebase by replacing service-specific `PlaylistIds` dictionaries with strongly typed, immutable `PlaylistID` dataclasses for each service (e.g. Spotify, Plex).
  - Removed obsolete playlist ID extraction utilities that are no longer required under the new identifier system.
  - Updated all playlist operations and internal synchronization flows to use the new typed identifier model consistently.

This improves type safety, clarity, and extensibility for playlist identification and lookup operations. All playlist-related APIs and synchronization logic now operate on explicit identifier types instead of loosely structured dictionaries.

- Replaced the import-based `ServiceRegistry` with entry-point based service discovery via `ServiceLoader` (`ServiceLoader.get(name)` / `ServiceLoader.all()`). Services are now discovered through the `plistsync.services` entry-point group without importing all service modules, and services with missing optional dependencies are skipped gracefully.
- Removed the `track_cls`, `library_cls`, `playlist_cls` and `playlist_id_cls` attributes from `Service` implementations; registered classes are resolved through the `Registry` instead.
- `OfflinePlaylist` now takes a typed `PlaylistID` (`id=...`) instead of an `id_serial` string.

### Added

- Added typed `Service` marker class with a module-inferred `name` property and registry-backed accessors (`library()`, `tracks()`, `track_ids()`, `playlist_ids()`), enabling single-handle access to all a service's core types. (#95)
- Added generic `Registry` base class that auto-registers concrete implementations by service name at class-definition time. `Track`, `Library`, `TrackID`, and `PlaylistID` are now registry roots, making service classes discoverable simply by importing their module.
- Added `SerialID` base class unifying the identifier contract (`parse`/`serial`) with a service-derived namespace `prefix()` that is enforced on construction. `TrackID.from_serial()` and `PlaylistID.from_serial()` resolve a serial string to the correct service's identifier class via `ServiceLoader`.
- Added a migration example to fully copy a playlist from an arbitrary service to another. (#60)
- Added `SyncedPlaylist` class for bidirectional playlist synchronization across an arbitrary number of services. This class encapsulates the logic for detecting differences, applying updates, and maintaining a consistent state across all linked services. (#100)
  - Conflict-free state replication via a CRDT (Fugue): each linked playlist acts as a replica, so changes made directly on a service (outside plistsync) merge cleanly without conflicts.
  - Phased `sync()` pipeline: `refresh()` pulls the current state from each service, `merge()` reconciles external additions/removals/reorders into the internal collection, `enrich()` cross-links tracks between services and backfills missing identifiers (e.g. ISRCs), and `push()` writes the resolved state back to every linked playlist.
  - Track association is availability-aware: tracks that cannot be resolved on a given service are skipped for that service instead of being dropped from the internal collection.
  - Added `SyncedPlaylistID`, a UUID-based playlist identifier for synced playlists.
  - Added serialization for SyncedPlaylists, `save_to` and `load_from` methods (#104)

### Fixed

- When syncing playlists to traktor, we now insert missing tracks into the library collection. This avoids those track to disappear from the playlist when launching Traktor after the sync. (#54)
- Adjusted spotify api layer for deprecations

### Changes

- Introduced a OfflineTrack class mirroring the idea behind the OfflinePlaylist. This allows us to preserve track information even after deletion from the remote service, and to keep the Playlist class hierarchy cleanly separated between in-memory and service-synced implementations.

## [0.6.0] - 2026-04-18

### Breaking Changes

#### Playlist Class Hierarchy Refactor

The playlist class hierarchy has been redesigned for clearer separation of concerns:

**Renamed Classes:**

- `PlaylistCollection` → `Playlist` (base protocol)
- `SpotifyPlaylistCollection` → `SpotifyPlaylist`
- `TidalPlaylistCollection` → `TidalPlaylist`
- `PlexPlaylistCollection` → `PlexPlaylist`
- `NMLPlaylistCollection` → `NMLPlaylist`

**Library Classes Renamed:**

- `SpotifyLibraryCollection` → `SpotifyLibrary`
- `TidalLibraryCollection` → `TidalLibrary`
- `PlexLibrarySectionCollection` → `PlexLibrary`
- `NMLLibraryCollection` → `NMLLibrary`

**New Abstractions:**

- `OfflinePlaylist` — In-memory playlist with no service synchronization
- `ServicePlaylist` — Base for playlists synchronized with music services
- `MultiRequestServicePlaylist` — For APIs requiring multi-request modifications
- `PlaylistIDs` — Unified TypedDict for cross-service playlist identification

**Method Changes:**
| Old | New | Notes |
|-----|-----|-------|
| `remote_edit()` | `edit()` | Context manager for transactional edits |
| `remote_delete()` | `delete()` | Returns `OfflinePlaylist` with last state |
| `remote_create()` | `library.create_playlist()` | Factory method on library |
| `remote_upsert()` | `update()` | Bulk sync to remote |
| `remote_associated` | Removed | Service playlists always correspond to remote |

**Migration:**

```python
# Old
pl = SpotifyPlaylistCollection(library, "Name", "desc")
pl.remote_create()
with pl.remote_edit():
    pl.tracks.append(track)

# New
pl = library.create_playlist("Name", "desc")
with pl.edit():
    pl.tracks.append(track)
```

- Auth commands are now available via `plistsync auth [service]` instead of `plistsync [service] auth`

### Added

- Split Playlist ABC into two classes: one for simple services, like filesystems, where states can be pushed via a single API call (`PlaylistCollection`) and one where multiple API calls are required (`MultiRequestPlaylistCollection`), e.g. when a playlists description cannot be pushed in the same call as track changes.
- Added `allservices` dependency group to allow a loaded pip install with batteries included.
- Added `plistsync --version` command to show the currently installed version of the library

### Fixed

- Fixed lazy track loading when playlist has 0 tracks (`force=True` logic in `_load_tracks`)
- In rare cases, spotify playlists can contain invalid items, which do not appear in the web interface (but through the api). We now filter and remove them.
- Fixed an issue with the spotify api returning duplicate playlists on pagination borders.
- In rare cases, spotify playlists can contain invalid items, which do not appear in the web interface (but through the api). We now filter and remove them.

## [0.5.1] - 2026-03-16

### Fixed

- Add missing platformdirs dependency

## [0.5.0] - 2026-03-15

This marks the first **public release** of `plistsync`, a major milestone for the project! 🎉

While the library is now in a **very usable state** and suitable for real-world music library synchronization, we’re still actively refining the public API. As such, **breaking changes to function signatures, module structure, or core abstractions may occur without deprecation warnings** until we reach version `1.0.0`.

We encourage early adopters to:

- Experiment freely and share feedback (via GitHub Issues or Discussions)
- Pin to this version if stability is critical
- Expect occasional breaking changes as we iterate toward a stable `1.0.0` API

### Added

- Traktor config option `backup_before_write` (enabled by default), which creates a backup of the NML file before each write operation.
- `pyproject.toml` metadata enhancements: updated `readme`, `license`, `authors`, `project_urls`, and `classifiers` for better discoverability and packaging.
- Support for **batched remote operations**, enabling efficient minification of expensive network requests (e.g., bulk playlist updates across services).
- Improved examples: now hosted in `docs/examples` (full-fledged Jupyter notebooks by the core team) and `docs/examples/community` (community-contributed scripts, including simple CLI workflows).

### Changed

- Unified `__repr__` format across all core classes to `ClassName(key=value)` for consistent, debug-friendly output.
- Standardized `get_playlist()` behavior across all services: now consistently returns `None` when no playlist is found, regardless of the lookup identifier used. Introduced `get_playlist_or_raise()` for predictable, exception-raising behavior when a playlist _must_ exist.

## [0.4.0] - 2026-03-07

### Added

- Enhanced documentation around traktor
- Plex authentication flow: Automated token retrieval replaces manual web page searches
- Config refactoring: Replaced hardcoded YAML defaults with dataclass fields (Note: requires config file recreation)
- Unified CLI authentication: Standardized parameters across Spotify, Tidal, and Plex services
- Configuration files can now be placed in multiple locations with clear precedence:
  1. Environment variable: `PSYNC_CONFIG_DIR=/path/to/config`
  2. Global directory: User's config folder (automatic fallback)
- Verify jupyter notebooks are runnable and output via [nbmake](https://github.com/treebeardtech/nbmake)
- Added configurable logging (`logging.handler`: `rich|basic`), improved CLI verbosity (`-v`) behavior and documented advanced logging.
- Renewed icon
- Added integration tests that use github secrets for tidal and spotify auth, and config yaml
- Added check for notebook consistency via nbmake

### Changed

- Traktor playlist `NMLPlaylistCollection` is now aligned with the `PlaylistCollection` protocol
- Enhanced typing for `Matches` class and collection protocols by using a TypeVar for Tracks.
- Nbstripout keeps outputs now

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

## [0.1.0] - 2025-09-08

### Added

- Initial release with core abstractions for tracks and collections.
- Integrations with Plex, Traktor, Beets, and Local services.
- Documentation setup and first examples.
- Basic CI/CD workflows.

[0.7.0]: https://github.com/metasauce/plistsync/releases/tag/v0.7.0
[0.6.0]: https://github.com/metasauce/plistsync/releases/tag/v0.6.0
[0.5.1]: https://github.com/metasauce/plistsync/releases/tag/v0.5.1
[0.5.0]: https://github.com/metasauce/plistsync/releases/tag/v0.5.0
[0.4.0]: https://github.com/metasauce/plistsync/releases/tag/v0.4.0
[0.3.0]: https://github.com/metasauce/plistsync/releases/tag/v0.3.0
[0.2.0]: https://github.com/metasauce/plistsync/releases/tag/v0.2.0
[0.1.0]: https://github.com/metasauce/plistsync/releases/tag/v0.1.0
