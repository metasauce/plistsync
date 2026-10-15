# Getting Started

This guide sets up the Plex integration with `plistsync` from start to finish. Once
connected, you can browse, search, create, and edit your Plex playlists from the CLI or
the library, and sync them with other services.

## Prerequisites

### Plex account

You'll need an active Plex account to use this application. If you don't have one, sign up at [plex.tv](https://www.plex.tv). Additionally, you must have a self-hosted Plex Media Server instance running, as some API endpoints are not available through the public Plex API and require direct server access.

## Installation

Install the Plex optional dependencies:

```{plistsync-install} plex
```

## Configuration

::::{tab-set}
:sync-group: config-method

:::{tab-item} CLI
:sync: cli

By default the `plex` service has a configuration section in your `plistsync` configuration file. If not, add the following snippet to your `config.yaml`:

```{plistsync-config} plistsync.services.plex.config.PlexConfig
:service: plex
```

:::

:::{tab-item} Library (inline)
:sync: library

Construct a plex configuration in code from custom values you provide
directly:

```{plistsync-config} plistsync.services.plex.config.PlexConfig
:type: library
```

:::

:::{tab-item} Library (from file)
:sync: file

Load the configuration from your user config directory, where the CLI stores the
values you configured:

```{plistsync-config} plistsync.services.plex.config.PlexConfig
:type: file
```

:::

::::

## Authentication

Once your server settings are configured, authenticate `plistsync` with your Plex
account:

```bash
plistsync plex auth
```

The flow is interactive:

1. `plistsync` prints a link to Plex's authorization page.
2. Log in with your Plex credentials and grant the requested permissions.
3. The resulting token is stored in your Plex config and reused by all later commands.

On a machine without a browser, pass `--mode manual` and paste the redirected URL
instead:

```bash
plistsync plex auth --mode manual
```

Check whether the stored credentials are still valid without starting the flow again;
`--check` prints `authenticated` and exits `0` when the token is valid, or
`not authenticated` and exits non-zero otherwise:

```bash
plistsync plex auth --check
```

To authenticate from Python instead of the CLI, see the
[authentication guide](../../library/guides/authentication.md).

```{typer} plistsync.cli.app:app::plex:auth
---
prog: plistsync plex auth
width: 80
---
```

## Verify

List the playlists `plistsync` can see on your Plex server:

```bash
plistsync plex playlist list
```

If your playlists are printed, the service is installed, configured, and authenticated
correctly.

:::{dropdown} Check server connectivity directly

```python
from plistsync.services.plex.api import PlexApi
print(PlexApi().identity())
```

This prints your server's `machineIdentifier` and some related metadata.
:::

## Next steps

- [CLI quickstart](../../cli/getting-started.md): create, edit, and search playlists from the terminal.
- [CLI commands](../../cli/commands.md): the shared commands and conventions.
- [Sync playlists](../sync/index.md): keep this service in step with the others.
- [Core concepts](../../core-concepts.md): services, capabilities, playlists, and tracks.
