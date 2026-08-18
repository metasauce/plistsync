# API

The same workflow is available programmatically through `plistsync.services.sync`; every CLI step maps to a method on the `SyncedPlaylist` class. If you are new to synced playlists, start with [Getting started](getting-started). The examples assume your services are installed, configured, and authenticated.

## Create a synced playlist

```python
from plistsync.services.sync import SyncedPlaylist

synced = SyncedPlaylist(name="My Mix", description="The tracks we both like")
```

`synced.id` holds the playlist's unique ID. You can seed the collection with initial tracks via the `tracks=` argument, a sequence of `OfflineTrack`.

## Link/register playlists

Fetch real playlists from your services and register them as replicas:

```python
from plistsync.services.spotify.library import SpotifyLibrary
from plistsync.services.tidal.library import TidalLibrary

spotify_playlist = SpotifyLibrary().get_playlist_or_raise(
    url="https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
)
tidal_playlist = TidalLibrary().get_playlist_or_raise(
    url="https://tidal.com/playlist/..."
)

synced.register(spotify_playlist)
synced.register(tidal_playlist)
```

```{note}
`register()` accepts any `ServicePlaylist` and immediately aligns it with the internal collection: the playlist's tracks are merged in, and the internal state (including name and description) is pushed back, the same round-trip the CLI performs.
```

## Inspect

```python
print(synced.name, synced.id)
print(synced.n_linked)  # number of linked playlists

for track, playlists in synced.track_associations():
    print(track.title, "→", ", ".join(p.name for p in playlists))
```

`track_associations()` yields each track of the internal collection together with the set of linked playlists it currently appears in, the same information `sync show` renders as its ✓/✗ matrix.

## Run a synchronisation

```python
synced.sync()
```

`sync()` runs the full pipeline (fetch, merge, enrich, push), so changes made anywhere (in the other services' apps, on another machine, or via another replica) propagate to all linked playlists. See [How it works](how-it-works) for what each phase does.

## Persist and reload

```python
synced.save_to("my-mix.json")

# ...later, in another process or on another machine...
synced = SyncedPlaylist.load_from("my-mix.json")
```

`save_to()`/`load_from()` persist and restore the full state, including the CRDT operation history, not just a snapshot, so a restored synced playlist can keep merging with operations produced later. Loading re-resolves the linked playlists from their services, so those services must be installed and configured.

To remove a synced playlist programmatically, just delete the file:

```python
from pathlib import Path

Path("my-mix.json").unlink()
```

As with `sync remove`, the linked playlists on your services are left untouched.
