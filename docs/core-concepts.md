```{eval-rst}
.. meta::
   :description: Shared vocabulary for plistsync: services, capabilities, libraries, playlists, tracks, identifiers, matching, and syncing.
```

# Core concepts

This page explains the words used throughout the `plistsync` documentation. The same
terms apply whether you use the command line or the Python library. Together they form
the layer that maps every service onto the same libraries, playlists, and tracks.

## Services

A **service** is a music platform or source that `plistsync` can talk to, for example
Spotify, Tidal, Plex, Traktor, or a folder of local files.

Services differ in how they are reached. Some are accessed through an API, others
through files on disk. `plistsync` unifies them behind one common interface, so a
feature works the same way wherever it is available.

Each service exposes its music as a **library**, i.e. the tracks and playlists it knows
about. On top of that, a service may support optional **capabilities**, for example
logging in, editing playlists, or searching for tracks.

```{mermaid}
:caption: A service, its library, and its capabilities, using Spotify as an example. Other services may support fewer of these.

flowchart TB
    S[Spotify]
    S --> L[Library]
    L --> P[Playlists]
    L --> T[Tracks]
    S --> A[Login]
    S --> E[Playlist editing]
    S --> F[Search]
```

## Collections, playlists, and tracks

A **collection** is any group of tracks. A library is a collection, and so is a
playlist.

A **playlist** is an ordered selection of tracks. Some playlists live on a service and
can be edited there. Others exist only inside `plistsync`.

A **track** is a single song. `plistsync` stores its metadata, such as title, artist, and
album, together with the identifiers that let it find the same song on another service.

## Identifiers

An **identifier** is a value that points to a track or playlist, for example an ISRC, a
service-specific ID, or a file path. Identifiers come in two kinds:

- **Global identifiers** work across services. An ISRC identifies the same recording
  everywhere it appears.
- **Local identifiers** only make sense in one context, such as a file path on your
  machine.

A track or playlist can carry more than one identifier at a time. Playlists can also be
referenced by name, ID, URL, or URI, whichever is most convenient.

## Matching

Matching is how `plistsync` finds the same song on two different services. It tries the
most reliable signals first and falls back to fuzzier ones:

```{mermaid}
flowchart LR
    A[Track] --> B{Global identifier?}
    B -->|Found| C[Match]
    B -->|Not found| D{Local identifier?}
    D -->|Found| C
    D -->|Not found| E{Metadata similar?}
    E -->|Yes| C
    E -->|No| F[No match]
```

Metadata matching compares title, artist, and album, and accepts the closest candidate
when the similarity is high enough. Exact identifier matches are preferred, because
they do not depend on how a service keeps its metadata up to date.

## Linking and syncing

A **synced playlist** groups two or more real playlists, on different services or on the
same one. **Linking** is the one-time step of adding a playlist to that group.
**Syncing** is the repeated step that brings the group back together: `plistsync`
compares the linked playlists and makes them share the same tracks, name, and
description.

For example, link a Spotify playlist and a Tidal playlist. Add a track or change the
description in one, then sync, and the other looks the same.

```{admonition} Reality check
:class: note
Keeping playlists identical is the goal, not a guarantee. A track that exists on one
service may be missing on another, in which case it is skipped there. Real-world
catalogs rarely agree on everything, so synced playlists are usually close siblings
rather than identical twins.
```

```{admonition} For the nerds 🤓
:class: tip
Interested in the technical details? When you sync, plistsync fetches every linked
playlist, merges the changes, and pushes the result back to all of them. Conflicts are
resolved automatically, so the linked playlists converge on the same tracks in the same
order. See [how syncing works](services/sync/how-it-works.md) for the details.
```

## Quick reference

| Term       | Meaning                                                                                     |
| ---------- | ------------------------------------------------------------------------------------------- |
| Capability | An optional feature a service may support, such as login or playlist editing.               |
| Collection | Any group of tracks.                                                                        |
| Identifier | A value that points to a track or playlist, global across services or local to one context. |
| Library    | All the tracks and playlists a service knows about.                                         |
| Linking    | The one-time step of adding a playlist to a synced playlist.                                |
| Matching   | Finding the same song on different services.                                                |
| Playlist   | An ordered selection of tracks.                                                             |
| Service    | A music platform or source plistsync can talk to.                                           |
| Syncing    | Keeping linked playlists across services in step.                                           |
| Track      | A single song.                                                                              |
