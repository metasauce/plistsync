"""Tests for service-first CLI commands and lazy service loading."""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar
from unittest.mock import patch

import pytest
from typer._click._compat import strip_ansi
from typer.main import get_group

from plistsync.cli.service_commands.auth import CLIInteraction, RawRedirectHandler
from plistsync.config import Config, ServiceConfig
from plistsync.core.auth import AuthProvider
from plistsync.errors import AuthenticationError, HowTheForkDidYouEndUpHereError
from plistsync.services import Service, ServiceLoader
from plistsync.utils.auth.bearer_token import Token

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

    import typer
    from typer.testing import CliRunner


class FakeToken(Token):
    """Minimal persistable token for CLI tests."""

    def __init__(self, file_path: Path | None = None) -> None:
        super().__init__(file_path)

    def as_dict(self) -> dict:
        return {"token": "secret"}

    @classmethod
    def from_dict(cls, token_dict: dict) -> FakeToken:
        return cls()

    def __call__(self, request):
        return request


@dataclass
class FakeConfig(ServiceConfig, service="fake"):
    """Config for the fake service.

    ``service="fake"`` registers it without relying on the module path. The
    module override below makes the service name -- and therefore the token
    path -- resolve to ``fake``. The field keeps the generated default config
    valid, since an empty service section is parsed as ``None``.
    """

    redirect_port: int = 5001


# ``__module__`` must be set after the class body: ``@dataclass`` resolves
# string annotations via ``sys.modules[cls.__module__]``, and no
# ``plistsync.services.fake`` module exists.
FakeConfig.__module__ = "plistsync.services.fake"


class FakeAuthProvider(AuthProvider[None, None, FakeToken]):
    """Auth provider returning a token the CLI can persist."""

    __module__ = "plistsync.services.fake"

    instances: ClassVar[list[FakeAuthProvider]] = []

    def __init__(self, config: ServiceConfig) -> None:
        super().__init__(config)
        FakeAuthProvider.instances.append(self)

    def build_request(self) -> None:
        return None

    def collect_response(self, interaction, request) -> None:
        return None

    def obtain_token(self, request, response) -> FakeToken:
        # The command persists the token at the service config's token path.
        return FakeToken()


class FakeService(Service):
    """Service exposing a config and an auth provider."""

    __module__ = "plistsync.services.fake"

    def config(self) -> type[FakeConfig]:
        return FakeConfig

    def auth(self) -> type[FakeAuthProvider]:
        return FakeAuthProvider


@contextmanager
def _fake_service() -> Iterator[None]:
    """Patch service discovery so the CLI resolves the fake service."""
    with (
        patch.object(ServiceLoader, "list_all", return_value=["fake"]),
        patch.object(ServiceLoader, "get", return_value=FakeService()),
    ):
        yield


@pytest.fixture
def fake_token_file() -> Iterator[Path]:
    """Path the fake service token is written to."""
    path = Config.get_dir() / "fake_token.json"
    yield path
    path.unlink(missing_ok=True)


class TestLazyServiceLoading:
    """Services are mounted as top level groups and loaded on demand."""

    def test_root_help_lists_services_without_loading_them(
        self, runner: CliRunner, cli_app: typer.Typer
    ) -> None:
        with patch.object(ServiceLoader, "get") as mock_get:
            result = runner.invoke(cli_app, ["--help"])

        assert result.exit_code == 0
        assert "config" in result.output
        assert "sync" in result.output
        assert any(name in result.output for name in ("plex", "spotify", "tidal"))
        mock_get.assert_not_called()

    def test_service_help_loads_only_that_service(
        self, runner: CliRunner, cli_app: typer.Typer, config: Config
    ) -> None:
        plex = ServiceLoader.get("plex")
        assert plex is not None

        with (
            patch.object(ServiceLoader, "get", return_value=plex) as mock_get,
            patch.object(ServiceLoader, "all") as mock_all,
        ):
            result = runner.invoke(cli_app, ["plex", "--help"])

        assert result.exit_code == 0, result.output
        mock_get.assert_any_call("plex")
        mock_all.assert_not_called()
        assert "auth" in result.output

    def test_unknown_command_does_not_load_services(
        self, runner: CliRunner, cli_app: typer.Typer
    ) -> None:
        with (
            patch.object(ServiceLoader, "list_all", return_value=["plex"]),
            patch.object(ServiceLoader, "get") as mock_get,
            patch.object(ServiceLoader, "all") as mock_all,
        ):
            result = runner.invoke(cli_app, ["nope", "--help"])

        assert result.exit_code != 0
        mock_get.assert_not_called()
        mock_all.assert_not_called()


