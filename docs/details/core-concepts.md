```{eval-rst}
.. meta::
   :description: Core concepts guide for plistsync library.
```

```{seealso}
This guide explains the core concepts behind `plistsync` from a **high level perspective**.
For detailed architecture, see the [Architecture](architecture.md) guide.
```

# Core Concepts

This guide explains the vocabulary used throughout plistsync: Services, Libraries, 
Playlists, Tracks, and Matching.

## Services

A **service** is a music platform that plistsync can sync with — Spotify, Tidal, Plex,
a local folder, or Traktor's database.

Plistsync connects to that platform using the appropriate authentication and API. From
there, you can access your library and playlists.

```python
from plistsync.services.spotify import SpotifyLibraryCollection
from plistsync.services.tidal import TidalLibraryCollection

spotify = SpotifyLibraryCollection()
tidal = TidalLibraryCollection()
```


## Libraries

A **library** represents everything you have in a single service. This encapsulates,your
complete music catalog.


Libraries are typically large and long-lived. They also contain your playlists.

```python
for playlist in spotify.playlists:
    print(playlist.name)
```

## Playlists

A **playlist** is a curated selection of tracks from a library. Playlists are usually
smaller and user-defined, with a specific purpose or mood in mind.

```python
road_trip = spotify.get_playlist(name="Road Trip")
print(f"{len(road_trip.tracks)} tracks")
```

## Tracks

A **track** is a single song or recording. It has the basic info you'd expect, title, 
artist(s), album, plus any identifiers from the source service.

When you sync between services, plistsync uses these identifiers to match tracks 
across platforms.

## Matching

**Matching** is how plistsync finds the same song across different services.

When syncing Spotify → Tidal, plistsync first tries exact ID matches, then falls back
to fuzzy title/artist matching for tracks without direct links. This lets you sync 
playlists even when services don't share the same ID systems.
