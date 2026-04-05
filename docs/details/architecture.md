# Architecture Overview

We follow a layered design that unifies and generalizes operations across different music platforms while maintaining flexibility.

## High-Level Architecture

From a high level, plistsync abstracts and unifies communication with external services - whether streaming platforms (Spotify, Tidal) or track storage (Traktor NML, local files).

Each service exposes a **Library**, which provides a unified interface to interact with that service. Whether you're fetching playlists from Spotify or a local folder with M3U files, the syntax is identical.

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

### Design Principles

The architecture follows these key principles:

| Principle | Description |
|-----------|-------------|
| **Service adapter pattern** | Each service (Spotify, Tidal, Plex) is an adapter that implements a common interface. Users interact with `Library`, never directly with the service/api. |
| **Capability-based protocols** | Collections declare what operations they support via protocols (`GlobalLookup`, `LocalLookup`, `InfoLookup`, `TrackStream`). This allows flexible composition without rigid inheritance. |
| **Three-layer identity** | Tracks have global IDs (cross-service), local IDs (context-scoped), and metadata. Matching uses the best available layer for reliability vs. coverage. |
| **Lazy loading** | Large libraries load data on-demand to avoid upfront cost. |

For detailed explanations of each concept (Tracks, Collections, Services, Matching), see [core-concepts.md](./core-concepts.md).


### Playlist Hierarchy

Playlists follow an abstract inheritance hierarchy. This allows services to implement playlists with different capabilities while users interact with a unified interface.

The hierarchy distinguishes between:

- **Offline playlists** exist only in memory, no remote association
- **Service playlists** backed by a remote service

Service playlists further distinguish between single-request operations and batch-friendly operations.


```{mermaid}
:config:   { "class": { "hideEmptyMembersBox": true }}

classDiagram
    direction TB
    
    class Playlist~T~ {
    }
    
    class OfflinePlaylist {
    }
    
    class ServicePlaylist~T~ {
        
    }
    
    class MultiRequestServicePlaylist~T~ {
        
    }
    
    class SpotifyPlaylist {
    }
    class TidalPlaylist {
    }
    class TraktorPlaylist {
    }


    Playlist <|-- OfflinePlaylist
    Playlist <|-- ServicePlaylist
    ServicePlaylist <|-- MultiRequestServicePlaylist
    MultiRequestServicePlaylist <|-- SpotifyPlaylist
    MultiRequestServicePlaylist <|-- TidalPlaylist
    ServicePlaylist <|-- TraktorPlaylist
```

:::{admonition} Why batch operations?
:class: note dropdown

Most music service APIs require separate calls for adding tracks vs. updating metadata. `MultiRequestServicePlaylist` computes the minimal diff between two playlist states and translates it into the appropriate sequence of API calls.
:::
