```{warning}
The command line documentation is work in progress and may be missing some parts.
Feel free to open an issue or PR if you find something missing or unclear.
```

# Quickstart

This guide assumes `plistsync` is installed. See the {doc}`Getting started guide <../getting-started>`
for installation.

## Connect a service

`plistsync` can only use services that are installed and connected. That setup is done
once per service, and it is described in one place: {doc}`Services <../services/index>`
has a table of what each service supports and a page per service with the exact steps.

For services that use a browser login, the command is always the same:

```bash
plistsync tidal auth
plistsync spotify auth
```

A browser window opens and asks you to log in. The token is stored in your user
configuration directory and reused by all following commands. On a machine without a
browser, add `--mode manual` and paste the redirected URL instead, and `--check` tells
you whether the stored token is still valid.

Services that read local files, such as `traktor` and `local`, need no login. They only
need their configuration. So check the {doc}`service page <../services/index>` for the
service you want to use before continuing.

## Explore the CLI

`--help` works on every level and is the fastest way to discover what you can do:

```bash
plistsync --help
plistsync tidal --help
plistsync tidal playlist --help
```

List the playlists of a service and inspect one:

```bash
plistsync tidal playlist list
plistsync tidal playlist show "My Playlist"
```

Playlist commands accept a playlist by name, serial, URL, or URI.

## Create your first playlist

The examples use tidal. The same commands work for every service with playlist
support.

Create a playlist:

```bash
plistsync tidal playlist create --name "Road Trip" --description "Songs for the road" --yes
```

Find a track to add. Tidal can search by title, artist, and album. Other services
accept an ID:

```bash
plistsync tidal search track --title "Song" --artist "Artist"
```

Add the track by URL, serial, or ISRC:

```bash
plistsync tidal playlist update "Road Trip" --add "https://tidal.com/track/571470960/u" --yes
```

Show the result:

```bash
plistsync tidal playlist show "Road Trip"
```

Remove the first track, or the whole playlist:

```bash
plistsync tidal playlist update "Road Trip" --remove 0 --yes
plistsync tidal playlist remove "Road Trip"
```

`--yes` skips the confirmation prompt.

## Where to go next

- {doc}`Services <../services/index>`: connect a service and check what it supports.
- {ref}`Editing playlists <cli_playlist_editing>`: list, create, change, and delete playlists.
- {doc}`Core concepts <../core-concepts>`: services, capabilities, playlists, and tracks.
- {doc}`Configuration <configuration>`: the config file, credentials, and logging.
- {doc}`Sync <../services/sync/index>`: keep playlists on different services in sync.
