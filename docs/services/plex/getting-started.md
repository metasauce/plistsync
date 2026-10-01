# Getting Started

This guide will help you set up Plex integration with `plistsync` from start to finish.

## Prerequisites

### Installation

First, install the Plex optional dependencies:

::::{tab-set}
:sync-group: install-method

:::{tab-item} uv tool
:sync: uv-tool

Installs `plistsync` as a standalone CLI tool.

```bash
uv tool install "plistsync[plex]"
```

:::

:::{tab-item} pipx
:sync: pipx

Installs `plistsync` as a standalone CLI tool.

```bash
pipx install "plistsync[plex]"
```

:::

:::{tab-item} uv add
:sync: uv-add

Adds `plistsync` as a dependency of your project.

```bash
uv add plistsync --extra plex
```

:::

:::{tab-item} pip
:sync: pip

Installs into the current environment, works for both.

```bash
pip install "plistsync[plex]"
```

:::

::::

### Plex Account

You'll need an active Plex account to use this application. If you don't have one, sign up at [plex.tv](https://www.plex.tv). Additionally, you must have a self-hosted Plex Media Server instance running, as some API endpoints are not available through the public Plex API and require direct server access.

## Configuration

::::{tab-set}

:::{tab-item} CLI
:sync: cli

By default the `plex` service has a configuration section in your `plistsync` configuration file. If not, add the following snippet to your `config.yaml`:

```{plistsync-config} plistsync.services.plex.config.PlexConfig
:service: plex
```

:::

:::{tab-item} Library
:sync: library

Construct a plex configuration from custom values.

```{plistsync-config} plistsync.services.plex.config.PlexConfig
:type: library
```

:::

::::

## Authentication

Once configured, authenticate `plistsync` with your Plex account:

```bash
plistsync plex auth
```

This will start an interactive authentication flow:

1. You'll be prompted to open a browser to Plex's authorization page
2. Log in with your Plex credentials
3. Grant `plistsync` the requested permissions
4. This will save an authentication token in the `config` folder

To check whether the stored credentials are still valid without starting the flow
again:

```bash
plistsync plex auth --check
```

This prints `authenticated` and exits with code `0` if the token is valid, or
`not authenticated` with a non-zero exit code otherwise.

### Authentication Preview

```{typer} plistsync.cli.app:app::plex:auth
---
prog: plistsync plex auth
width: 80
---
```

## Verification

Test that everything is working by getting your user data:

```python
from plistsync.services.plex.api import PlexApi
print(PlexApi().identity())
```

This should return your ``machineIdentifier`` and some related metadata.
