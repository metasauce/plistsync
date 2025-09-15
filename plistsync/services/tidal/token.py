import os
from typing import Callable, TypeVar

import requests

from plistsync.config import Config
from plistsync.utils.bearer_token import (
    BearerToken,
    InvalidToken,
    requires_bearer_token,
)

R = TypeVar("R")


def requires_tidal_token(func: Callable[..., R]) -> Callable[..., R]:
    """Require Tidal token."""
    return requires_bearer_token("tidal")(func)


def refresh_tidal_token(token: BearerToken) -> None:
    """Refresh the Tidal token.

    This function will refresh the Tidal token using the refresh token.
    It will update the token in place.

    Raises
    ------
    InvalidToken
        If the token is not found or invalid.
    """
    tidal_config = Config().tidal

    request_url = "https://auth.tidal.com/v1/oauth2/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": tidal_config.client_id,
        "refresh_token": token.as_dict()["refresh_token"],
    }
    res = requests.post(request_url, data=data)
    try:
        res.raise_for_status()
    except requests.HTTPError as e:
        raise InvalidToken(token) from e

    token_data = res.json()
    token.update(token_data)
    token.save(os.path.join(Config.get_dir(), "tidal_token.json"))
    return
