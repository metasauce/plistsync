# Getting Started

This guide sets up the Tidal integration with `plistsync` from start to finish.

## Prerequisites

- An active [Tidal account](https://tidal.com). Free accounts are sufficient for `plistsync`.
- `plistsync` must be authenticated with your Tidal account, see {ref}`the CLI authentication <tidal-cli-authenticate>` or {ref}`the library authentication <tidal-library-authenticate>`.

## Installation

Install the Tidal optional dependencies:

::::{tab-set}
:sync-group: install-method

:::{tab-item} uv tool
:sync: uv-tool

Installs `plistsync` as a standalone CLI tool.

```bash
uv tool install "plistsync[tidal]"
```

:::

:::{tab-item} pipx
:sync: pipx

Installs `plistsync` as a standalone CLI tool.

```bash
pipx install "plistsync[tidal]"
```

:::

:::{tab-item} uv add
:sync: uv-add

Adds `plistsync` as a dependency of your project.

```bash
uv add plistsync --extra tidal
```

:::

:::{tab-item} pip
:sync: pip

Installs into the current environment.

```bash
pip install "plistsync[tidal]"
```

:::

::::

## Configuration

::::{tab-set}

:::{tab-item} CLI
:sync: cli

By default the `tidal` service has a configuration section in your `plistsync` configuration file. If not, add the following snippet to your `config.yaml`:

```{plistsync-config} plistsync.services.tidal.config.TidalConfig
:service: tidal
```

:::

:::{tab-item} Library
:sync: library

Construct a tidal configuration from custom values.

```{plistsync-config} plistsync.services.tidal.config.TidalConfig
:type: library
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

