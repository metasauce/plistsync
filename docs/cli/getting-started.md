```{warning}
The CLI guide is work in progress and may be missing some parts. Feel free to open an
issue or PR if you find something missing or unclear.
```

# Quickstart

This guide assumes `plistsync` is installed. See the [Getting started guide](../getting-started.md) for installation.

## Connect a service

Spotify, Tidal, and Plex use a browser login before `plistsync` can manage their
playlists:

```bash
plistsync spotify auth
plistsync tidal auth
plistsync plex auth
```

A browser window opens and asks you to log in. On a remote machine without a browser,
use `--mode manual` to paste the redirected URL instead:

```bash
plistsync spotify auth --mode manual
```

The token is stored in your user configuration directory and reused by all following
commands. Check it at any time:

```bash
plistsync spotify auth --check
```

Not every service works this way. Plex also needs your server settings in the
configuration, Traktor only needs a path to its NML file, and the `local` and `beets`
services are track sources without playlist commands. The service guides cover the
specifics.

## Explore the CLI

`--help` works on every level and is the fastest way to discover what you can do:

```bash
plistsync --help
plistsync spotify --help
plistsync spotify playlist --help
```

List the playlists of a service and inspect one:

```bash
plistsync spotify playlist list
plistsync spotify playlist show "My Playlist"
```

Playlist commands accept a playlist by name, serial, URL, or URI.

## Create your first playlist

The examples use Spotify. The same commands work for every service with playlist
support.

Create a playlist:

```bash
plistsync spotify playlist create --name "Road Trip" --description "Songs for the road" --yes
```

Find a track to add. Spotify can search by title, artist, and album. Other services
accept an ID:

```bash
plistsync spotify search track --title "Song" --artist "Artist"
```

Add the track by URL, serial, or ISRC:

```bash
plistsync spotify playlist update "Road Trip" --add "https://open.spotify.com/track/<id>" --yes
```

Show the result:

```bash
plistsync spotify playlist show "Road Trip"
```

Remove the first track, or the whole playlist:

```bash
plistsync spotify playlist update "Road Trip" --remove 0 --yes
plistsync spotify playlist remove "Road Trip"
```

`--yes` skips the confirmation prompt.

## Where to go next

- [Core concepts](../core-concepts.md): services, capabilities, playlists, and tracks.
- [CLI guide](commands.md): all commands and shared conventions.
- [Configuration](configuration.md): service settings, credentials, and logging.
- [Sync guide](../services/sync/index.md): keep playlists on different services in sync.
- Service guides: service-specific setup and commands in the sidebar.
