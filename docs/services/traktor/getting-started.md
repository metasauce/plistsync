# Getting Started

This guide will help you set up Traktor integration with `plistsync` from start to finish.

## Prerequisites

### Installation

First, install the Traktor optional dependencies:

::::{tab-set}
:sync-group: environment

:::{tab-item} pip
:sync: pip

```bash
pip install 'plistsync[traktor]'
```

:::

:::{tab-item} uv
:sync: uv

```bash
uv add plistsync --extra traktor
```

:::
::::

## Configuration

Enable Traktor in your `plistsync` configuration file:

```yaml
# ./config/config.yaml
services:
  traktor:
    enabled: true
```
