import json
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Self,
)

import requests
from requests_oauth2client import BearerToken

from ...config.yaml import Config
from ...errors import ConfigurationError
from ...logger import log


class TidalBearerToken:
    __custom: Dict[str, Any]
    token: BearerToken

    def __init__(
        self,
        access_token,
        expires_at,
        refresh_token,
        scope,
        token_type="Bearer",
        **kwargs,
    ):
        self.token = BearerToken(
            access_token=access_token,
            expires_at=expires_at,
            refresh_token=refresh_token,
            scope=scope,
            token_type=token_type,
            **kwargs,
        )
        self.__custom = {
            "access_token": access_token,
            "expires_at": expires_at,
            "refresh_token": refresh_token,
            "scope": scope,
            "token_type": token_type,
            **kwargs,
        }

    @classmethod
    def from_dict(cls, token_dict):
        token_dict = cls._parse(token_dict)
        return cls(**token_dict)

    @classmethod
    def _parse(cls, token_dict):
        # Convert `expires_in` (comes from tidal) to `expires_at` (needed in bearer class)
        if "expires_in" in token_dict:
            expires_in = token_dict.pop("expires_in")
            token_dict["expires_at"] = datetime.now(tz=timezone.utc).replace(
                microsecond=0
            ) + timedelta(seconds=expires_in)

        # Convert `expires_at` to datetime
        if "expires_at" in token_dict and isinstance(token_dict["expires_at"], str):
            token_dict["expires_at"] = datetime.fromisoformat(token_dict["expires_at"])

        return token_dict

    def to_dict(self):
        # for saving on disk, we need serializable fields, and datetime objects
        res = {k: v for k, v in self.__custom.items() if k != "expires_at"}
        res["expires_at"] = self.__custom["expires_at"].isoformat()
        return res

    def __repr__(self):
        res = "TidalBearerToken("
        res += ", ".join([f"{k}={v}" for k, v in self.__custom.items()])
        return res + ")"

    def __str__(self):
        return f"{self.token_type} {self.access_token}"

    @classmethod
    def load(cls, file_path: str | Path) -> Self | None:
        if not os.path.exists(file_path):
            return None
        with open(file_path, "r") as f:
            token_dict = json.load(f)
        return cls.from_dict(token_dict)

    def save(self, file_path: str | Path):
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f)

    def __getattr__(self, name):
        return getattr(self.token, name)

    def __call__(self, *args, **kwargs):
        return self.token(*args, **kwargs)

    @property
    def is_expired(self):
        return self.expires_at < datetime.now(tz=timezone.utc)


class InvalidToken(Exception):
    def __init__(self, token: TidalBearerToken | None):
        if token:
            self.message = f"Invalid token: {token}"
        else:
            self.message = "Token not found. Is it created?"
        super().__init__(self.message)


def requires_tidal_token(func: Callable[..., Any]) -> Callable[..., Any]:
    """Add tidal token to function.

    This decorator will load the token from the file if it exists. If the token does not
    exist it will throw an error. If the token is expired, it will refresh the token.

    Raises
    ------
    ConfigurationError
        If the Tidal config is not available.
    InvalidToken
        If the token is not found or invalid.

    Usage
    -----

    ```python
    @requires_tidal_token
    async def needs_tidal_token(token: BearerToken):
        return token
    ```

    Attention
    ---------
    This decorator will not work for generator functions. If you need to use the
    `requires_tidal_token_generator` decorator.

    Note: If you want to use this decorator in a route make sure to catch the
    errors and redirect to the login route.

    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        token = await __get_token()
        # Pass the token as a keyword argument
        return await func(*args, token=token, **kwargs)

    return wrapper


def requires_tidal_token_generator(
    func: Callable[..., AsyncGenerator],
) -> Callable[..., AsyncGenerator]:
    """Add tidal token to generator function.

    This decorator will load the token from the file if it exists. If the token does not
    exist it will throw an error. If the token is expired, it will refresh the token.

    Raises
    ------
    ConfigurationError
        If the Tidal config is not available.
    InvalidToken
        If the token is not found or invalid.

    Usage
    -----

    ```python
    @requires_tidal_token_generator
    async def needs_tidal_token(token: BearerToken):
        return token
    ```

    Attention
    ---------
    This decorator is for generator functions. If you need to use the
    `requires_tidal_token` decorator.

    Note: If you want to use this decorator in a route make sure to catch the
    errors and redirect to the login route.
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        token = await __get_token()
        # Pass the token as a keyword argument
        async for res in func(*args, token=token, **kwargs):
            yield res

    return wrapper


async def __get_token():
    """Get the Tidal token.

    Raises
    ------
    ConfigurationError
        If the Tidal config is not available.
    InvalidToken
        If the token is not found or invalid.

    """

    # Check if the config is available
    config = Config()
    tidal_config = config.tidal
    if not tidal_config or not tidal_config.enabled:
        raise ConfigurationError(
            "Tidal config not available or tidal integration disabled!", "tidal"
        )

    # Redirect to login if token does not exist
    token_file = os.path.join(config.get_dir(), "tidal_token.json")
    token = TidalBearerToken.load(token_file)
    if token is None:
        raise InvalidToken(token)

    # Convert `expires_at` to datetime
    if token.is_expired:
        # Token expired
        request_url = "https://auth.tidal.com/v1/oauth2/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": token.to_dict()["refresh_token"],
            "client_id": tidal_config.client_id,
        }
        res = requests.post(request_url, data=data)
        if res.status_code == 200:
            token = TidalBearerToken.from_dict(
                {
                    **data,
                    **res.json(),
                }
            )
            token.save(token_file)
        else:
            log.error(f"Failed to refresh token: {res.text}, {res.status_code}")
            raise InvalidToken(token)

    return token
