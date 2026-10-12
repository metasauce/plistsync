```{eval-rst}
.. meta::
   :description: Developer guide for track matching: single-track search and full-collection comparison.
```

# Matching Tracks

This guide covers matching tracks with the `plistsync` library for two tasks:

1. [**Single-track search**](single_track_search): find the best matches for one track in a target collection (one-to-many).
2. [**Full-collection comparison**](full_collection_comparison): find matches between two collections (many-to-many).

```{important}
Matching follows a [three-layer strategy](matching_order): global identifiers first, then local identifiers, then metadata similarity.
```

## Quick reference

```python
from plistsync.cli.config import UserDirConfigIO
from plistsync.services.local import LocalTrack
from plistsync.services.spotify import SpotifyConfig, SpotifyLibrary

library = SpotifyLibrary.from_config(UserDirConfigIO().load(SpotifyConfig))

track = LocalTrack("./path_to_track.mp3")
matches = library.match(track)
for candidate, similarity in matches:
    print(f"Found match: {candidate.title}, similarity: {similarity:.2f}")
```

```python
# Match many tracks in one batch
tracks = [LocalTrack(f"./track_{i}.mp3") for i in range(100)]

for matches in library.match_many(tracks):
    if matches.best_match is not None:
        print(f"{matches.truth.title}: {matches.best_match.title} ({matches.similarity:.2f})")
    else:
        print(f"{matches.truth.title}: no match")
```

(single_track_search)=

## Single-track search

Single-track search uses the {meth}`~plistsync.core.collection.Collection.match` method. It returns tracks from the target collection that are similar to the source track, prioritizing global identifiers, local identifiers, and metadata similarity in that order.

Imagine you have a track file on your local computer that you ripped from a CD and now want to find on Spotify:

```python
from plistsync.cli.config import UserDirConfigIO
from plistsync.services.local import LocalTrack
from plistsync.services.spotify import SpotifyConfig, SpotifyLibrary

# This represents a single track on your local filesystem
source_track = LocalTrack("./path_to_source_track.mp3")

# Access to Spotify
target_collection = SpotifyLibrary.from_config(
    UserDirConfigIO().load(SpotifyConfig)
)

# Find the source track in the target collection
matches = target_collection.match(source_track)

if len(matches.found) == 0:
    print("No matches found.")
else:
    for match, similarity in matches:
        artist = match.primary_artist or "unknown artist"
        print(f"Found {match.title} by {artist} (similarity: {similarity:.2f})")
```

Similarity is computed from track metadata with {func}`~plistsync.core.matching.fuzzy_match`, which uses a normalized Levenshtein ratio per shared metadata field.

:::{dropdown} Advanced usage

Depending on the target collection, different search strategies might be available. Collections may implement the {class}`~plistsync.core.collection.IDLookup`, {class}`~plistsync.core.collection.InfoLookup`, and {class}`~plistsync.core.collection.TrackStream` protocols, which provide different ways to search tracks. {meth}`~plistsync.core.collection.Collection.match` prioritizes global identifiers, but the protocol methods can be more suitable for other requirements.

:::

(full_collection_comparison)=

## Full-collection comparison

When you need to match many tracks against the same collection, use {meth}`~plistsync.core.collection.Collection.match_many`. It accepts an iterable of tracks and yields a {class}`~plistsync.core.matching.Matches` result for each, in input order.

```python
from plistsync.cli.config import UserDirConfigIO
from plistsync.services.local import LocalCollection
from plistsync.services.spotify import SpotifyConfig, SpotifyLibrary

spotify = SpotifyLibrary.from_config(UserDirConfigIO().load(SpotifyConfig))
local = LocalCollection("./my_music")

# Batch-match every local track against the Spotify library
for result in spotify.match_many(local):
    if result.best_match is not None:
        print(f"{result.truth.title}: {result.best_match.title}")
    else:
        print(f"{result.truth.title}: no match")
```

```{tip}
{meth}`~plistsync.core.collection.Collection.match_many` is logically equivalent to calling {meth}`~plistsync.core.collection.Collection.match` for each track, but it can be more efficient when the collection implements batched lookup ({meth}`~plistsync.core.collection.IDLookup.find_many_by_ids` and {meth}`~plistsync.core.collection.InfoLookup.find_many_by_info`).
```

### Matching with a fallback

A common pattern is to try a smaller, faster collection first (for example a playlist) and fall back to a larger one (for example the full library) for tracks that were not found:

```python
# Try the playlist first, then the library for misses
results = list(playlist.match_many(queries))

unmatched = [(i, queries[i]) for i, r in enumerate(results) if r.best_match is None]
if unmatched:
    indices, remaining = zip(*unmatched)
    for idx, match in zip(indices, library.match_many(remaining)):
        results[idx] = match
```

This two-phase batching avoids touching the library for tracks already resolved by the playlist, while still benefiting from batched lookups in both phases.

(matching_order)=

## Matching order

Matching works through three layers, from most to least reliable:

### 1. Global identifiers

Global identifiers are intended to identify a track across services and libraries, for example an ISRC or a service-specific track ID. They are stable across devices, so a match found on one machine resolves on another. This makes them the most reliable and fastest way to match.

Each {class}`~plistsync.core.track.Track` exposes its identifiers through the {py:attr}`~plistsync.core.track.Track.ids` property. Every {class}`~plistsync.core.ids.TrackID` carries a {class}`~plistsync.core.ids.Scope`, and global identifiers use `Scope.GLOBAL`.

### 2. Local identifiers

Local identifiers are scoped to one context, such as a device or a particular library. They identify tracks reliably within that context but can produce false positives across contexts. A file path is only meaningful on the device or network share where it exists, and a library-specific ID is only valid in its originating library, for example one Plex server out of several.

Local identifiers use `Scope.LOCAL` and include {class}`~plistsync.core.ids.FilePath`.

### 3. Metadata and fuzzy matching

Metadata and fuzzy matching are the fallback when no identifier produces a reliable match. This layer uses attributes such as title, artists, and albums. It relies on heuristics and fuzzy string comparison, which makes it slower and less reliable, but it can link tracks across libraries even when identifiers are missing or inconsistent.

Each {class}`~plistsync.core.track.Track` exposes its metadata through the {py:attr}`~plistsync.core.track.Track.info` property. This layer is purely metadata based.

Collections without {class}`~plistsync.core.collection.IDLookup` or {class}`~plistsync.core.collection.InfoLookup` fall back to streaming every track through the same comparison, which is much slower.
