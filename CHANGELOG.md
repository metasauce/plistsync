# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Upcoming

### Added

- Enhanced collection protocols: Replaced `__iter__` with explicit `tracks` and `playlists` properties
- Transactional playlist editing: `edit()` context manager with lazy loading and minimal API calls
- Unified playlist API: Consistent `PlaylistInfo` structure and diff-based synchronization
- Spotify/Tidal improvements: URL parsing, lazy track loading, and better error handling
- Comprehensive documentation: Jupyter notebooks for Spotify and Tidal collections

### Changed

- Plex authentication flow: Automated token retrieval replaces manual web page searches
- Config refactoring: Replaced hardcoded YAML defaults with dataclass fields (Note: requires config file recreation)
- Unified CLI authentication: Standardized parameters across Spotify, Tidal, and Plex services
- Diff algorithm: Fixed edge cases for duplicates and improved move operations
- Enhanced README, added LICENCE, reformatted CHANGELOG

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

[0.2.0]: https://github.com/metasauce/plistsync/releases/tag/0.2.0
[0.1.0]: https://github.com/metasauce/plistsync/releases/tag/0.1.0
