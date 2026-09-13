from __future__ import annotations

import base64
import hashlib
import inspect
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Generic, Protocol, TypeVar
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from plistsync.errors import AuthenticationError
from plistsync.services.registry import Registry
from plistsync.utils.auth.bearer_token import Oauth2Token, Token
from plistsync.utils.session import PlistsyncSession

if TYPE_CHECKING:
    from plistsync.config import ServiceConfig


class Interaction(Protocol):
    """Primitive user-facing operations, implemented by the caller.

    The provider decides which primitives its flow needs; the interaction
    holds no request, response, service or mode knowledge.
    """

    def open_url(self, url: str) -> None:
        """Open (or print) a URL for the user."""
        ...

    def show(self, message: str) -> None:
        """Display instructions (e.g. a device code)."""
        ...

    def ask(self, message: str) -> str:
        """Ask the user for a value (pasted URL, API key, ...)."""
        ...

    def capture_redirect(self, redirect_uri: str) -> str | None:
        """Wait for the browser callback at ``redirect_uri``; return it raw."""
        ...


Req = TypeVar("Req")
Res = TypeVar("Res")
T = TypeVar("T", bound=Token)


class AuthProvider(ABC, Registry, Generic[Req, Res, T]):
    """Initial authentication flow for a service.

    Used to obtain a token for the first time by a user.
    """

    config: ServiceConfig
    """Service configuration this provider is bound to."""

    def __init_subclass__(cls, **kwargs) -> None:
        super().__init_subclass__(**kwargs)
        # Registry makes every abstract subclass a new root. Keep shared
        # abstract providers (e.g. OAuth2Provider) under the AuthProvider root,
        # so concrete services still register against AuthProvider.
        if inspect.isabstract(cls) or ABC in cls.__bases__:
            cls._registry = AuthProvider

    def __init__(self, config: ServiceConfig) -> None:
        self.config = config

    def authenticate(
        self,
        interaction: Interaction,
    ) -> T:
        """Run the flow: build the request, collect the response, obtain the token."""
        request = self.build_request()
        response = self.collect_response(interaction, request)
        return self.obtain_token(request, response)

    @abstractmethod
    def build_request(self) -> Req:
        """Prepare what the user has to act on. No user-facing I/O."""

    @abstractmethod
    def collect_response(self, interaction: Interaction, request: Req) -> Res:
        """Drive the interaction and collect what it returned."""

    @abstractmethod
    def obtain_token(self, request: Req, response: Res) -> T:
        """Interpret the response, obtain a token and return it."""

