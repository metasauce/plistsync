"""Render the shared plistsync installation instructions as a tab-set.

Adds the ``plistsync-install`` directive, which renders the supported
installation methods (uv tool, pipx, uv add, pip) for an optional extra:

```md
{plistsync-install} spotify
```

Passing no argument renders the core install without extras.
"""

from __future__ import annotations

from typing import Any, ClassVar, NamedTuple

from docutils import nodes  # type: ignore[import-untyped]
from docutils.statemachine import StringList  # type: ignore[import-untyped]
from sphinx.util.docutils import SphinxDirective


class _Method(NamedTuple):
    label: str
    sync: str
    description: str
    command: str


_METHODS: tuple[_Method, ...] = (
    _Method(
        label="uv tool",
        sync="uv-tool",
        description=(
            "Installs the `plistsync` CLI in an isolated environment, managed by uv."
        ),
        command='uv tool install "{spec}"',
    ),
    _Method(
        label="pipx",
        sync="pipx",
        description=(
            "Installs the `plistsync` CLI in an isolated environment, managed by pipx."
        ),
        command='pipx install "{spec}"',
    ),
    _Method(
        label="uv add",
        sync="uv-add",
        description=(
            "Adds `plistsync` to your project's dependencies, so scripts can import it "
            "and run the CLI with `uv run`."
        ),
        command="uv add plistsync{extra_arg}",
    ),
    _Method(
        label="pip",
        sync="pip",
        description=(
            "Installs `plistsync` into the currently active Python environment."
        ),
        command='pip install "{spec}"',
    ),
)


def install_tabs(extra: str | None = None) -> list[str]:
    """Render the installation tab-set as MyST lines."""
    spec = f"plistsync[{extra}]" if extra else "plistsync"
    extra_arg = f" --extra {extra}" if extra else ""

    lines = ["::::{tab-set}", ":sync-group: install-method", ""]
    for method in _METHODS:
        command = method.command.format(spec=spec, extra_arg=extra_arg)
        lines += [
            f":::{{tab-item}} {method.label}",
            f":sync: {method.sync}",
            "",
            method.description,
            "",
            "```bash",
            command,
            "```",
            "",
            ":::",
            "",
        ]
    lines.append("::::")
    return lines


class PlistsyncInstallDirective(SphinxDirective):
    """Render the shared installation tab-set."""

    required_arguments: ClassVar[int] = 0
    optional_arguments: ClassVar[int] = 1
    has_content: ClassVar[bool] = False

    def run(self) -> list[nodes.Node]:
        extra = self.arguments[0] if self.arguments else None

        container = nodes.container()
        self.state.nested_parse(
            StringList(install_tabs(extra)), self.content_offset, container
        )
        return container.children


def setup(app: Any) -> dict[str, Any]:
    app.add_directive("plistsync-install", PlistsyncInstallDirective)

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
