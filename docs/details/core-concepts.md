```{eval-rst}
.. meta::
   :description: Core concepts guide for plistsync library.
```

```{seealso}
This guide explains the core concepts behind `plistsync` from a **high level perspective**.
For implementation details, abstract base classes, and protocols, see the [Advanced Guide](./advanced/index.md).
```

# Core Concepts

The `plistsync` library helps users manage and synchronize their music collections across different platforms. It aims to make tasks like transferring playlists, comparing libraries, and matching songs seamless and reliable.

## Tracks

A **track** is the smallest meaningful unit of music data - an individual song, recording, or musical piece. Each track encapsulates its metadata (title, artists, albums) and any known identifiers that allow it to be recognized or matched across different services.

Tracks form the foundation of all higher-level operations such as syncing, matching, and collection management. Whether a track originates from a local music library, a streaming platform, or an online catalog, plistsync provides a _unified_ way to represent and compare them.

### Track structure

Every track consists of three conceptual layers of data:

- **Descriptive metadata** - information about the song itself, such as its title and artists.
- **Global identifiers** - IDs that uniquely identify a track across platforms.
- **Local identifiers** - IDs that only make sense within a particular environment.

This layered design allows plistsync to recognize the same song across unrelated systems, for example, linking a local MP3 file to its equivalent on Spotify.

## Collections

A **collection** is any group of tracks you can browse, search, or operate on together. Collections provide a unified way to work with multiple tracks at once, regardless of whether they're stored locally or on a streaming service.

Collections power all operations involving more than one track: importing/exporting playlists, syncing entire libraries between services, or analyzing track matches across platforms.

### Libraries and Playlists

`plistsync` recognizes two primary collection types you'll know from music services:

- **Libraries** represent your complete music catalog — like "your entire Spotify library" or all tracks in a local folder. They're typically large (thousands of tracks), long-lived, and serve as the foundation for all syncing operations. Libraries also contain your playlists.
- **Playlists** are curated subsets of tracks from a library, organized for specific contexts like workouts, road trips, or favorites. Playlists are smaller, user-defined, and often maintain a specific playback order.

**For example**, different collections offer capabilities like fast ID lookups, metadata search, or playlist editing — `plistsync` automatically uses the best available approach for each operation based on the collection type.

## Matching

Matching is how `plistsync` determines when two tracks from different sources represent the same underlying song. This is the core intelligence that makes cross-platform syncing possible.

### Matching priority

1. **Exact global ID match** - ISRC codes, Spotify IDs, Apple Music IDs (highest confidence, instant lookup)
2. **Exact local ID match** - File paths, database IDs within the same environment
3. **Fuzzy metadata match** - Title + artist + album similarity scoring (0.6+ threshold by default)

When exact matches aren't available, plistsync computes similarity scores and selects the best candidates. This handles real-world messiness like slightly different track titles or missing service IDs.

Example: Transferring a Spotify playlist to Tidal might match 95% of tracks by ID, then use metadata similarity for the remaining 5%.

```{mermaid}
flowchart TD
    A[Input Track<br/>e.g. Spotify Song] --> B{Global ID Match?<br/>ISRC, Spotify ID, etc.}

    B -->|Yes<br/>100% confidence| C[✅ Perfect Match Found]
    B -->|No| D{Local ID Match?<br/>File path, DB ID}

    D -->|Yes| E[✅ Local Match +<br/>Metadata Validation]
    D -->|No| F{Fuzzy Metadata Match?<br/>Title+Artist+Album<br/>Score ≥ 0.6}

    F -->|Yes| G[✅ Best Similarity Match]
    F -->|No| H[❌ No Match Found]

    C --> I[Return Matches Object]
    E --> I
    G --> I
    H --> I

    %% Theme-agnostic styling using strokes and simple fills
    classDef success stroke:#28a745,stroke-width:2px
    classDef info stroke:#17a2b8,stroke-width:2px
    classDef warning stroke:#ffc107,stroke-width:2px
    classDef danger stroke:#dc3545,stroke-width:2px

    class C,E,G success
    class E info
    class G warning
    class H danger
```

## Services

A **service** connects plistsync to your actual music sources and destinations — whether that's Spotify, your local music folder, Apple Music, or Tidal. Think of services as the adapters that make different platforms speak plistsync's universal language.

Each service manages the platform-specific details so you don't have to:

- **Authentication** - OAuth flows, API keys, local file permissions
- **Data extraction** - Reading playlists, libraries, track metadata from each platform's unique format
- **Data import/export** - Converting between platform formats and plistsync's standard Tracks/Collections
- **Write-back** - Creating playlists, adding tracks, updating metadata on the target platform

**Example**: Sync a Spotify "Road Trip" playlist → Tidal by letting services handle authentication → data extraction → track matching → playlist recreation automaticall
