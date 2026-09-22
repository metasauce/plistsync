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

## Authenticating a service

Streaming services need a one-time authentication before you can manage their playlists:

```bash
plistsync <service> auth
```

A browser window opens and asks you to log in. If you run `plistsync` on a remote machine without a browser, use manual mode, which asks you to paste the redirected URL instead:

```bash
plistsync <service> auth --mode manual
```

Not every service needs authentication. Some work with local files and only need a little configuration instead. Every service is set up differently, see the corresponding service guide.

## Configuration

`plistsync` stores its settings in a YAML configuration file, managed through the CLI:

```bash
plistsync config ls        # show the current configuration
plistsync config path      # where the file lives
plistsync config edit      # edit it in your default editor
plistsync config validate  # check it against the schema
```

Most services work out of the box. If a service needs settings like a client ID or a file path, its service guide tells you what to put in. See the [configuration page](configuration.md) for details, including logging.
