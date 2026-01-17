```{eval-rst}
.. meta::
   :description: Core concepts guide for plistsync library.
```

# Core Concepts

The `plistsync` library includes a suite of abstract base classes (ABCs) that establish the fundamental functionality and architecture. These classes serve as a foundation, allowing developers to create specific implementations tailored to various music platforms or formats. While the library comes with implementations for several popular platforms, users are encouraged to develop custom solutions by extending these classes.

## Tracks

A {py:class}`Track <plistsync.core.track.Track>` is the fundamental unit of music. It represents the metadata of a single piece of music and contains various common attributes. Each track can be identified by one of its {py:class}`unique identifiers <plistsync.core.track.TrackIdentifiers>`, such as ISRC or services specific IDs.

## Collections

A {py:class}`Collection <plistsync.core.collection.Collection>` is a data structure that holds multiple `Tracks`. It provides methods to access, filter, and iterate over the tracks. Collections can represent libraries, playlists, or databases of music tracks.

## Matches

When trying to sync or {py:class}`match <plistsync.core.matching.Matches>` tracks between different platforms, `plistsync` uses a set of matching strategies. Currently we prioritize matching tracks based on their unique identifiers first and then fall back to matching based on metadata attributes like title, artist, and album. This ensures that tracks are matched as accurately as possible across different platforms. For more details, please refer to the [matching documentation](./matching.md).

## Services

A service within `plistsync` is an implementation targeting a specific music platform or format. Services are tasked with interacting with the platform's API, managing music metadata, and translating between the platform's data structures and those used by other platforms. `plistsync` includes services for several popular platforms, and users can expand this by creating new services using the base service classes provided by the library.
