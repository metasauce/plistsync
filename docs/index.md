---
hide-toc: true
---

# plistsync

```{include} ../README.md
:start-after: <!-- start intro -->
:end-before: <!-- end intro -->
```

## Features

```{include} ../README.md
:start-after: <!-- start features -->
:end-before: <!-- end features -->
```

## Where to go next

:::::{grid} 1 2 3 3
:gutter: 2

::::{grid-item-card} Getting started
:link: getting-started
:link-type: doc

Install `plistsync` and manage your first playlists from the command line, no coding required.
::::

::::{grid-item-card} CLI guide
:link: details/cli
:link-type: doc

Everything the command line can do, from browsing playlists to syncing them.
::::

::::{grid-item-card} Core concepts
:link: details/core-concepts
:link-type: doc

The key abstractions behind `plistsync`, for building your own tooling.
::::

::::{grid-item-card} Examples
:link: examples/readme
:link-type: doc

Step-by-step guides for common workflows.
::::

::::{grid-item-card} API reference
:link: api/index
:link-type: doc

In-depth reference material for the library.
::::
:::::

```{note}
We are always happy for contributions, whether small or big. Feel free to check out our [contribution guide](contribution.md), improvements to both code and documentation are welcome!
```

```{toctree}
:hidden:

getting-started.md
```

```{toctree}
:hidden:
:caption: 💻 CLI

details/cli.md
details/configuration.md
```

```{toctree}
:maxdepth: 1
:hidden:
:caption: 🐍 Library

details/core-concepts.md
details/architecture.md
details/advanced/index.md
examples/readme.md
```

```{toctree}
:maxdepth: 1
:hidden:
:caption: 🛠️ Services

services/sync/index
services/local/index
services/tidal/index
services/spotify/index
services/plex/index
services/traktor/index
```

```{toctree}
:hidden:
:caption: 📖 Reference

changelog.md
contribution.md
api/index.md
```
