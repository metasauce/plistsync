# Sync

The `sync` service is `plistsync`'s orchestration layer for keeping playlists in sync across music services. Instead of talking to a single external API, it manages **synced playlists**: named, virtual playlists that link real playlists on any number of services (Spotify, Tidal, Plex, Traktor, ...) to one shared, service-agnostic track collection.

Running a synchronisation pulls the current contents of every linked playlist, merges external changes with conflict-free (CRDT-based) rules, and pushes the reconciled collection back to all linked playlists, so every service ends up with the same tracks in the same order.

Unlike the other services, `sync` is not backed by an external API: it needs no configuration or credentials of its own, only the services whose playlists you link, which must be configured and authenticated as usual.

```{toctree}
:maxdepth: 2

getting-started
how-it-works
cli
api
```
