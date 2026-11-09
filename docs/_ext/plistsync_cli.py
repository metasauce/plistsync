"""Generate the CLI command reference from the installed services.

The page is written to ``reference/api/cli.md`` before Sphinx reads its sources, so
the reference cannot drift from the Typer app, and adding a service needs no
documentation change.

Only services that install commands are listed: a service without a playlist
library (``local``, ``beets``) is a track source and has no CLI of its own.

Usage in ``conf.py``::

    extensions = [..., "plistsync_cli"]
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sphinx.util import logging

if TYPE_CHECKING:
    from sphinx.application import Sphinx

logger = logging.getLogger(__name__)

#: Preferred order in the reference; unknown services are appended alphabetically.
_ORDER = ("spotify", "tidal", "plex", "traktor", "sync")

_INTRO = """\
*Generated from the installed services. `plistsync <service> --help` prints the
same information in your terminal.*

Every service is set up once, as described on its
{doc}`service page <../../services/index>`.
"""

_SYNC = """\
## Sync

The sync workflow lives under `plistsync sync`. It needs no configuration or
login of its own. See {doc}`Sync <../../services/sync/index>` for the setup of the
services you link, and {doc}`the walkthrough <../../services/sync/cli>` for what each
command does.
"""

_FALLBACK = """\
# CLI Reference

*This page is generated at build time and needs `plistsync` with all service
extras installed.*
"""


def _typer(target: str, prog: str) -> str:
    """Render one Typer directive with all nested subcommands expanded."""
    return (
        f"```{{typer}} {target}\n---\nprog: {prog}\nwidth: 80\nshow-nested:\n---\n```\n"
    )


def _section(name: str, title: str) -> str:
    if name == "sync":
        return (
            _SYNC
            + "\n"
            + _typer("plistsync.cli.commands.sync:sync_app", "plistsync sync")
        )

    playlist = _typer(
        f"plistsync.cli.app:app::{name}:playlist",
        f"plistsync {name} playlist",
    )
    search = _typer(f"plistsync.cli.app:app::{name}:search", f"plistsync {name} search")
    return (
        f"## {title}\n\n"
        f"All {title} commands live under `plistsync {name}`. The one-time setup is\n"
        f"covered in {{doc}}`{title} setup <../../services/{name}/index>`.\n\n"
        f"{playlist}\n{search}"
    )


def _render() -> str:
    from plistsync.services import ServiceLoader

    available = list(ServiceLoader.list_all())
    ordered = [n for n in _ORDER if n in available]
    ordered += sorted(n for n in available if n not in _ORDER)

    sections = ["# CLI Reference", _INTRO.strip()]
    for name in ordered:
        service = ServiceLoader.get(name)
        if service is None:
            logger.warning("plistsync_cli: unknown service %r", name)
            continue
        try:
            library = service.library()
        except Exception as err:  # sphinx runs this for every build
            logger.warning("plistsync_cli: skipping service %r: %s", name, err)
            continue
        if name != "sync" and library is None:
            continue
        sections.append(_section(name, name.capitalize()))

    return "\n\n".join(sections) + "\n"


def generate(app: Sphinx) -> None:
    """Write the reference page, before Sphinx reads the sources."""
    target = Path(app.srcdir) / "reference" / "api" / "cli.md"
    try:
        content = _render()
    except Exception as err:  # docs must build without plistsync installed
        logger.warning("plistsync_cli: cannot generate the reference: %s", err)
        content = _FALLBACK

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    logger.info("plistsync_cli: wrote %s", target)


def setup(app: Sphinx) -> dict[str, object]:
    app.connect("builder-inited", generate)
    return {"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}
