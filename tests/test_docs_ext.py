from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Annotated

from eyconf.generate_yaml import dataclass_to_yaml

from docs._ext.plistsync_config import (
    _without_dataio_fields,
    dataclass_to_file,
    dataclass_to_python,
)
from docs._ext.plistsync_install import install_tabs
from plistsync.core.config import DataIO  # noqa: TC001


@dataclass
class _Inner:
    value: int = 1


@dataclass
class _Simple:
    name: str = "example"
    count: int = 3


@dataclass
class _Outer:
    name: str = "example"
    inner: _Inner = field(default_factory=_Inner)


@dataclass
class _WithDataIO:
    name: Annotated[str, "The display name."] = "example"
    token: DataIO[_Inner] | _Inner | None = None


def test_dataclass_to_python_puts_each_option_on_its_own_line() -> None:
    body = dataclass_to_python(_Simple).split("\n\n", 1)[1]

    assert body == "config = _Simple(\n    name='example',\n    count=3,\n)"


def test_dataclass_to_python_indents_nested_dataclasses() -> None:
    body = dataclass_to_python(_Outer).split("\n\n", 1)[1]

    assert body == (
        "config = _Outer(\n"
        "    name='example',\n"
        "    inner=_Inner(\n"
        "        value=1,\n"
        "    ),\n"
        ")"
    )


def test_dataclass_to_python_renders_dataio_with_jsonfileio() -> None:
    code = dataclass_to_python(_WithDataIO)

    assert "from pathlib import Path" in code
    assert "from plistsync.core.config import JsonFileIO" in code
    assert "token=JsonFileIO[_Inner](Path('withdataio_token.json'))" in code
    assert "#" not in code


def test_dataclass_to_file_loads_from_user_config() -> None:
    code = dataclass_to_file(_Simple)

    assert code == (
        "from plistsync.cli.config import UserDirConfigIO\n"
        f"from {_Simple.__module__} import _Simple\n\n"
        "config = UserDirConfigIO().load(_Simple)"
    )


def test_without_dataio_fields_removes_dataio_fields() -> None:
    filtered = _without_dataio_fields(_WithDataIO)

    assert [f.name for f in fields(filtered)] == ["name"]


def test_yaml_skips_dataio_fields_and_keeps_comments() -> None:
    code = dataclass_to_yaml(_without_dataio_fields(_WithDataIO))

    assert "# The display name." in code
    assert "token" not in code


def test_install_tabs_renders_methods_for_extra() -> None:
    code = "\n".join(install_tabs("spotify"))

    assert "::::{tab-set}" in code
    assert ":sync-group: install-method" in code
    for label in ("uv tool", "pipx", "uv add", "pip"):
        assert f":::{{tab-item}} {label}" in code
    assert 'uv tool install "plistsync[spotify]"' in code
    assert "uv add plistsync --extra spotify" in code
    assert 'pip install "plistsync[spotify]"' in code


def test_install_tabs_without_extra_installs_core() -> None:
    code = "\n".join(install_tabs())

    assert 'uv tool install "plistsync"' in code
    assert "uv add plistsync" in code
    assert "--extra" not in code
