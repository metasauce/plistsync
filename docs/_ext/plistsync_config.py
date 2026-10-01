"""Render plistsync config classes as commented YAML or Python snippets.

Adds the ``plistsync-config`` directive, which generates configuration
snippets directly from a config dataclass, so the docs never drift from the
code.

- ``:type: cli`` (default) renders YAML for the configuration file,
- ``:type: library`` renders a Python constructor call for configuring in
  code.
"""

from __future__ import annotations

import importlib
from dataclasses import fields, is_dataclass
from typing import (
    Any,
    ClassVar,
)

from docutils import nodes
from docutils.parsers.rst import directives
from eyconf.generate_yaml import dataclass_to_yaml
from sphinx.util.docutils import SphinxDirective
from sphinx.util.logging import getLogger

logger = getLogger(__name__)


def _indent(text: str, spaces: int = 2) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else "" for line in text.splitlines())


def _load_class(path: str) -> type:
    module_name, separator, class_name = path.rpartition(".")
    if not separator:
        raise ValueError(f"expected a fully qualified class path: {path!r}")

    cls = getattr(importlib.import_module(module_name), class_name)
    if not isinstance(cls, type):
        raise TypeError(f"{path!r} is not a class")

    return cls


class PlistsyncConfigDirective(SphinxDirective):
    """Render an eyconf config class as YAML or Python."""

    required_arguments: ClassVar[int] = 1
    has_content: ClassVar[bool] = False
    option_spec: ClassVar[dict[str, Any]] = {
        "service": directives.unchanged_required,
        "section": directives.unchanged_required,
        "type": lambda value: directives.choice(value, ("cli", "library")),
    }

    def run(self) -> list[nodes.Node]:
        class_path = self.arguments[0]
        render_type = self.options.get("type", "cli")
        service = self.options.get("service")
        section = self.options.get("section")

        try:
            if service and section:
                raise ValueError(":service: and :section: are mutually exclusive")

            cls = _load_class(class_path)

            if render_type == "library":
                code = dataclass_to_python(cls)
                language = "python"
            else:
                code = dataclass_to_yaml(cls)
                language = "yaml"

                if service:
                    code = f"services:\n  {service}:\n{_indent(code, 4)}"
                elif section:
                    code = f"{section}:\n{_indent(code)}"

        except Exception as exc:
            logger.warning(
                "plistsync-config: failed to render %s: %s",
                class_path,
                exc,
                location=self.get_location(),
            )
            return []

        literal = nodes.literal_block(code, code)
        literal["language"] = language
        self.set_source_info(literal)
        return [literal]


def setup(app: Any) -> dict[str, Any]:
    app.add_directive("plistsync-config", PlistsyncConfigDirective)

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }


# ------------------------------ Render helper ------------------------------- #


def _value(value: Any) -> str:
    if is_dataclass(value) and not isinstance(value, type):
        return _call(value)

    if isinstance(value, list):
        return f"[{', '.join(map(_value, value))}]"

    if isinstance(value, tuple):
        values = ", ".join(map(_value, value))
        return f"({values}{',' if len(value) == 1 else ''})"

    if isinstance(value, dict):
        values = ", ".join(
            f"{_value(key)}: {_value(item)}" for key, item in value.items()
        )
        return f"{{{values}}}"

    return repr(value)


def _call(instance: Any) -> str:
    cls = type(instance)
    arguments = ", ".join(
        f"{field.name}={_value(getattr(instance, field.name))}"
        for field in fields(cls)
        if field.init
    )
    return f"{cls.__name__}({arguments})"


def dataclass_to_python(cls: type) -> str:
    """Render a dataclass as an import and constructor call."""
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")

    instance = cls()

    return f"from {cls.__module__} import {cls.__name__}\n\nconfig = {_call(instance)}"
