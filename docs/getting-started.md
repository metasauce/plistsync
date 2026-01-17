# Getting started

```{include} ../README.md
:start-after: <!-- start overview -->
:end-before: <!-- end overview -->
```

## Installation

<!-- start installation -->

You can install `plistsync` from [PyPi](https://pypi.org/project/plistsync/).

::::{tab-set}
:sync-group: environment

:::{tab-item} pip
:sync: pip

```bash
pip install plistsync
```

:::

:::{tab-item} uv
:sync: uv

```bash
uv add plistsync
```

:::
::::

```{note}
`plistsync` follows [Semantic Versioning](https://semver.org/). While we strive to maintain backward compatibility within the same major version, **we strongly recommend using a lockfile** (such as `requirements.txt` for pip or `uv.lock` for uv) to prevent unexpected breaking changes when upgrading between major versions.
```

<!-- end installation -->

## First steps

To get started with plistsync, you have a few recommended paths:

:::::{grid} 1 3 3 3
:gutter: 2

::::{grid-item-card} Core Concepts
:link: details/core-concepts
:link-type: doc

Understand the key abstractions and notation of `plistsync`. Learn about `Tracks`, `Collections`, `Matches`, and `Services`, which form the foundation of the library.
::::

::::{grid-item-card} Examples
:link: /examples
:link-type: doc

Follow step-by-step guides to see `plistsync` in action. Great for hands-on learning and testing common workflows.
::::

::::{grid-item-card} References
:link: api/index
:link-type: doc

Find in-depth reference material, API documentation, and additional resources to deepen your understanding of `plistsync`.
::::
:::::
