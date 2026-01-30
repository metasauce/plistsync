"""Registers an authentication command for Spotify.

This is used to obtain the initial authentication token for Spotify.
"""

import secrets
from typing import Literal

import requests
import typer

from plistsync.config import Config
from plistsync.errors import AuthenticationError
from plistsync.logger import log
from plistsync.utils import build_url
from plistsync.utils.auth.bearer_token import BearerToken

spotify_cli = typer.Typer(
    rich_markup_mode="rich", help="Interact with Spotify.", add_completion=False
)


SCOPES = " ".join(
    [
        "playlist-read-private",
        "playlist-read-collaborative",
        "playlist-modify-private",
        "playlist-modify-public",
    ]
)


@spotify_cli.command()
def auth(
    mode: Literal["forward", "manual"] = typer.Option(
        "forward",
        "--mode",
        "-m",
        help="If set to 'manual', the CLI will not start a local server and instead ask"
        " you to paste the redirected URL after login. This should be used if you"
        " are running the CLI on a remote server without browser access.",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        "-p",
        help="Port for the local server (if server is used).",
    ),
):
    """Use your Spotify account to authenticate with the Spotify API.

    This will open a browser window to log in to Spotify and obtain an access token.
    """
    from plistsync.utils.auth import (
        generate_pkce_codes,
        safe_webbrowser_open,
    )
    from plistsync.utils.auth.redirect import (
        OAuthRedirectHandler,
        start_redirect_server,
    )

    config = Config()
    spotify_config = config.spotify
    redirect_port = port if port is not None else config.redirect_port
    code_verifier, code_challenge = generate_pkce_codes()
    state = secrets.token_urlsafe(8)

    url = build_url(
        "https://accounts.spotify.com/authorize",
        {
            "response_type": "code",
            "client_id": spotify_config.client_id,
            "redirect_uri": f"http://127.0.0.1:{redirect_port}",
            "scope": SCOPES,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "state": state,
            "show_dialog": "true",
        },
    )

    log.debug(f"Redirecting to Spotify login: {url}")
    try:
        safe_webbrowser_open(url)
    except Exception:
        typer.echo(
            "Failed to open the url in the default browser automatically. "
            "Please open the URL manually."
        )
        typer.echo(url)

    # Start a local server to handle the redirect
    try:
        if mode == "manual":
            pasted_url = typer.prompt(
                "Paste the redirected URL after logging into Tidal"
            )
            results = OAuthRedirectHandler.parse_redirect_parameters(pasted_url)
        else:
            results = start_redirect_server(redirect_port, OAuthRedirectHandler, {})
    except AuthenticationError as e:
        typer.echo(f"Authentication failed: {str(e)}")
        return typer.Exit(code=1)

    # Send request to get spotify token
    token_url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": spotify_config.client_id,
        "code": results.get("code"),
        "redirect_uri": f"http://127.0.0.1:{redirect_port}",
        "code_verifier": code_verifier,
    }
    response = requests.post(
        token_url,
        data=data,
    )
    response.raise_for_status()
    token_data = response.json()

    # Create BearerToken instance and save it
    token = BearerToken.from_dict(token_data)
    f_path = Config.get_dir() / "spotify_token.json"
    token.save(f_path)
    typer.echo(f"Authentication successful! Spotify token saved to {f_path}.")
