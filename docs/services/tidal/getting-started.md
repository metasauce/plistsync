# Getting Started

This guide sets up the Tidal integration with `plistsync` from start to finish. Once
connected, you can browse, search, create, and edit your Tidal playlists from the CLI or
the library, and sync them with other services.

## Prerequisites

- An active [Tidal account](https://tidal.com). Free accounts are sufficient for `plistsync`.

## Installation

Install the Tidal optional dependencies:

```{plistsync-install} tidal
```

## Configuration

::::{tab-set}
:sync-group: config-method

:::{tab-item} CLI
:sync: cli

By default the `tidal` service has a configuration section in your `plistsync` configuration file. If not, add the following snippet to your `config.yaml`:

```{plistsync-config} plistsync.services.tidal.config.TidalConfig
:service: tidal
```

:::

:::{tab-item} Library (inline)
:sync: library

Construct a tidal configuration in code from custom values you provide
directly:

```{plistsync-config} plistsync.services.tidal.config.TidalConfig
:type: library
```

:::

:::{tab-item} Library (from file)
:sync: file

Load the configuration from your user config directory, where the CLI stores the
values you configured:

```{plistsync-config} plistsync.services.tidal.config.TidalConfig
:type: file
```

:::

::::

:::{dropdown} API Credentials

We ship a default `client_id` for Tidal, but you can also create your own credentials if you want to.

If you want to use your own credentials, you need to obtain API credentials:

1. Visit the [Tidal Developer Portal](https://developer.tidal.com/)
2. Log in with your Tidal account
3. Create a new application
4. Generate your `client_id` (and optionally `client_secret`)

:::

## Authentication

Tidal uses OAuth: you log in once, after setting your `client_id` above. Start the
browser flow with the CLI:

```bash
plistsync tidal auth
```

On a machine without a browser, pass `--mode manual` and paste the redirected URL
instead:

```bash
plistsync tidal auth --mode manual
```

The token is stored in your Tidal config and reused by all later commands. Check it at
any time; `--check` prints `authenticated` and exits `0` when the token is valid, or
`not authenticated` and exits non-zero otherwise:

```bash
plistsync tidal auth --check
```

To authenticate from Python instead of the CLI, see the
[authentication guide](../../library/guides/authentication.md).

```{typer} plistsync.cli.app:app::tidal:auth
---
prog: plistsync tidal auth
width: 80
---
```

## Verify

List the playlists `plistsync` can see for your account:

```bash
plistsync tidal playlist list
```

If your playlists are printed, the service is installed, configured, and authenticated
correctly.

## Next steps

- [CLI quickstart](../../cli/getting-started.md): create, edit, and search playlists from the terminal.
- [CLI commands](../../cli/commands.md): the shared commands and conventions.
- [Sync playlists](../sync/index.md): keep this service in step with the others.
- [Core concepts](../../core-concepts.md): services, capabilities, playlists, and tracks.
