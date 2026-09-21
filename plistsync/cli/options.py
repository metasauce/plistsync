"""Shared Typer options and signature helpers for CLI commands."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Annotated, Any, TypeAlias, TypeVar

import typer

NameOption: TypeAlias = Annotated[
    str | None,
    typer.Option("--name", "-n", help="Name of the playlist."),
]
DescriptionOption: TypeAlias = Annotated[
    str | None,
    typer.Option("--description", "-d", help="Description of the playlist."),
]
AddTrackOption: TypeAlias = Annotated[
    list[str] | None,
    typer.Option(
        "--add",
        "-a",
        help="Track to add: id/uri/url. Can be specified multiple times.",
    ),
]
YesOption: TypeAlias = Annotated[
    bool,
    typer.Option("--yes", "-y", help="Skip the confirmation prompt."),
]

F = TypeVar("F", bound=Callable[..., Any])


def without_param(fn: F, name: str) -> F:
    """Remove a parameter from a command's CLI signature.

    Typer derives CLI options from the function signature, so removing a
    parameter here hides it from ``--help``, completion and parsing without
    duplicating the command body. The Python function itself is unchanged.

    Used to gate capability-dependent options, e.g. ``--add`` requires
    :class:`~plistsync.core.collection.IDLookup`.
    """
    signature = inspect.signature(fn, eval_str=True)
    fn.__signature__ = signature.replace(  # type: ignore[attr-defined]
        parameters=[
            parameter
            for parameter in signature.parameters.values()
            if parameter.name != name
        ]
    )
    return fn
