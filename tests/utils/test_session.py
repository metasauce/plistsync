import threading
from importlib.metadata import version
from unittest.mock import MagicMock, patch

import pytest
import requests
from requests import Response

from plistsync.utils.session import RateLimitAdapter, PlistsyncSession


def _prepared_request(
    url: str = "https://example.com",
    method: str = "GET",
) -> requests.PreparedRequest:
    req = requests.Request(method, url)
    return req.prepare()


class TestRateLimitAdapter:
    """Tests for RateLimitAdapter."""

    @pytest.fixture
    def adapter(self) -> RateLimitAdapter:
        return RateLimitAdapter(rate_limit=0.25)

    @pytest.fixture
    def mock_sleep(self, monkeypatch):
        """Mock time.sleep and capture calls."""
        sleep_mock = MagicMock()
        monkeypatch.setattr("plistsync.utils.session.time.sleep", sleep_mock)
        return sleep_mock

    @pytest.mark.parametrize(
        "rate_limit, expected_calls_after_two_sends",
        [
            (0.25, 1),  # First no sleep, second sleeps
            (0.0, 0),  # No sleeps
        ],
    )
    def test_rate_limiting(
        self,
        adapter,
        mock_sleep,
        rate_limit,
        expected_calls_after_two_sends,
    ):
        """Fixed: Assert total sleeps after exactly two sends."""
        adapter.rate_limit = rate_limit
        adapter.send(_prepared_request())
        adapter.send(_prepared_request())
        assert mock_sleep.call_count == expected_calls_after_two_sends

    def test_custom_wait_time(self, adapter, mock_sleep, monkeypatch):
        """Fixed: Force elapsed=0 so custom wait always triggers once per send."""
        adapter._wait_time = lambda elapsed: 0.5
        monkeypatch.setattr(
            "plistsync.utils.session.time.monotonic", lambda: 0.0
        )  # elapsed always 0

        adapter.send(_prepared_request())
        adapter.send(_prepared_request())
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([((0.5,),), ((0.5,),)], any_order=False)

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE", "PATCH"])
    def test_different_methods(self, adapter, mock_sleep, method):
        """Parameterized: works with all HTTP methods."""
        request = _prepared_request(method=method)
        adapter.send(_prepared_request())  # First: no sleep
        adapter.send(request)
        mock_sleep.assert_called_once()

    def test_thread_safety(self, adapter, mock_sleep):
        """Thread-safe: concurrent requests respect rate limit."""

        def make_request():
            adapter.send(_prepared_request())

        threads = [threading.Thread(target=make_request) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # Multiple sleeps expected due to concurrency; no exceptions = success
        assert mock_sleep.call_count >= 9

    def test_retries_configured(self, adapter):
        """Retries configured for 502/503/etc."""
        assert adapter.max_retries.total >= 5


class TestPlistsyncSession:
    """Tests for PlistsyncSession."""

    def test_default_user_agent(self):
        """Sets expected User-Agent."""
        session = PlistsyncSession()
        expected = f"plistsync/{version('plistsync')} https://docs.plistsync.com/"
        assert session.headers["User-Agent"] == expected

    def test_custom_rate_limit(self):
        """Uses custom rate limit."""
        session = PlistsyncSession(rate_limit=1.0)
        adapter = session.get_adapter("https://example.com")
        assert adapter.rate_limit == 1.0  # type: ignore

    @pytest.mark.parametrize("timeout", [None, 30])
    def test_timeout_handling(self, monkeypatch, timeout):
        """Parameterized: default/custom timeout preserved."""
        session = PlistsyncSession()
        mock_response = MagicMock(spec=Response)
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            requests.Session, "request", return_value=mock_response
        ) as mock_request:
            kwargs = {"timeout": timeout} if timeout else {}
            session.request("GET", "https://api.example.com", **kwargs)

        call_kwargs = mock_request.call_args.kwargs
        assert call_kwargs["timeout"] == (timeout or 10)

    def test_adapters_mounted(self):
        """Mounts RateLimitAdapter for http/https."""
        session = PlistsyncSession()
        assert isinstance(session.get_adapter("https://example.com"), RateLimitAdapter)
        assert isinstance(session.get_adapter("http://example.com"), RateLimitAdapter)
