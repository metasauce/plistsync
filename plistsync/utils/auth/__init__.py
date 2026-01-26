"""Utilities and common functions for auth needs."""

import base64
import hashlib
import secrets


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
