# Getting started

```{include} ../README.md
:start-after: <!-- start overview -->
:end-before: <!-- end overview -->
```

## Installation

`plistsync` is available on [PyPI](https://pypi.org/project/plistsync/). Pick the install method that matches how you want to use it:

```{plistsync-install} allservices
```

To keep the package slim and flexible, all services (like Spotify or Tidal) are optional. The commands above include all of them via the `allservices` extra. Drop it to install only the core.

```{note}
`plistsync` follows [Semantic Versioning](https://semver.org/). While we strive to maintain backward compatibility within the same major version, **we strongly recommend using a lockfile** (such as `requirements.txt` for pip or `uv.lock` for uv) to prevent unexpected breaking changes when upgrading between major versions.
```

## Choose your path

The same core powers both the command line tool and the Python library. Pick whichever fits your workflow. You can always switch later. Both paths share the same vocabulary, explained in [Core concepts](core-concepts.md).

:::::{grid} 1 2 2 2
:gutter: 3

::::{grid-item-card} 💻 Using the CLI
For everyday use in the terminal, with no coding required.

- {doc}`Quickstart <cli/getting-started>`: authenticate a service and manage your first playlists.
- {doc}`All commands <cli/commands>`: browse, search, match, and sync playlists.
- {doc}`Settings & configuration <cli/configuration>`: credentials, config file, and logging.
::::

::::{grid-item-card} 🐍 Using the Library
For developers and advanced users who want to build scripts and tooling.

- {doc}`Python quickstart <library/getting-started>`: install the package and write your first script.
- {doc}`Examples <library/examples/readme>`: ready-to-run notebooks and scripts.
- {doc}`API reference <reference/api/index>`: in-depth reference for every module and class.
::::
:::::
