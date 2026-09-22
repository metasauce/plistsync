# Getting started

```{note}
This guide assumes you want to use `plistsync` from the command line. If you are looking to use the Python library instead, start with the [core concepts](library/core-concepts.md).
```

```{include} ../README.md
:start-after: <!-- start overview -->
:end-before: <!-- end overview -->
```

## Installation

<!-- start installation -->

Install `plistsync` from [PyPI](https://pypi.org/project/plistsync/) as a standalone tool:

::::{tab-set}
:sync-group: install-method

:::{tab-item} uv tool
:sync: uv-tool

```bash
uv tool install "plistsync[allservices]"
```

:::

:::{tab-item} pipx
:sync: pipx

```bash
pipx install "plistsync[allservices]"
```

:::

:::{tab-item} pip
:sync: pip

```bash
pip install "plistsync[allservices]"
```

:::

::::

To keep the package slim and flexible, all services (like Spotify or Tidal) are optional. The commands above include all of them via the `allservices` extra, drop it if you want only the core.

```{note}
`plistsync` follows [Semantic Versioning](https://semver.org/). While we strive to maintain backward compatibility within the same major version, **we strongly recommend using a lockfile** (such as `requirements.txt` for pip or `uv.lock` for uv) to prevent unexpected breaking changes when upgrading between major versions.
```

<!-- end installation -->

## Using the CLI

The command line is the fastest way to manage your playlists, no coding required. Every service speaks the same syntax, so once you get a feel for the commands, they work with every service.

Check that everything works:

```bash
plistsync --help
```

For example, inspect a playlist:

```bash
plistsync <service> playlist list
plistsync <service> playlist show <playlist>
```

`<playlist>` can be a playlist name or its ID. All available services have their own guide in the sidebar. For more information about the available commands, see either each command's help page or the [CLI guide](cli/commands.md).

## Using the Python API

Prefer code? Everything the CLI does just wraps our core library. You can use it programatically if you prefer. For example, this creates a playlist (or finds it) and prints its track count:

```python
from plistsync.services.spotify import SpotifyLibrary

library = SpotifyLibrary()

playlist = library.get_playlist(name="My Playlist")
if playlist is None:
    playlist = library.create_playlist(name="My Playlist")

print(f"{playlist.name}: {len(playlist.tracks)} tracks")
```

To properly understand what happens under the hood and how to use the `plistsync` abstraction, we recommend starting with the [core concepts](library/core-concepts.md).
