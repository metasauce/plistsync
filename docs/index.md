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
:link: cli/commands
:link-type: doc

Everything the command line can do, from browsing playlists to syncing them.
::::

::::{grid-item-card} Core concepts
:link: library/core-concepts
:link-type: doc

The key abstractions behind `plistsync`, for building your own tooling.
::::

::::{grid-item-card} Examples
:link: library/examples/readme
:link-type: doc

Step-by-step guides for common workflows.
::::

::::{grid-item-card} API reference
:link: reference/api/index
:link-type: doc

In-depth reference material for the library.
::::
:::::

```{note}
We are always happy for contributions, whether small or big. Feel free to check out our [contribution guide](reference/contribution.md), improvements to both code and documentation are welcome!
```

```{toctree}
:hidden:

getting-started.md
```

```{toctree}
:hidden:
:caption: 💻 CLI

cli/commands.md
cli/configuration.md
```

```{toctree}
:maxdepth: 1
:hidden:
:caption: 🐍 Library

library/core-concepts.md
library/architecture.md
library/advanced/index.md
library/examples/readme.md
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

reference/changelog.md
reference/contribution.md
reference/api/index.md
```
