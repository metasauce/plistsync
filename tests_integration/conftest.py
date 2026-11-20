"""Shared setup for the live integration tests."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from _pytest.reports import TestReport

# In CI we never want a silent skip to look like a green run. When strict, any
# skipped integration test is reported as a failure instead.
STRICT = any(
    os.getenv(name, "").strip().lower() in {"1", "true", "yes"}
    for name in ("PLISTSYNC_INTEGRATION_STRICT", "CI")
)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo
) -> Generator[None, TestReport, TestReport]:
    """Turn skips into failures when running in strict (CI) mode."""
    report = yield
    if STRICT and report.skipped:
        report.outcome = "failed"
        report.longrepr = (
            "Strict integration mode: skips are not allowed. "
            f"Original skip: {report.longrepr}"
        )
    return report
