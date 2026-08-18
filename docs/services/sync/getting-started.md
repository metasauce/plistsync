# Getting Started

This guide walks you through the full lifecycle of a synced playlist: creating one, linking playlists from your services, inspecting the result, and running a synchronisation. By the end you'll have playlists on different services that stay in lockstep, same tracks and same order, with `plistsync` doing the bookkeeping.

`plistsync` exposes the same workflow through two interfaces, each covered on its own page:

- [Using the CLI](cli): shell commands for interactive use and scripting.
- [Using the Python API](api): the same steps as direct function calls, for embedding in your own code.

## Prerequisites

Synchronisation moves tracks _between_ services, so every service whose playlists you want to link must be installed, configured, and authenticated. The `sync` service works with any service-specific playlist class, i.e. anything implementing {py:class}`plistsync.core.playlist.ServicePlaylist` (currently spotify, tidal, plex, and traktor), and you can mix and match freely.

```{note}
The `sync` service itself requires **no configuration and no credentials**. It has no external API of its own and works entirely through the services above. All you need are configured services with playlists to link.
```

## Concepts

A **synced playlist** is the unit of synchronisation: a virtual playlist that keeps a group of real playlists in sync. It consists of

- an **internal track collection**, the single source of truth. Tracks are stored service-agnostically as global IDs (e.g. ISRC) plus metadata, with no service-specific objects attached; and
- **linked playlists**, real playlists on your services (e.g. a Spotify playlist and a Tidal playlist) that are registered as _replicas_ of the synced playlist.

```{mermaid}
flowchart LR
    subgraph SP ["Synced playlist 'My Mix'"]
        C[(internal track collection)]
    end

    S[Spotify playlist] <--> C
    T[Tidal playlist] <--> C
    P[Plex playlist] <--> C
```

Every synchronisation is an exchange: the current contents of each linked playlist are **merged** into the internal collection, and the reconciled collection is then **pushed** back to all of them. Because the merge is expressed as conflict-free (CRDT) operations rather than "last write wins" overwrites, edits made in different services or directly in a service's own app between runs combine deterministically instead of clobbering each other. See [How it works](how-it-works) for the details.

## Next steps

- [Using the sync CLI](cli): the full command walkthrough, from creating a synced playlist to removing it.
- [Using the Python API](api): the same workflow as calls on `SyncedPlaylist`.
- [How it works](how-it-works): the merge and push mechanics, replicas, and the CRDT design in depth.
- The service getting-started guides: configure and authenticate the services you want to link.
