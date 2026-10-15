# Getting Started

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

## Authentication

Local files need no authentication. `plistsync` reads track metadata directly from disk.

## Verify

Read the metadata of a single track:

```python
from plistsync.services.local import LocalTrack

track = LocalTrack("./path_to_track.mp3")
print(track.title, track.primary_artist)
```

If the title and artist are printed, the service is installed correctly.

## Next steps

- [Library quickstart](../../library/getting-started.md): work with collections from Python.
- [Matching tracks](../../library/guides/matching.md): find your local tracks on a streaming service.
- [Core concepts](../../core-concepts.md): services, capabilities, playlists, and tracks.
