"""Utilities shared by service command factories."""

from __future__ import annotations

from inspect import Parameter, Signature
from typing import Annotated, Any

import typer


class CLIParameters:
    """Build the parameters for typer CLI commands on the fly."""

    def __init__(self) -> None:
        self.parameters: list[Parameter] = []

    def add_option(
        self,
        name: str,
        help: str,
        *,
        annotation: Any = str | None,
        default: object = None,
        param_decls: tuple[str, ...] = (),
        **kwargs: Any,
    ) -> None:
        """Add a keyword-only Typer option parameter."""
        self.parameters.append(
            Parameter(
                name,
                Parameter.KEYWORD_ONLY,
                annotation=Annotated[
                    annotation,
                    typer.Option(*param_decls, help=help, **kwargs),
                ],
                default=default,
            )
        )

    def add_argument(
        self,
        name: str,
        help: str,
        *,
        annotation: Any = str | None,
        default: object = None,
        **kwargs: Any,
    ) -> None:
        """Add a positional-or-keyword Typer argument parameter."""
        self.parameters.append(
            Parameter(
                name,
                Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Annotated[
                    annotation,
                    typer.Argument(help=help, **kwargs),
                ],
                default=default,
            )
        )

    def signature(self):
        return Signature(self.parameters)
