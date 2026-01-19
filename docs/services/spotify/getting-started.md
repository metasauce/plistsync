# Getting Started

This guide will help you set up Spotify integration with `plistsync` from start to finish.

## Prerequisites

### Installation

First, install the Spotify optional dependencies:

::::{tab-set}
:sync-group: environment

:::{tab-item} pip
:sync: pip

```bash
pip install 'plistsync[spotify]'
```

:::

:::{tab-item} uv
:sync: uv

```bash
uv add plistsync --extra spotify
```

:::
::::

### Spotify Account

You'll need an active Spotify account. If you don't have one, sign up at [spotify.com](https://spotify.com).

### API Credentials

To authenticate with Spotify's API, you need to obtain API credentials:

1. Visit the [Spotify Developer Portal](https://developer.spotify.com/)
2. Log in with your Spotify account
3. Create a new application
4. Generate your `client_id` (and optionally `client_secret`)

## Configuration

Enable Tidal in your `plistsync` configuration file:

```yaml
# ./config/config.yaml
services:
  spotify:
    enabled: true
    client_id: your_spotify_client_id_here
    client_secret: your_spotify_client_secret_here # Optional but recommended
```

## Authentication

Once configured, authenticate `plistsync` with your Tidal account:

```bash
plistsync spotify auth
```

This will start an interactive authentication flow:

1. You'll be prompted to open a browser to Tidal's authorization page
2. Log in with your Tidal credentials
3. Grant `plistsync` the requested permissions
4. This will save an authentication token in the `config` folder

### Authentication Preview

<div class="only-light">

```{typer} plistsync.services.spotify.authenticate:spotify_cli
---
prog: plistsync spotify auth
theme: light
width: 80
---
```

</div>

<div class="only-dark">

```{typer} plistsync.services.spotify.authenticate:spotify_cli
---
prog: plistsync spotify auth
theme: dark
width: 80
---
```

</div>

## Verification

Test that everything is working by getting your user data:

```python
from plistsync.services.spotify.api import SpotifyApi
print(SpotifyApi().user.me())
```

This should return your user's ID and email.
