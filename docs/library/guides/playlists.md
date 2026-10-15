```{eval-rst}
.. meta::
   :description: Create, edit, reorder, and delete service playlists from the plistsync Python library.
```

# Editing Playlists

This guide shows how to create, edit, and delete playlists on a service from Python,
using the {py:class}`~plistsync.core.playlist.ServicePlaylist` interface. The examples
use Spotify; every service that provides a library works the same way. Which operations
are available depends on the service, see [Core concepts](../../core-concepts.md).

## Set up a library

Build the library from a service config, see the [Configuration](configuration.md) guide
for the different ways to obtain one:

```python
from plistsync.cli.config import UserDirConfigIO
from plistsync.services.spotify import SpotifyConfig, SpotifyLibrary

library = SpotifyLibrary.from_config(UserDirConfigIO().load(SpotifyConfig))
```

## Retrieve playlists

Iterate over all playlists of the authenticated user:

```python
for playlist in library.playlists:
    print(f"{playlist.name} ({len(playlist)} tracks)")
```

Fetch a single playlist by name, id, URL, or URI. Which of these are supported depends
on the service:

```python
playlist = library.get_playlist(name="My Playlist")
```

{py:meth}`get_playlist <plistsync.core.collection.Library.get_playlist>` returns `None`
when nothing matches. Use
{py:meth}`get_playlist_or_raise <plistsync.core.collection.Library.get_playlist_or_raise>`
if you would rather have it raise a `ValueError`:

```python
playlist = library.get_playlist_or_raise(id="<playlist id>")
```

## Create a playlist

Playlists are always created through a library:

```python
playlist = library.create_playlist(
    name="My New Playlist",
    description="Created via plistsync",
)
```

Pass `tracks=` to seed the new playlist right away:

```python
playlist = library.create_playlist(
    name="My New Playlist",
    tracks=[track_a, track_b],
)
```

## Find tracks to add

Look up tracks by their identifiers, for example an ISRC or a service-specific id:

```python
from plistsync.core.ids import ISRC

track = library.find_by_ids([ISRC("GBBZH9601601")])
if track is None:
    print("Track not found")
```

{py:meth}`find_by_ids <plistsync.core.collection.IDLookup.find_by_ids>` returns the
first track carrying any of the given identifiers. For many tracks at once, use
{py:meth}`find_many_by_ids <plistsync.core.collection.IDLookup.find_many_by_ids>`, which
batches the lookups. To search by title, artist, or album instead, see the
[Matching tracks](matching.md) guide.

## Edit a playlist

Wrap every change in the
{py:meth}`edit() <plistsync.core.playlist.ServicePlaylist.edit>` context manager.
plistsync takes a snapshot on entry, and on exit computes the minimal diff and writes
only what changed to the service. If an exception is raised inside the block, the local
changes are rolled back and the exception propagates.

Name and description:

```python
with playlist.edit():
    playlist.name = "New name"
    playlist.description = "Updated description"
```

Add tracks. Assigning a list goes through the playlist's track conversion, so plain
service tracks are accepted:

```python
with playlist.edit():
    playlist.tracks = [*playlist.tracks, track]
```

Remove tracks:

```python
with playlist.edit():
    playlist.tracks.pop()  # remove the last track
```

Reorder tracks by mutating the list inside the block:

```python
with playlist.edit():
    playlist.tracks.insert(0, playlist.tracks.pop())  # move the last track to the front
```

```{note}
Tracks are only sent to the service when the `edit()` block exits successfully. Make
all of your changes inside the block.
```

## Force the service to match a local playlist

{py:meth}`update() <plistsync.core.playlist.ServicePlaylist.update>` re-fetches the
playlist from the service and commits your local state to it, so the service matches the
object you edited. Use it when a playlist object may have diverged from the service, for
example after you changed it elsewhere. For the usual case of a few targeted changes,
prefer `edit()`, which produces fewer API calls:

```python
playlist.description = "Updated description"
playlist.update()
```

## Delete a playlist

{py:meth}`delete() <plistsync.core.playlist.ServicePlaylist.delete>` removes the
playlist from the service and returns an
{py:class}`OfflinePlaylist <plistsync.core.playlist.OfflinePlaylist>` holding the last
known state, so you do not lose the data:

```python
offline = playlist.delete()
print(offline.name, len(offline))
```

After deletion the playlist is gone from the service:

```python
assert library.get_playlist(id=playlist.id) is None
```

Do not keep using the deleted `playlist` object; switch to the returned `offline` one.
Its tracks are plain
{py:class}`OfflineTrack <plistsync.core.track.OfflineTrack>` objects, which you can use
to recreate the playlist on the same or another service.
