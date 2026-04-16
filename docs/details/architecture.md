```{eval-rst}
.. meta::
   :description: Software architecture overview for the core ideas in plistsync.
```


# Architecture

We follow a layered design that unifies and generalizes operations across different
music platforms while maintaining flexibility.

## High-Level

From a high level, plistsync abstracts and unifies communication with external services, whether streaming platforms (Spotify, Tidal) or track storage (Traktor NML, local files).

Each service exposes a **Library**, which provides a unified interface to interact with
that service. Whether you're fetching playlists from Spotify or a local folder with M3U
files, the syntax is identical.

```{mermaid}
flowchart LR
    S(Service)
    subgraph Core [Unified abstractions]
        L[Library]
        P[Playlist]
        T[Track]
    end

    S <--> L
    L --> T
    L -.-> P

    S@{ shape: processes }
```


## Playlists

Playlists follow an abstract inheritance hierarchy. This allows services to implement 
playlists with different capabilities while users interact with a unified interface.

The hierarchy distinguishes between:

- **Offline playlists** exist only in memory, no remote association
- **Service playlists** backed by a remote service

Service playlists further distinguish between single-request operations and 
batch-friendly operations.


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
    class TraktorPlaylist {}

    Playlist <|-- OfflinePlaylist
    Playlist <|-- ServicePlaylist
    ServicePlaylist <|-- MultiRequestServicePlaylist
    MultiRequestServicePlaylist <|-- SpotifyPlaylist
    MultiRequestServicePlaylist <|-- TidalPlaylist
    ServicePlaylist <|-- TraktorPlaylist
```

:::{admonition} Why batch operations?
:class: note dropdown

Most music service APIs require separate calls for adding tracks vs. updating metadata.
`MultiRequestServicePlaylist` computes the minimal diff between two playlist states and 
translates it into the appropriate sequence of API calls.
:::


## Tracks

Tracks follow a composition-over-inheritance model. Rather than a deep hierarchy,
tracks aggregate three distinct identity layers via typed dictionaries, allowing
flexible composition based on what identifiers are available.

The design separates concerns into:

- **Global IDs** Cross-service identifiers (ISRC, service IDs) for matching across libraries
- **Local IDs** Context-scoped identifiers (file paths, database IDs) for internal references  
- **Metadata** Title, artists, albums for display and fuzzy matching

Each service implements the `Track` abstract base class by providing these three
contracts:


```python
@property
@abstractmethod
def global_ids(self) -> GlobalTrackIDs:
    """The globally unique identifiers of this track."""
    ...

@property
@abstractmethod
def local_ids(self) -> LocalTrackIDs:
    """The locally unique identifiers of this track."""
    ...

@property
@abstractmethod
def info(self) -> TrackInfo:
    """Get this tracks information."""
    ...
```

:::{admonition} Why three identity layers?
:class: note dropdown

No single identifier is universally available. ISRCs miss older tracks, service IDs
don't transfer between platforms, and file paths vary across machines. The three-layer
approach lets matching use the best available identifier for reliability vs. coverage.
:::


## Libraries

Libraries are the top-level entry point for interacting with a music service. Each 
service implements a `Library` that provides a unified interface for playlist 
management.

Libraries provide the following abstractions:

- **Playlist retrieval** via `playlists` property
- **Playlist lookup** by various identifiers (name, id, url, uri)
- **Playlist creation** with optional initial tracks

:::{admonition} Why the Library abstraction?
:class: note dropdown

Whether you're fetching playlists from Spotify or a local folder with M3U files, the
syntax is identical. Libraries abstract away the underlying service while providing
a consistent API for playlist operations.
:::


## Matching

Matching connects tracks across services, enabling cross-platform syncing. For example when you transfer a playlist from Spotify to Tidal, matching finds which Tidal tracks correspond to your Spotify songs.

The algorithm tries increasingly fuzzy strategies until it finds a suitable match or 
exhausts all options.

```{mermaid}
flowchart TD
    A[Track] --> B{Global ID}
    B -->|Hit| C[✅ Match]
    B -->|Miss| D{Local ID}
    D -->|Hit| E[✅ Match + validate]
    D -->|Miss| F{Metadata score ≥ 0.6}
    F -->|Hit| G[✅ Best candidate]
    F -->|Miss| H[❌ No match]

    class C,E,G success
    class H danger
```

Priority | Method | Confidence |
|--------|--------|------------|
| 1 | Global ID (ISRC, service ID) | Certain |
| 2 | Local ID (file path, DB ID) | High + validation |
| 3 | Metadata similarity (title/artist/album) | Fuzzy (≥0.6)

:::{admonition} Example
:class: note dropdown

A typical sync matches ~95% of tracks by global ID, then falls back to metadata similarity for the remaining ~5%.
:::
