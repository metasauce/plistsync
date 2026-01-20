"""Utilities and common functions for auth needs."""

import base64
import hashlib
import http.server
import secrets
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from urllib.parse import parse_qs, urlparse

T = TypeVar("T", bound=dict)


class BaseRedirectHandler(http.server.BaseHTTPRequestHandler, ABC, Generic[T]):
    state: T

    def __init__(self, *args, state: T, **kwargs):
        self.state = state
        super().__init__(*args, **kwargs)

    @staticmethod
    @abstractmethod
    def parse_redirect_parameters(url: str) -> T:
        """Parse redirect URL parameters. Must be implemented by subclasses.

        This should raise if an error occurs!
        """
        pass

    def do_GET(self):
        try:
            self.state.update(self.parse_redirect_parameters(self.path))
            self.send_success_response()
        except Exception as e:
            self.send_error_response(e)

    def send_success_response(self):
        """Send success HTML response."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(self.get_success_html())

    def send_error_response(self, exception: Exception):
        """Send error HTML response."""
        self.send_response(400)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(self.get_error_html(exception))

    @staticmethod
    def get_success_html() -> bytes:
        """Get HTML to display after successful authentication."""
        return (
            b"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Authentication Successful</title>
            """
            + BaseRedirectHandler.styling()
            + b"""</head>
            <body>
            <div class="card">
            <h1>Authentication Successful!</h1>
            <p style="font-size: 1rem; margin-bottom: 1rem;">
            Thank you for using <strong>plistsync</strong>! You can safely close
            this window.
            </p>
            <p style="font-size: 0.9rem; color: #555;">
            Check out our project on
            <a href="https://github.com/metasauce/plistsync" target="_blank"
            style="color: #2c7be5; text-decoration: none;">GitHub</a>.
            </p>
            </div>
            </body>
            </html>
            """
        )

    @staticmethod
    def get_error_html(error: Exception) -> bytes:
        """Get HTML to display after authentication error."""
        return (
            b"""
            <!DOCTYPE html>
            <html>
            <head>
            <title>Authentication Error</title>
            """
            + BaseRedirectHandler.styling()
            + b"""</head>
            <body>
            <div class="card">"""
            + f"""<div class="card">
            <h1>Authentication Error</h1>
            <p><strong>{str(error)}</strong></p>
            <p>Something went wrong!</p>
            </div>
            </body>
            </html>""".encode()
        )

    def log_message(self, format, *args):
        """Override to disable logging."""
        pass

    @staticmethod
    def styling():
        return b"""<style>
    body {
        font-family: 'Inter', sans-serif;
        background: black;
        color: #f1f5f9;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 100vh;
        margin: 0;
        text-align: center;
    }
    .card {
        padding: 2rem;
        box-shadow: 0 8px 20px rgba(0,0,0,0.3);
    }
    </style>"""


class AuthenticationError(Exception):
    pass


class OAuthRedirectHandler(BaseRedirectHandler):
    """Handles the redirect from Tidal after login."""

    state: dict[str, str | None]

    def __init__(self, *args, state: dict[str, str | None], **kwargs):
        super().__init__(*args, state=state, **kwargs)

    @staticmethod
    def parse_redirect_parameters(url: str) -> dict[str, str | None]:
        query_components = parse_qs(urlparse(url).query)
        code = query_components.get("code", [None])[0]
        state = query_components.get("state", [None])[0]
        error = query_components.get("error", [None])[0]
        error_description = query_components.get("error_description", [None])[0]

        if error:
            raise AuthenticationError(error_description or error)

        if not code or not state:
            raise AuthenticationError(
                "Missing authorization code or state parameter in the redirect URL. "
            )

        return {
            "code": code,
            "state": state,
        }


def start_redirect_server(
    port: int,
    handler_class: type[BaseRedirectHandler[T]],
    state: T,
) -> T:
    """
    Start a local HTTP server to listen for OAuth2 redirects.

    Paramters
    ---------
    port: Port to listen on
    handler_class: HTTP handler class (default: OAuth2RedirectHandler)
    state: Sstate dict to store redirect results, depdent on implementation.
    """
    import socketserver

    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    httpd = None
    try:
        with ReusableTCPServer(
            ("", port),
            lambda *args, **kwargs: handler_class(*args, state=state, **kwargs),
        ) as httpd:
            httpd.handle_request()  # Handle exactly one request

    except OSError as e:
        if "Address already in use" in str(e):
            raise AuthenticationError(
                f"Port {port} is already in use. Try a different port with --port"
            )
        else:
            raise AuthenticationError(f"Failed to start server on port {port}: {e}")
    except Exception as e:
        raise AuthenticationError(f"Unexpected server error: {e}")
    finally:
        if httpd:
            httpd.server_close()

    return state


def generate_pkce_codes():
    """Generate PKCE code verifier and code challenge.

    Used for OAuth2 authentication with PKCE (S256).
    """

    code_verifier = secrets.token_urlsafe(32)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return code_verifier, code_challenge


def safe_webbrowser_open(url: str) -> bool:
    """Open URL in the default browser, silencing browser stderr/stdout."""
    import subprocess
    import webbrowser

    controller = webbrowser.get()  # default browser controller

    # If it's a BackgroundBrowser, override Popen behavior
    if isinstance(controller, webbrowser.BackgroundBrowser):

        def quiet_open(url, new=0, autoraise=True):
            try:
                subprocess.Popen(
                    [controller.name, url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                )
                return True
            except Exception:
                return False

        return quiet_open(url)

    # Fallback: just use normal open()
    return controller.open(url)
