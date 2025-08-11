# Core Concepts

`plistsync` is a Python library designed to manage and synchronize music metadata across various platforms. It provides a structured way to handle music tracks, collections, and their associated metadata.


We provide a set of abstract base classes (ABCs) that define the core functionality and structure of the library. These classes can be extended to create specific implementations for different music platforms or formats. We ship with a few implementations for popular music platforms, but you can create your own by extending these ABCs.


## Tracks

```{currentmodule} plistsync.services.abc
```

A {py:class}`Track <track.Track>` is the fundamental unit of music. It represents the metadata of a single piece of music and contains various common attributes. Each track can be identified by its {py:class}`unique identifiers <track.TrackIdentifiers>`, such as ISRC or services specific IDs.

## Collections



A {py:class}`Collection <collection.Collection>` is a data structure that holds multiple `Tracks`. It provides methods to access, filter, and iterate over the tracks. Collections can represent libraries, playlists, or databases of music tracks.

## Matching tracks

When trying to sync or match tracks between different platforms, `plistsync` uses a set of matching strategies. Currently we prioritize matching tracks based on their unique identifiers first and then fall back to matching based on metadata attributes like title, artist, and album. This ensures that tracks are matched as accurately as possible across different platforms.