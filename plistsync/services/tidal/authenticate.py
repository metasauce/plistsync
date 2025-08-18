"""Registers an authentication command for Tidal.

This is used to obtain the initial authentication token for Tidal.
"""

import base64
import hashlib
import http.server
import secrets
import socketserver
from urllib.parse import parse_qs, urlparse

import requests
import typer

from plistsync.config import Config
from plistsync.logger import log
from plistsync.utils import build_url

from .token import TidalBearerToken

tidal_cli = typer.Typer(
    rich_markup_mode="rich", help="Interact with Tidal.", add_completion=False
)


SCOPES = "playlists.read"


@tidal_cli.command()
def auth(
    no_server: bool = typer.Option(
        False,
        "--no-server",
        "-ns",
        help="Do not run a server. You will need to manually paste the URL.",
    ),
):
    """Use your Tidal account to authenticate with the Tidal API.

    This will open a browser window to log in to Tidal and obtain an access token.
    """
    tidal_config = Config().tidal
    code_verifier, code_challenge = _generate_pkce_codes()
    state = secrets.token_urlsafe(8)

    url = build_url(
        "https://login.tidal.com/authorize",
        {
            "response_type": "code",
            "client_id": tidal_config.client_id,
            "redirect_uri": f"http://localhost:{tidal_config.redirect_port}",
            "scope": SCOPES,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "state": state,
        },
    )

    # Start a local server to handle the redirect after login

    log.debug(f"Redirecting to Tidal login: {url}")
    # Try to open the URL in the default browser
    try:
        import webbrowser

        webbrowser.open(url)
    except Exception:
        typer.echo(
            "Failed to open the url in the default browser automatically. Please open the URL manually."
        )
        typer.echo(url)

    # Start a local server to handle the redirect
    if no_server:
        pasted_url = typer.prompt("Paste the redirected URL after logging into Tidal")
        results = handle_pasted_url(pasted_url)
    else:
        results = get_auth_code_server(tidal_config.redirect_port)

    # Send request to get tidal token
    token_url = "https://auth.tidal.com/v1/oauth2/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": tidal_config.client_id,
        "code": results.get("code"),
        "redirect_uri": f"http://localhost:{tidal_config.redirect_port}",
        "code_verifier": code_verifier,
    }
    response = requests.post(token_url, data=data)
    response.raise_for_status()
    token_data = response.json()

    # Create TidalBearerToken instance and save it
    token = TidalBearerToken.from_dict(token_data)
    f_path = Config.get_dir() / "tidal_token.json"
    token.save(f_path)
    typer.echo(f"Authentication successful! Tidal token saved to {f_path}.")


def _generate_pkce_codes():
    code_verifier = secrets.token_urlsafe(32)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return code_verifier, code_challenge


# ----------------------------- Redirect handler ----------------------------- #
# Starts a simple HTTP server to handle the redirect from Tidal/user after login.


class RedirectHandler(http.server.BaseHTTPRequestHandler):
    """Handles the redirect from Tidal after login."""

    results: dict[str, str | None]

    def __init__(self, *args, results: dict[str, str | None], **kwargs):
        self.results = results
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        query_components = parse_qs(urlparse(self.path).query)

        code = query_components.get("code", [None])[0]
        state = query_components.get("state", [None])[0]
        error = query_components.get("error", [None])[0]
        error_description = query_components.get("error_description", [None])[0]

        self.results["code"] = code
        self.results["state"] = state
        self.results["error"] = error
        self.results["error_description"] = error_description

        # Error for testing
        if error:
            # log.error(f"Tidal authentication error: {error} - {error_description}")
            # Stop the server after handling the error
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"Error: {error} - {error_description}".encode("utf-8"))
            return

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h1>Authentication Successful</h1>"
            b"<p>You can close this window.</p></body></html>"
        )

    def log_message(self, format, *args):
        """Override to disable logging."""
        pass


def get_auth_code_server(port):
    """Start the local HTTP server to listen for redirect."""
    results: dict[str, str | None] = {}
    httpd = None

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    try:
        handler = lambda *args, **kwargs: RedirectHandler(
            *args, results=results, **kwargs
        )
        with ReusableTCPServer(("", port), handler) as httpd:
            httpd.handle_request()  # Handle a single request; adjust as needed
    finally:
        if httpd:
            httpd.server_close()
    if results.get("error"):
        typer.echo(
            f"Authentication failed: {results['error']} - {results['error_description']}"
        )
        typer.Exit(code=1)

    return results


def handle_pasted_url(url):
    """Handle the URL provided by the user by extracting the code from the URL."""
    parsed_url = urlparse(url)
    query_components = parse_qs(parsed_url.query)
    return {
        "code": query_components.get("code", [None])[0],
        "state": query_components.get("state", [None])[0],
        "error": query_components.get("error", [None])[0],
        "error_description": query_components.get("error_description", [None])[0],
    }
