"""``playlist create`` command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.markup import escape
from rich.prompt import Prompt

from plistsync.cli.context import (
    ServiceCommandContext,  # noqa: TC001 (typer resolves it at runtime)
)
from plistsync.cli.options import (
    AddTrackOption,  # noqa: TC001 (typer resolves it at runtime)
    DescriptionOption,  # noqa: TC001 (typer resolves it at runtime)
    NameOption,  # noqa: TC001 (typer resolves it at runtime)
    YesOption,  # noqa: TC001 (typer resolves it at runtime)
    without_param,
)
from plistsync.cli.parsing import parse_track_id
from plistsync.cli.visualization import confirm_or_abort, stdout_console, to_rich
from plistsync.core.collection import IDLookup
from plistsync.core.playlist import Snapshot
from plistsync.errors import HowTheForkDidYouEndUpHereError
from plistsync.logger import log

if TYPE_CHECKING:
    import typer

    from plistsync.core import Library, Track, TrackID


def _create_playlist(
    ctx: ServiceCommandContext,
    *,
    name: str | None,
    description: str | None,
    add: list[str] | None,
    yes: bool,
) -> None:
    """Create a playlist in the service library."""
    library = ctx.obj.library
    if library is None:
        raise HowTheForkDidYouEndUpHereError(
            f"Service {ctx.obj.name!r} provides no library, but the 'create' "
            "command was invoked."
        )

    console = stdout_console()

    # Prompt for missing name and description
    if name is None:
        name = Prompt.ask("Playlist name", console=console)
    if description is None:
        description = (
            Prompt.ask(
                "Description (optional)",
                default="",
                show_default=False,
                console=console,
            )
            or None
        )
    # TODO: Allow to prompt for tracks to add

    # Parse ids: string -> TrackID
    ids: list[TrackID] = []
    for track_id_str in add or []:
        if track_id := parse_track_id(track_id_str, ctx.obj.service):
            ids.append(track_id)
        else:
            log.warning(f"Could not parse track identifier {track_id_str!r}. Skipping.")

    # Parse tracks: TrackID -> Track
    tracks: list[Track] = []
    if add:
        if not isinstance(library, IDLookup):
            # Unreachable via the CLI: register_create_command removes --add
            # for libraries without IDLookup.
            raise HowTheForkDidYouEndUpHereError(
                f"{type(library)!r} does not support lookup by track identifier."
            )
        for track, track_id in zip(library.find_many_by_ids([[id] for id in ids]), ids):
            if track is not None:
                tracks.append(track)
            else:
                log.warning(
                    f"Could not find track {track_id.serial!r} in library. Skipping."
                )

    confirm_or_abort(
        console,
        to_rich(Snapshot(name=name, description=description, tracks=tracks)),
        yes=yes,
        default=True,
    )

    playlist = library.create_playlist(
        name=name,
        description=description,
        tracks=tracks or None,
    )

    console.print(
        f"Created playlist [bold]{escape(repr(playlist.name))}[/bold] "
        f"(id: [cyan]{playlist.id.serial}[/cyan]) "
        f"with {len(playlist)} track(s)."
    )


def register_create_command(app: typer.Typer, library_cls: type[Library]) -> None:
    """Register the ``create`` command on the playlist command group.

    The ``--add`` option is only offered if the library supports
    :class:`~plistsync.core.collection.IDLookup`.
    """

    def create(
        ctx: ServiceCommandContext,
        name: NameOption = None,
        description: DescriptionOption = None,
        add: AddTrackOption = None,
        yes: YesOption = False,
    ) -> None:
        """Create a playlist in the service library.

        Prompts for missing name and description, then asks for confirmation.
        """
        _create_playlist(ctx, name=name, description=description, add=add, yes=yes)

    if not issubclass(library_cls, IDLookup):
        without_param(create, "add")

    app.command(name="create")(create)
