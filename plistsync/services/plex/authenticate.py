import json
import time
from typing import Any, Literal
from urllib.parse import urlencode

import requests
import typer

from plistsync.config import Config
from plistsync.errors import AuthenticationError
from plistsync.logger import log
from plistsync.utils.auth.redirect import BaseRedirectHandler


def auth(
    mode: Literal["forward", "polling"] = typer.Option(
        "forward",
        "--mode",
        "-m",
        help="If set to 'polling', the CLI will not start a local server and instead"
        " ask you to paste the redirected URL after login. This should be used if you"
        " are running the CLI on a remote server without browser access.",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        "-p",
        help="Port for the local server (if 'forward' mode is used).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force re-authentication even if a valid token exists.",
    ),
):
    """Authenticate with Plex to obtain an access token.

    This will open a browser window to log in to Plex and obtain an access token.
    """
    from plistsync.utils.auth import (
        safe_webbrowser_open,
    )
    from plistsync.utils.auth.redirect import (
        start_redirect_server,
    )

    config = Config()
    plex_config = config.plex
    redirect_port = port if port is not None else config.redirect_port

    # Check if token exists and is valid
    token_path = Config.get_dir() / "plex_token.json"
    if token_path.exists() and not force:
        with open(token_path) as f:
            token = json.load(f)

        response = requests.get(
            "https://plex.tv/api/v2/user",
            headers={
                "X-Plex-Product": plex_config.app_name,
                "X-Plex-Client-Identifier": plex_config.client_identifier,
                "X-Plex-Token": token["X-Plex-Token"],
            },
        )
        if response.status_code == 200:
            log.info("Plex is already authenticated. Use --force to re-authenticate.")
            return
        else:
            log.debug("Existing Plex token is invalid, re-authenticating.")

    # Generate a pin
    response = requests.post(
        "https://plex.tv/api/v2/pins?strong=true",
        headers={
            "accept": "application/json",
            "X-Plex-Product": config.plex.app_name,
            "X-Plex-Client-Identifier": config.plex.client_identifier,
        },
        json={"strong": True},
    )
    response.raise_for_status()
    pin = pin_data = response.json()

    # Create an url for the user to authenticate
    params = {
        "clientID": config.plex.client_identifier,
        "code": pin["code"],
        "context[device][product]": config.plex.app_name,
    }
    if mode == "forward":
        params["forwardUrl"] = f"http://localhost:{redirect_port}/"
    auth_url = "https://app.plex.tv/auth#?" + urlencode(params)

    # Try to open the URL in the default browser
    log.debug(f"Redirecting to Plex login: {auth_url}")
    try:
        safe_webbrowser_open(auth_url)
    except Exception:
        typer.echo(
            "Failed to open the url in the default browser automatically. "
            "Please open the URL manually."
        )
        typer.echo(auth_url)

    try:
        if mode == "forward":
            start_redirect_server(redirect_port, PlexRedirectHandler, {})
            success, pin_data = verify_pin(pin["id"])
        else:
            # Check for the pin manually every 2 seconds
            timeout = 300  # 5 minutes
            start_time = time.time()
            success = False

            while time.time() - start_time < timeout and not success:
                time.sleep(2)
                success, pin_data = verify_pin(pin["id"])

            if not success:
                raise AuthenticationError("Failed to authenticate with Plex.")
    except AuthenticationError as e:
        typer.echo(f"Authentication failed: {str(e)}")
        return typer.Exit(code=1)

    # Save the token
    token_path = Config.get_dir() / "plex_token.json"
    with open(token_path, "w") as f:
        json.dump(
            {"X-Plex-Token": pin_data["authToken"]},
            f,
        )
    typer.echo(f"Authentication successful! Plex token saved to {token_path}.")


# ----------------------------- Redirect Handler ----------------------------- #
# Start a local server to handle the redirect after auth


class PlexRedirectHandler(BaseRedirectHandler):
    """Handles the redirect from Tidal after login."""

    def __init__(self, *args, state: dict[str, str | None], **kwargs):
        super().__init__(*args, state=state, **kwargs)

    @staticmethod
    def parse_redirect_parameters(url: str) -> dict[str, str | None]:
        return {"url": url}


# -------------------------------- Pin verify -------------------------------- #
# Plex does not use a redirect handler but requires polling the pin endpoint


def verify_pin(pin_id: int) -> tuple[bool, Any]:
    """Verify the PIN code with Plex."""
    response = requests.get(
        f"https://plex.tv/api/v2/pins/{pin_id}",
        headers={
            "accept": "application/json",
            "X-Plex-Client-Identifier": Config().plex.client_identifier,
            "X-Plex-Product": Config().plex.app_name,
        },
    )
    if response.status_code != 200:
        return False, {}
    data = response.json()
    if not data.get("authToken"):
        return False, {}

    return True, data
