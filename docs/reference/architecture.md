```{eval-rst}
.. meta::
   :description: Software architecture overview for the core ideas in plistsync.
```

# Architecture

We follow a layered design that unifies and generalizes operations across different
music platforms while maintaining flexibility.

## High-Level

From a high level, plistsync abstracts and unifies communication with external services,
whether streaming platforms (Spotify, Tidal, Plex) or local track storage (Traktor NML,
local files).

Services are plugins. `ServiceLoader` discovers them through entry points, and importing
a service module registers its classes (tracks, playlists, identifiers, config, and auth)
under the service name.

A service registers the abstractions it supports: a **Library** if it manages playlists,
a plain **Collection** if it only provides tracks, or a **Playlist** in the case of the
sync service. Not every service is a library.

```{mermaid}
flowchart LR
    S(Service)
    subgraph Core [Unified abstractions]
        C[Collection]
        L[Library]
        P[Playlist]
        T[Track]
    end

    S -. registers .-> C
    S -. registers .-> L
    C --> T
    L --> P
```

Collections express what they can do through **capabilities**. These are protocols
checked at runtime, so a collection only supports what it implements:

- `IDLookup`: find tracks by exact `TrackID`.
- `InfoLookup`: find tracks by metadata similarity.
- `TrackStream`: iterate over all tracks.

Matching and the CLI use these capabilities to decide which operations are available.

## Playlists

Playlists follow an abstract inheritance hierarchy. This allows services to implement
playlists with different capabilities while users interact with a unified interface.

The hierarchy distinguishes between:

- **Offline playlists** exist only in memory, no remote association
- **Service playlists** backed by a remote service
- **Synced playlists**, the sync service's playlists backed by a CRDT

`ServicePlaylist` adds `update()`, `delete()`, and `edit()`, a transactional context
manager that rolls back on error. `MultiRequestServicePlaylist` is the base for APIs
that need separate calls for track changes and metadata updates.

```{mermaid}
:config:   { "class": { "hideEmptyMembersBox": true }}

classDiagram
    direction TB

    class Playlist~T~ {}
    class OfflinePlaylist {}
    class ServicePlaylist~T~ {}
    class MultiRequestServicePlaylist~T~ {}
    class SpotifyPlaylist {}
    class TidalPlaylist {}
    class PlexPlaylist {}
    class NMLPlaylist {}
    class SyncedPlaylist {}

    Playlist <|-- OfflinePlaylist
    Playlist <|-- ServicePlaylist
    Playlist <|-- SyncedPlaylist
    ServicePlaylist <|-- MultiRequestServicePlaylist
    MultiRequestServicePlaylist <|-- SpotifyPlaylist
    MultiRequestServicePlaylist <|-- TidalPlaylist
    MultiRequestServicePlaylist <|-- PlexPlaylist
    ServicePlaylist <|-- NMLPlaylist
```

:::{admonition} Why batch operations?
:class: note dropdown

Most music service APIs require separate calls for adding tracks vs. updating metadata.
`MultiRequestServicePlaylist` computes the minimal diff between two playlist states with
`core/diff.py` and translates it into the appropriate sequence of API calls, batching
consecutive inserts and deletes.
:::

`SyncedPlaylist` is the sync service's playlist. It links playlists across services and
merges changes with a CRDT. See [How syncing works](../services/sync/how-it-works.md) for
the details.

## Tracks

A **track** is one piece of music. Each service implements the `Track` abstract base
class, which exposes metadata and identifiers:

```python
@property
@abstractmethod
def info(self) -> TrackInfo:
    """The track metadata, for example title, artists, and albums."""

@property
@abstractmethod
def ids(self) -> frozenset[TrackID]:
    """All identifiers known for this track."""
```

`TrackInfo` is a typed dictionary with the optional keys `title`, `artists`, and
`albums`.

Identifiers are `TrackID` subclasses. Each one carries a `Scope` that decides how it is
used:

- **Global identifiers** (`Scope.GLOBAL`) work across services, for example an ISRC or a
  service-specific track ID.
- **Local identifiers** (`Scope.LOCAL`) only make sense in one context, for example a
  `FilePath` on your machine.

A track can carry several identifiers at once. Matching partitions them by scope instead
of relying on any single identifier.

:::{admonition} Why scoped identifiers?
:class: note dropdown

No single identifier is universally available. ISRCs miss older tracks, service IDs
don't transfer between platforms, and file paths vary across machines. Matching uses the
best available identifier for reliability, and falls back to metadata for coverage.
:::

## Libraries

A `Library` is the top-level entry point for a service that manages playlists. It extends
`Collection` with playlist management. Services that only provide tracks, such as local
files and beets, register a plain `Collection` instead.

Libraries provide the following abstractions:

- **Playlist retrieval** via the `playlists` property
- **Playlist lookup** with `get_playlist`, by `id` or `name`. Some services also accept
  `url` or `uri`
- **Playlist creation** with `create_playlist`, with optional initial tracks
- **Construction from a config** through the `from_config` alternative constructor

:::{admonition} Why the Library abstraction?
:class: note dropdown

Whether you're fetching playlists from Spotify or from a Traktor NML file, the syntax is
identical. Libraries abstract away the underlying service while providing a consistent
API for playlist operations.
:::

## Matching

Matching connects tracks across services, enabling cross-platform syncing. For example
when you transfer a playlist from Spotify to Tidal, matching finds which Tidal tracks
correspond to your Spotify songs.

`Collection.match` tries increasingly fuzzy strategies until it finds a suitable match or
exhausts all options:

```{mermaid}
flowchart TD
    A[Track] --> B{Global ID}
    B -->|Hit| C[Match]
    B -->|Miss| D{Local ID}
    D -->|Hit and similar enough| E[Match]
    D -->|Miss or not similar enough| F{Metadata similarity >= cutoff}
    F -->|Hit| G[Best candidate]
    F -->|Miss| H[No match]

    class C,E,G success
    class H danger
```

1. **Global ID**: exact lookup by global identifiers. A hit returns immediately with
   similarity 1.0.
2. **Local ID**: exact lookup by local identifiers, validated with metadata similarity.
   Candidates below the cutoff are discarded.
3. **Metadata**: `InfoLookup` candidates ranked with `fuzzy_match`, keeping those at or
   above the cutoff (0.6 by default).
4. **Track stream fallback**: collections without ID or metadata lookup stream every
   track through the same comparison. This is much slower.

`match` returns `Matches` with the candidates and their similarities, and exits early
after a local match or a perfect fuzzy match unless the `skip_after_local_match` and
`skip_after_perfect_fuzzy_match` flags are disabled. `match_many` batches the same
stages with `find_many_by_ids` and `find_many_by_info`.

| Priority | Method | Confidence |
|--------|--------|------------|
| 1 | Global ID (ISRC, service ID) | Certain |
| 2 | Local ID (file path, DB ID) | High + validation |
| 3 | Metadata similarity (title/artist/album) | Fuzzy (≥0.6) |
