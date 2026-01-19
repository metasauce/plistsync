```{eval-rst}
.. meta::
   :description: Developer guide for track matching operations - single-track search and full-collection comparison.
```

# Matching Tracks

This guide covers the **user-facing API** for matching tracks using the `plistsync` library. It focuses on how to use the matching functions for two core tasks:

1. [**Single-track search**](single_track_search) - Find best match(es) for one track in a target collection (one-to-many)
2. [**Full-collection comparison**](full_collection_comparison) - Find matches between two collections (many-to-many)

```{important}
The matching system uses a **three-layer strategy** (global ID → local ID → metadata) as described in the {ref}`three_layer_matching_strategy` section. Understanding this approach might be beneficial for effective API usage.
```

## Quick References

```python
# Matching a single track in a collection
# Any combination of collection and track should work here
track = LocalTrack("./path_to_track.mp3")
collection = BeetsCollection("./path_to_beets_db.db")

matches = collection.match(track)
for match, similarity in matches:
    print(f"Found match: {match}, similarity: {similarity}")
```

(single_track_search)=

## Single-track search

Single-track search is performed using the high-level {meth}`~plistsync.core.collection.Collection.match` method. This method returns tracks from the target collection that are similar (or identical) to the source track, prioritizing global ID matches, local ID matches, and metadata similarity in that order.

Imagine you have a track file on your local computer that you've recently bought and ripped from a CD. You want to check if this track already exists in your Beets music collection, which maintains a large database of your music library. With the `match` method, you can automate this lookup efficiently:

```python
from plistsync.services.local import LocalTrack
from plistsync.services.beets import BeetsCollection

# This represents a single track on your local filesystem
source_track = LocalTrack("./path_to_source_track.mp3")

# BeetsCollection is an implementation of the Collection ABC, tailored to interact with a Beets database.
# It supports TrackStream (you can iterate over its tracks) and lookups via global ID or local ID
target_collection = BeetsCollection("./path_to_beets_db.db")

# Perform the match operation
matches = target_collection.match(source_track)

# Output the matches found
if len(matches.found) == 0:
    print("No matches found.")
else:
    for match, similarity in matches:
        print(f"Found match: {match.title} by {match.artist} from album {match.album}, similarity: {similarity}")
```

The similarity is calculated using the track's metadata and leveraging a levenstein distance algorithm for fuzzy matching. If you want to compute the distance between two tracks manually you may use the {meth}`~plistsync.core.matching.fuzzy_match` method.

### Advanced usage

Depending on the target collection, different search strategies might be available. Collections may implement {class}`~plistsync.core.collection.LocalLookup`, {class}`~plistsync.core.collection.GlobalLookup`, {class}`~plistsync.core.collection.InfoLookup` and {class}`~plistsync.core.collection.TrackStream` interfaces, which provide different methods for searching tracks. While the {meth}`~plistsync.core.collection.Collection.match` function will prioritize global ID matching, other methods may be more suitable depending on your requirements. In these cases you can explore the specific interface methods for more tailored search options.

(full_collection_comparison)=

## Full-collection comparison

This features is currently work in progress and not available in optimized form yet. For now
you may iterate over the tracks in both collections and match them individually.

(three_layer_matching_strategy)=

## Three-layer matching strategy

Our toolbox uses a **three-layer matching strategy**:

### 1. Global Unique Identifiers (`guid`)

Global Unique Identifiers are fields that are intended to uniquely identify a track across services and collections, such as ISRC, Spotify ID, Tidal ID, or MusicBrainz Recording ID. Because these identifiers are globally unique and stable across devices, a match found on one machine will reliably resolve on another. This makes `guid` matching the most reliable and fastest method in our system.

Each {class}`~plistsync.core.track.Track` exposes a {py:attr}`~plistsync.core.track.Track.global_ids` property, which returns a {class}`~plistsync.core.track.GlobalTrackIDs` instance containing the track's global identifiers.

### 2. Local Identifiers

Local Identifiers are scoped to a specific context, such as a device or a particular library. They can reliably identify tracks within that context but may produce false positives across different contexts. The exact scope depends on the type of identifier: for example, a file path is only meaningful on the device or network share where it exists, and library-specific IDs are only valid within their originating library (e.g., multiple Plex servers).

Each {class}`~plistsync.core.track.Track` exposes a {attr}`~plistsync.core.track.Track.local_ids` property, which returns a {class}`~plistsync.core.track.LocalTrackIDs` instance containing the track's local identifiers.

### 3. Metadata & Fuzzy Matching

Metadata and fuzzy matching are used as a fallback when no global or local identifiers can produce a reliable match. This includes attributes such as artist, album, track title. Matching at this layer relies on heuristics, fuzzy string comparisons, which makes it slower and less reliable than identifier-based matching, but it enables linking tracks across libraries even when identifiers are missing or inconsistent.

Each {class}`~plistsync.core.track.Track` exposes an {attr}`~plistsync.core.track.Track.info` property, which returns a dictionary of metadata fields used for these fallback comparisons. This layer does not include any global or local identifiers and is purely based on track metadata.
