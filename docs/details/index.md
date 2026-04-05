
# Overview

Managing music across multiple platforms and storage formats is notoriously difficult. Each service (Spotify, Tidal, Plex) and format (local files, Traktor NML) uses different identifiers, metadata formats, and APIs. Users often find themselves:

- Locked into a single ecosystem because migrating playlists is too tedious
- Maintaining duplicate libraries across services with no way to sync changes
- Losing metadata (track BPM, key, etc.) when transferring between platforms

`plistsync` solves this by providing a unified abstraction layer that normalizes tracks, collections, and playlists from various services into a common format. This enables seamless synchronization while handling the complexities of different APIs, authentication methods, and metadata formats.

In the following we will give you a primer on our library architecture which should ease the starting threshold and allow you to jump into the nitty gritty quicker.

:::{toctree}
:maxdepth: 2
:caption: Contents


architecture.md
core-concepts.md
:::
