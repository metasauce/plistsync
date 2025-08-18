```{eval-rst}
.. meta::
   :description: Developer guide for track matching operations - single-track search and full-collection comparison.
```

# Matching Usage Guide

This guide covers the recommended **developer-facing API** for matching tracks in the `plistsync` library. It focuses on how to use the matching functions for two core tasks:

1. [**Single-track search**](single_track_search) - Find best match(es) for one track in a target collection  
2. [**Full-collection comparison**](full_collection_comparison) - Find matches between two collections (one-to-many/many-to-many)

```{important}
The matching system uses a **three-layer strategy** (global ID → local ID → metadata) as described in the {ref}`three_layer_matching_strategy` section. Understanding this approach might be beneficial for effective API usage.
```


## Quick References

```python
# TODO
```

(single_track_search)=
## Single-track search

```python
# TODO
```

(full_collection_comparison)=
## Full-collection comparison

```python
# TODO
```

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
