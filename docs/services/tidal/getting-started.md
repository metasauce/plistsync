# Getting Started

This guide will help you set up Tidal integration with `plistsync` from start to finish.

## Prerequisites

### Installation

First, install the Tidal optional dependencies:

::::{tab-set}
:sync-group: environment

:::{tab-item} pip
:sync: pip

```bash
pip install 'plistsync[tidal]'
```

:::

:::{tab-item} uv
:sync: uv

```bash
uv add plistsync --extra tidal
```

:::
::::

### Tidal Account

You'll need an active Tidal account. If you don't have one, sign up at [tidal.com](https://tidal.com).

### API Credentials

To authenticate with Tidal's API, you need to obtain API credentials:

1. Visit the [Tidal Developer Portal](https://developer.tidal.com/)
2. Log in with your Tidal account
3. Create a new application
4. Generate your `client_id` (and optionally `client_secret`)

**Note**: The `client_secret` is optional but recommended for improved authentication reliability.

## Configuration

Enable Tidal in your `plistsync` configuration file:

```yaml
# ./config/config.yaml
services:
  tidal:
    enabled: true
    client_id: your_tidal_client_id_here
    client_secret: your_tidal_client_secret_here # Optional but recommended
```

## Authentication

Once configured, authenticate `plistsync` with your Tidal account:

```bash
plistsync tidal auth
```

This will start an interactive authentication flow:

1. You'll be prompted to open a browser to Tidal's authorization page
2. Log in with your Tidal credentials
3. Grant `plistsync` the requested permissions
4. This will save an authentication token in the `config` folder

### Authentication Preview

<div class="only-light">

```{typer} plistsync.services.tidal.authenticate:tidal_cli
---
prog: plistsync tidal auth
theme: light
width: 80
---
```

</div>

<div class="only-dark">

```{typer} plistsync.services.tidal.authenticate:tidal_cli
---
prog: plistsync tidal auth
theme: dark
width: 80
---
```

</div>

## Verification

Test that everything is working by getting your user data:

```python
from plistsync.services.tidal.api import TidalApi
print(TidalApi().users.me())
```

This should return your user's ID and email.
