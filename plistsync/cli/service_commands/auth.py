"""Auth command factory and its terminal interaction.

Services with an auth provider expose ``plistsync <service> auth``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal
from urllib.parse import urlparse

import typer

from plistsync.errors import AuthenticationError
from plistsync.logger import log
from plistsync.utils.auth import safe_webbrowser_open
from plistsync.utils.auth.redirect import BaseRedirectHandler, start_redirect_server

if TYPE_CHECKING:
    from collections.abc import Callable

    from plistsync.core.auth import AuthProvider, Token


class RawRedirectHandler(BaseRedirectHandler[dict[str, str]]):
    """Capture the raw redirect URL without interpreting its parameters."""

    @staticmethod
    def parse_redirect_parameters(url: str) -> dict[str, str]:
        return {"url": url}


class CLIInteraction:
    """User-facing auth primitives backed by the terminal and a browser.

    Parameters
    ----------
    mode:
        ``"forward"`` starts a local server for the browser callback,
        ``"manual"`` asks the user to paste the redirected URL instead. The
        latter is useful when the CLI runs on a remote machine without
        browser access.
    """

    def __init__(self, mode: Literal["forward", "manual"] = "forward") -> None:
        self.mode = mode

    def open_url(self, url: str) -> None:
        """Open the URL in the default browser, printing it as a fallback."""
        log.debug("Opening authentication URL: %s", url)
        try:
            safe_webbrowser_open(url)
        except Exception:
            typer.echo(
                "Failed to open the url in the default browser automatically. "
                "Please open the URL manually:"
            )
            typer.echo(url)

    def show(self, message: str) -> None:
        """Display a message to the user."""
        typer.echo(message)

    def ask(self, message: str) -> str:
        """Ask the user for a value."""
        return typer.prompt(message)

    def capture_redirect(self, redirect_uri: str) -> str | None:
        """Return the raw browser callback, or ``None`` if unavailable.

        In manual mode the user is asked to paste the redirected URL. An empty
        answer returns ``None`` so providers can fall back to polling.
        """
        if self.mode == "manual":
            pasted = self.ask(
                "Paste the redirected URL after logging in "
                "(leave empty if the provider polls for completion)"
            )
            return pasted or None

        port = urlparse(redirect_uri).port
        if port is None:
            raise AuthenticationError(
                f"Cannot capture redirect without a port: {redirect_uri!r}"
            )
        state: dict[str, str] = {}
        start_redirect_server(port, RawRedirectHandler, state)
        return state.get("url")


def auth_command_factory(auth_provider: AuthProvider) -> Callable[..., None]:
    """Create the auth command for a configured auth provider."""
    service_name = auth_provider.service()

    def auth(
        mode: Annotated[
            Literal["forward", "manual"],
            typer.Option(
                "--mode",
                "-m",
                help="If set to 'manual', the CLI will not start a local server and"
                " instead ask you to paste the redirected URL after login. This"
                " should be used if you are running the CLI on a remote server"
                " without browser access.",
            ),
        ] = "forward",
    ) -> None:
        """Authenticate and persist a token."""
        token: Token = auth_provider.authenticate(CLIInteraction(mode=mode))
        token.save()
        typer.echo(f"Authentication successful! Token saved to {token.file_path!r}.")

    auth.__doc__ = f"Authenticate with {service_name}."
    return auth
