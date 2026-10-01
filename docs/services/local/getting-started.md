# Getting Started

This guide will help you set up Local Filesystem integration with `plistsync` from start to finish.

## Prerequisites

### Installation

First, install the optional dependencies:

::::{tab-set}
:sync-group: install-method

:::{tab-item} uv tool
:sync: uv-tool

Installs `plistsync` as a standalone CLI tool.

```bash
uv tool install "plistsync[local]"
```

:::

:::{tab-item} pipx
:sync: pipx

Installs `plistsync` as a standalone CLI tool.

```bash
pipx install "plistsync[local]"
```

:::

:::{tab-item} pip
:sync: pip

Installs into the current environment, works for both.

```bash
pip install "plistsync[local]"
```

:::

:::{tab-item} uv add
:sync: uv-add

Adds `plistsync` as a dependency of your project.

```bash
uv add plistsync --extra local
```

:::

::::
