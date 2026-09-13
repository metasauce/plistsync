from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urlencode

import requests

from plistsync.core.auth import AuthProvider
from plistsync.errors import AuthenticationError
from plistsync.utils.session import PlistsyncSession

from .api import PlexToken

if TYPE_CHECKING:
    from plistsync.core.auth import Interaction

    from .config import PlexConfig


@dataclass(kw_only=True, frozen=True)
class PlexAuthRequest:
    """Flow state for Plex pin-based authentication."""

    url: str
    """Authorization URL the user opens in the browser."""

    pin_id: int
    """ID of the created pin, polled for the auth token."""

    redirect_uri: str
    """Redirect URI the browser callback is captured on."""


class PlexAuth(AuthProvider[PlexAuthRequest, str | None, PlexToken]):
    """Authenticate with Plex by confirming a pin in the browser.

    Plex does not use OAuth2: we create a pin, send the user to plex.tv to
    confirm it, and poll the pin until it carries an auth token.
    """

    config: PlexConfig

    pins_endpoint: ClassVar[str] = "https://plex.tv/api/v2/pins"
    """Plex endpoint to create and poll pins on."""

    auth_endpoint: ClassVar[str] = "https://app.plex.tv/auth"
    """Plex web app endpoint the user confirms the pin on."""

    poll_interval: ClassVar[float] = 2.0
    """Seconds between pin polls while waiting for the user to confirm."""

    poll_timeout: ClassVar[float] = 300.0
    """Seconds to wait for the user to confirm the pin before giving up."""

    def redirect_uri(self) -> str:
        """Return the URI the browser is redirected to after confirming."""
        return f"http://127.0.0.1:{self.config.redirect_port}/"

    def build_request(self) -> PlexAuthRequest:
        """Create a pin and build the URL the user confirms it on."""
        try:
            response = PlistsyncSession().post(
                self.pins_endpoint,
                params={"strong": "true"},
                json={"strong": True},
                headers=self._headers(),
            )
        except requests.RequestException as e:
            raise AuthenticationError(f"Failed to create Plex pin: {e}") from e

        pin = response.json()
        params = {
            "clientID": self.config.client_identifier,
            "code": pin["code"],
            "context[device][product]": self.config.app_name,
            "forwardUrl": self.redirect_uri(),
        }
        return PlexAuthRequest(
            url=f"{self.auth_endpoint}#?{urlencode(params)}",
            pin_id=int(pin["id"]),
            redirect_uri=self.redirect_uri(),
        )

    def collect_response(
        self, interaction: Interaction, request: PlexAuthRequest
    ) -> str | None:
        """Open the login page and wait for the browser to come back.

        The Plex callback carries no code, it only tells us the user is done.
        Interactions without a local redirect server may return ``None``; the
        pin is then polled in :meth:`obtain_token`.
        """
        interaction.open_url(request.url)
        response = interaction.capture_redirect(request.redirect_uri)
        if response is None:
            interaction.show("Waiting for you to confirm the login in your browser.")
        return response

    def obtain_token(self, request: PlexAuthRequest, response: str | None) -> PlexToken:
        """Poll the pin until Plex attached an auth token to it."""
        deadline = time.monotonic() + self.poll_timeout
        while True:
            auth_token = self._fetch_auth_token(request.pin_id)
            if auth_token:
                return PlexToken(auth_token, None)
            if time.monotonic() >= deadline:
                raise AuthenticationError(
                    "Timed out waiting for Plex authentication. Please try again."
                )
            time.sleep(self.poll_interval)

    def _fetch_auth_token(self, pin_id: int) -> str | None:
        """Fetch the auth token stored on a pin, if the user confirmed it."""
        try:
            response = PlistsyncSession().get(
                f"{self.pins_endpoint}/{pin_id}",
                headers=self._headers(),
            )
        except requests.RequestException as e:
            raise AuthenticationError(f"Failed to poll Plex pin: {e}") from e
        return response.json().get("authToken")

    def _headers(self) -> dict[str, str]:
        """Return the headers identifying plistsync to plex.tv."""
        return {
            "accept": "application/json",
            "X-Plex-Product": self.config.app_name,
            "X-Plex-Client-Identifier": self.config.client_identifier,
        }
