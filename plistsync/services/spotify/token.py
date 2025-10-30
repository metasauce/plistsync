import os
from typing import Any, Callable

import requests

from plistsync.config import Config
from plistsync.logger import log
from plistsync.utils.bearer_token import (
    BearerToken,
    InvalidToken,
    requires_bearer_token,
)


def requires_spotify_token(func: Callable[..., Any]) -> Callable[..., Any]:
    """Require Spotify token."""
    return requires_bearer_token("spotify")(func)


def refresh_spotify_token(token: BearerToken) -> None:
    """Refresh the Spotify token.

    This function will refresh the Spotify token using the refresh token.
    It will update the token in place.

    Raises
    ------
    InvalidToken
        If the token is not found or invalid.
    """
    log.debug("Spotify token expired, refreshing...")
    spotify_config = Config().spotify

    request_url = "https://accounts.spotify.com/api/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": spotify_config.client_id,
        "refresh_token": token.as_dict()["refresh_token"],
    }
    res = requests.post(request_url, data=data)
    try:
        res.raise_for_status()
    except requests.HTTPError as e:
        raise InvalidToken(token) from e

    token_data = res.json()
    token.update(token_data)
    token.save(os.path.join(Config.get_dir(), "spotify_token.json"))
    return
