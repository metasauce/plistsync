# Local

This guide sets up the local filesystem integration with `plistsync` from start to
finish. The local service is a track source rather than a full library: it reads
metadata from audio files on disk so you can match them against, or transfer them to,
other services.

## Prerequisites

- Audio files on a local disk or a mounted network share.

## Installation

Install the local optional dependencies:

```{plistsync-install} local
```

## Configuration

The local service has no configuration file section. You point it at a path when you
construct it in code: a directory with `LocalCollection`, or a single file with
`LocalTrack`.

A single file can be read directly. The tags come from the file itself:

```python
from plistsync.services.local import LocalTrack

track = LocalTrack("./path_to_track.mp3")
print(track.title, track.primary_artist)
```

## Authentication

Local files need no authentication. `plistsync` reads track metadata directly from disk.

## Next steps

- {doc}`Library quickstart <../../library/getting-started>`: work with collections from Python.
- {doc}`Matching tracks <../../library/guides/matching>`: find your local tracks on a streaming service.
- {doc}`Core concepts <../../core-concepts>`: services, capabilities, playlists, and tracks.

% TODO: add guide collections and tracks once implemented
