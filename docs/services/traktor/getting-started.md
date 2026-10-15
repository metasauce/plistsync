# Getting Started

This guide sets up the Traktor integration with `plistsync` from start to finish. Once
connected, you can browse, create, and edit the playlists in your Traktor library, and
sync them with other services.

## Prerequisites

- Traktor installed, with an existing library file (`collection.nml`). If you have used
  Traktor, this file already exists.

## Installation

Install the Traktor optional dependencies:

```{plistsync-install} traktor
```

## Configuration

::::{tab-set}
:sync-group: config-method

:::{tab-item} CLI
:sync: cli

By default the `traktor` service has a configuration section in your `plistsync` configuration file. If not, add the following snippet to your `config.yaml`:

```{plistsync-config} plistsync.services.traktor.config.TraktorConfig
:service: traktor
```

:::

:::{tab-item} Library (inline)
:sync: library

Construct a traktor configuration in code from custom values you provide
directly:

```{plistsync-config} plistsync.services.traktor.config.TraktorConfig
:type: library
```

:::

:::{tab-item} Library (from file)
:sync: file

Load the configuration from your user config directory, where the CLI stores the
values you configured:

```{plistsync-config} plistsync.services.traktor.config.TraktorConfig
:type: file
```

:::

::::

`path` must be the absolute path to *your* `collection.nml` file, inside your Native
Instruments / Traktor folder. The default value is a placeholder and will not work
until you replace it.

```{warning}
`plistsync` writes back to the NML file when you edit playlists. `backup_before_write`
is enabled by default and creates a copy before every write; only turn it off if you
keep your own backups. Edit with Traktor closed to avoid conflicting writes.
```

## Authentication

Traktor is read from a local NML file, so no authentication is required. Once `path`
points at your library, you are ready to go.

## Verify

List the playlists in your Traktor library:

```bash
plistsync traktor playlist list
```

If your playlists are printed, the service is installed and configured correctly.

## Next steps

- [CLI quickstart](../../cli/getting-started.md): create, edit, and search playlists from the terminal.
- [CLI commands](../../cli/commands.md): the shared commands and conventions.
- [Sync playlists](../sync/index.md): keep this service in step with the others.
- [Core concepts](../../core-concepts.md): services, capabilities, playlists, and tracks.
