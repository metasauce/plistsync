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

By default the `traktor` service should have a configuration option in your `plistsync` configuration file. If not, you can add the following snippet to your `config.yaml` file:


```yaml
# ./config/config.yaml
services:
  traktor:
    # The absolute path to the nml file you want to use as your default traktor
    # library.
    path: /replace/me/with/a/path/to/nml.nml
    # Create a backup of the libraries nml file before every write.
    backup_before_write: true

```
