# Getting Started

This guide will help you set up Traktor integration with `plistsync` from start to finish.

## Prerequisites

### Installation

First, install the Traktor optional dependencies:

::::{tab-set}
:sync-group: install-method

:::{tab-item} uv tool
:sync: uv-tool

Installs `plistsync` as a standalone CLI tool.

```bash
uv tool install "plistsync[traktor]"
```

:::

:::{tab-item} pipx
:sync: pipx

Installs `plistsync` as a standalone CLI tool.

```bash
pipx install "plistsync[traktor]"
```

:::

:::{tab-item} uv add
:sync: uv-add

Adds `plistsync` as a dependency of your project.

```bash
uv add plistsync --extra traktor
```

:::

:::{tab-item} pip
:sync: pip

Installs into the current environment, works for both.

```bash
pip install "plistsync[traktor]"
```

:::

::::

## Configuration

::::{tab-set}

:::{tab-item} CLI
:sync: cli

By default the `traktor` service has a configuration section in your `plistsync` configuration file. If not, add the following snippet to your `config.yaml`:

```{plistsync-config} plistsync.services.traktor.config.TraktorConfig
:service: traktor
```

:::

:::{tab-item} Library
:sync: library

Construct a traktor configuration from custom values.

```{plistsync-config} plistsync.services.traktor.config.TraktorConfig
:type: library
```

:::

::::
