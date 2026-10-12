# Quickstart

This guide starts from an installed `plistsync`. See the
[Getting started guide](../getting-started.md) for installation. For the Spotify
example below, install its extra:

```bash
uv add "plistsync[spotify]"
```

## Before you start

The example talks to your Spotify account, so it needs an access token first. The CLI
stores one in your user config directory:

```bash
plistsync spotify auth
```

```{note}
Spotify requires your own API credentials and a paid account. See the
[Spotify setup guide](../services/spotify/getting-started.md) for details.
```

To obtain a token without the CLI, see the [Authentication](guides/authentication.md)
guide.

## Your first script

`plistsync` abstracts away the hard parts of working with music services, so scripting
stays simple. Tracks, playlists, and authentication are normalized across services, and
the example below builds a library from a config and works with a playlist in just a few
lines. The same pattern applies to the Tidal, Plex, and Traktor libraries.

```python
from plistsync.cli.config import UserDirConfigIO
from plistsync.services.spotify import SpotifyConfig, SpotifyLibrary

# Load the config and token from your user config directory
config = UserDirConfigIO().load(SpotifyConfig)

# Build the library from the config
library = SpotifyLibrary.from_config(config)

# Find the playlist, or create it if it does not exist yet
playlist = library.get_playlist(name="My Playlist")
if playlist is None:
    playlist = library.create_playlist(
        name="My Playlist",
        description="Created with plistsync",
    )

# Print how many tracks the playlist has
print(f"{playlist.name}: {len(playlist)} tracks")
```

The config can also be built inline instead of read from the user directory, see the
[Configuration](guides/configuration.md) guide.

## Where to go next

- [Core concepts](../core-concepts.md): the vocabulary shared by all services.
- [Configuration](guides/configuration.md): configs from a file or inline.
- [Authentication](guides/authentication.md): token flows from Python.
- [Logging](guides/logging.md): configure the `plistsync` logger.
- {doc}`Examples <examples/readme>`: ready-to-run notebooks and scripts.
- {doc}`API reference <../reference/api/index>`: every module and class.