class TestAuthCommand:
    """``plistsync <service> auth`` drives the provider and persists a token."""

    def test_runs_provider_and_saves_token(
        self, runner: CliRunner, cli_app: typer.Typer, fake_token_file: Path
    ) -> None:
        with (
            _fake_service(),
            patch(
                "plistsync.cli.service_commands.auth.CLIInteraction"
            ) as mock_interaction,
        ):
            result = runner.invoke(cli_app, ["fake", "auth"])

        assert result.exit_code == 0, result.output
        mock_interaction.assert_called_once_with(mode="forward")
        assert json.loads(fake_token_file.read_text()) == {"token": "secret"}
        assert str(fake_token_file) in result.output

    def test_mode_option_is_forwarded_to_interaction(
        self, runner: CliRunner, cli_app: typer.Typer
    ) -> None:
        with (
            _fake_service(),
            patch(
                "plistsync.cli.service_commands.auth.CLIInteraction"
            ) as mock_interaction,
        ):
            result = runner.invoke(cli_app, ["fake", "auth", "--mode", "manual"])

        assert result.exit_code == 0, result.output
        mock_interaction.assert_called_once_with(mode="manual")

    def test_help_lists_mode_option(
        self, runner: CliRunner, cli_app: typer.Typer
    ) -> None:
        with _fake_service():
            result = runner.invoke(cli_app, ["fake", "auth", "--help"])

        assert result.exit_code == 0, result.output
        assert "--mode" in strip_ansi(result.output)


class TestCliServiceFactory:
    """cli_service_factory mounts only the commands a service supports."""

    def test_supported_commands_are_mounted(
        self, service_app: Callable[[Service], typer.Typer]
    ) -> None:
        group = get_group(service_app(FakeService()))

        assert group.help == "Commands for the fake service."
        assert set(group.commands) == {"auth"}
        command = group.commands["auth"]
        assert command.name == "auth"
        assert command.help == "Authenticate with fake."

    def test_provider_is_constructed_with_resolved_config(
        self, runner: CliRunner, cli_app: typer.Typer, fake_token_file: Path
    ) -> None:
        FakeAuthProvider.instances.clear()

        with _fake_service():
            result = runner.invoke(cli_app, ["fake", "auth"])

        assert result.exit_code == 0, result.output
        assert len(FakeAuthProvider.instances) == 1
        assert isinstance(FakeAuthProvider.instances[0].config, FakeConfig)

    def test_unsupported_commands_are_skipped(
        self, service_app: Callable[[Service], typer.Typer]
    ) -> None:
        class NoAuthService(Service):
            __module__ = "plistsync.services.fake_no_auth"

            def auth(self):
                return None

        group = get_group(service_app(NoAuthService()))

        assert group.commands == {}

    def test_auth_without_config_raises(
        self,
        runner: CliRunner,
        service_app: Callable[[Service], typer.Typer],
    ) -> None:
        class NoConfigService(Service):
            __module__ = "plistsync.services.fake_no_config"

            def auth(self):
                return FakeAuthProvider

            def config(self):
                return None

        result = runner.invoke(service_app(NoConfigService()), ["auth"])

        assert result.exit_code != 0
        assert isinstance(result.exception, HowTheForkDidYouEndUpHereError)


class TestCLIInteraction:
    """CLI interaction primitives for the auth flows."""

    def test_open_url_opens_browser(self, monkeypatch: pytest.MonkeyPatch) -> None:
        opened: list[str] = []
        monkeypatch.setattr(
            "plistsync.cli.service_commands.auth.safe_webbrowser_open",
            opened.append,
        )

        CLIInteraction().open_url("https://example.com/auth")

        assert opened == ["https://example.com/auth"]

    def test_open_url_prints_url_when_browser_fails(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        def failing_open(url: str) -> None:
            raise RuntimeError("no browser")

        monkeypatch.setattr(
            "plistsync.cli.service_commands.auth.safe_webbrowser_open", failing_open
        )

        CLIInteraction().open_url("https://example.com/auth")

        output = capsys.readouterr().out
        assert "https://example.com/auth" in output
        assert "manually" in output

    def test_show_echoes_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        CLIInteraction().show("waiting for you")

        assert "waiting for you" in capsys.readouterr().out

    def test_ask_prompts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("typer.prompt", lambda message: f"answer: {message}")

        assert CLIInteraction().ask("value?") == "answer: value?"

    def test_manual_capture_returns_pasted_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "http://x/?code=1")
        interaction = CLIInteraction(mode="manual")

        assert (
            interaction.capture_redirect("http://127.0.0.1:5001/") == "http://x/?code=1"
        )

    def test_manual_capture_empty_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: "")
        interaction = CLIInteraction(mode="manual")

        assert interaction.capture_redirect("http://127.0.0.1:5001/") is None

    def test_raw_redirect_handler_returns_url_verbatim(self) -> None:
        assert RawRedirectHandler.parse_redirect_parameters("/?code=1&state=2") == {
            "url": "/?code=1&state=2"
        }

    def test_forward_capture_starts_redirect_server(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: dict[str, object] = {}

        def fake_server(port, handler_class, state):
            calls["port"] = port
            calls["handler"] = handler_class
            state.update(handler_class.parse_redirect_parameters("/?code=1&state=2"))
            return state

        monkeypatch.setattr(
            "plistsync.cli.service_commands.auth.start_redirect_server", fake_server
        )
        interaction = CLIInteraction(mode="forward")

        assert interaction.capture_redirect("http://127.0.0.1:5001/") == (
            "/?code=1&state=2"
        )
        assert calls == {"port": 5001, "handler": RawRedirectHandler}

    def test_forward_capture_requires_port(self) -> None:
        interaction = CLIInteraction(mode="forward")

        with pytest.raises(AuthenticationError, match="without a port"):
            interaction.capture_redirect("http://127.0.0.1/")
