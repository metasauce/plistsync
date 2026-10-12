# Getting Started

This guide sets up the Tidal integration with `plistsync` from start to finish.

## Prerequisites

- An active [Tidal account](https://tidal.com). Free accounts are sufficient for `plistsync`.
- `plistsync` must be authenticated with your Tidal account, see {ref}`the CLI authentication <tidal-cli-authenticate>` or {ref}`the library authentication <tidal-library-authenticate>`.

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

