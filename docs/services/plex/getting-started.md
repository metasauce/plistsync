# Getting Started

This guide will help you set up Plex integration with `plistsync` from start to finish.

## Prerequisites

### Installation

First, install the Plex optional dependencies:

::::{tab-set}
:sync-group: environment

:::{tab-item} pip
:sync: pip

```bash
pip install 'plistsync[plex]'
```

:::

:::{tab-item} uv
:sync: uv

```bash
uv add plistsync --extra plex
```

:::
::::

### Plex Account

You'll need an active Plex account to use this application. If you don't have one, sign up at [plex.tv](https://www.plex.tv). Additionally, you must have a self-hosted Plex Media Server instance running, as some API endpoints are not available through the public Plex API and require direct server access.

## Configuration

Enable Plex in your `plistsync` configuration file:

```yaml
# ./config/config.yaml
services:
  plex:
    enabled: true
    server_url: your_plex_server_url_here
    server_name: optional_server_name
```

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

### Authentication Preview

<div class="only-light">

```{typer} plistsync.services.plex.authenticate:plex_cli
---
prog: plistsync plex auth
theme: light
width: 80
---
```

</div>

<div class="only-dark">

```{typer} plistsync.services.plex.authenticate:plex_cli
---
prog: plistsync plex auth
theme: dark
width: 80
---
```

</div>

## Verification

Test that everything is working by getting your user data:

```python
from plistsync.services.plex.api import PlexApi
print(PlexApi().identity())
```

This should return your machineIdentifier and some related metadata.
