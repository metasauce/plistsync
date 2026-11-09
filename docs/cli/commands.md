```{warning}
The command line documentation is work in progress and may be missing some parts.
Feel free to open an issue or PR if you find something missing or unclear.
```

# Commands

The command line is the fastest way to manage your playlists. Every service speaks the same syntax, so once you get a feel for the commands, they work with every service.

## Discovering commands

`--help` works on every level and is the fastest way to find out what you can do:

```bash
plistsync --help
plistsync <service> --help
plistsync <service> playlist --help
```

The top level lists all commands and the services you have installed, each service lists its commands, and every command has a help page describing its arguments and options.

Services that are track sources only, such as `local`, install no commands, and `plistsync --version` prints which services are available in your installation. Every other service has its own page with its commands and options.

## Authenticating a service

Streaming services need a one-time authentication before you can manage their playlists:

```bash
plistsync <service> auth
```

A browser window opens and asks you to log in. If you run `plistsync` on a remote machine without a browser, use manual mode, which asks you to paste the redirected URL instead:

```bash
plistsync <service> auth --mode manual
```

Not every service needs authentication. Some work with local files and only need a little configuration instead. Each service is set up differently, see the {doc}`service pages <../services/index>` for the details.

(cli_playlist_editing)=

## Editing playlists

These commands are the same for every service that supports playlist editing, see the
{doc}`service overview <../services/index>`. A playlist is addressed by its **name,
serial, URL, or URI**, so you can paste a link from the web player instead of looking up
an ID.

**List and show.** `list` prints the playlists in your library, `show` prints one
playlist with its tracks, in order:

```bash
plistsync spotify playlist list
plistsync spotify playlist show "Road Trip"
```

**Create.** `--add` seeds the new playlist right away and can be given more than once:

```bash
plistsync spotify playlist create --name "Road Trip" --description "Songs for the road"
```

**Add and remove tracks.** Both options can be repeated. A track is given as an ID, URL,
URI, or ISRC. For `--remove`, a bare number is the position in the playlist and counts
from zero, so `--remove 0` removes the first track. A URL, URI, or ID removes the first
track that matches it:

```bash
plistsync spotify playlist update "Road Trip" --add <track>
plistsync spotify playlist update "Road Trip" --remove 0
```

The CLI adds and removes tracks, but does not reorder them. To change the order, use the
{doc}`Python library <../library/guides/playlists>`.

**Search.** `playlist search` finds playlists by name or description pattern.
`search track` takes `--title`, `--artist`, and `--album` on services that can search by
metadata. Elsewhere those options do not exist, and a track is found by ID or URL:

```bash
plistsync spotify playlist search --name "Road"
plistsync spotify search track --title "Song" --artist "Artist"
```

**Delete.** Removing a playlist asks before deleting it:

```bash
plistsync spotify playlist remove "Road Trip"
```

Commands that change a playlist show you what will happen and ask first. Pass `--yes`
(`-y`) to skip the question, which is what you want in scripts.

## Configuration

`plistsync` stores its settings in a YAML configuration file, managed through the CLI:

```bash
plistsync config ls        # show the current configuration
plistsync config path      # where the file lives
plistsync config edit      # edit it in your default editor
plistsync config validate  # check it against the schema
```

Most services work out of the box. If a service needs settings like a client ID or a file path, its {doc}`service page <../services/index>` tells you what to put in. See the {doc}`configuration page <configuration>` for details, including logging.
