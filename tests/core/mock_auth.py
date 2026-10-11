"""In-memory fakes for auth provider tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class FakeInteraction:
    """In-memory implementation of the auth interaction protocol.

    Parameters
    ----------
    redirect:
        Value returned by :meth:`capture_redirect`: a fixed callback URL,
        ``None``, or a callable receiving this interaction and the redirect
        URI (e.g. to echo the ``state`` from the URL a provider opened).
    """

    def __init__(
        self,
        redirect: str | None | Callable[[FakeInteraction, str], str | None] = None,
    ) -> None:
        self.redirect = redirect
        self.opened_urls: list[str] = []
        self.captured_uris: list[str] = []
        self.messages: list[str] = []

    def open_url(self, url: str) -> None:
        self.opened_urls.append(url)

    def show(self, message: str) -> None:
        self.messages.append(message)

    def ask(self, message: str) -> str:
        return ""

    def capture_redirect(self, redirect_uri: str) -> str | None:
        self.captured_uris.append(redirect_uri)
        if callable(self.redirect):
            return self.redirect(self, redirect_uri)
        return self.redirect
