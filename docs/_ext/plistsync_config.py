"""Render plistsync config classes as commented YAML or Python snippets.

Adds the ``plistsync-config`` directive, which generates configuration
snippets directly from a config dataclass, so the docs never drift from the
code. Fields loaded through :class:`~plistsync.core.config.DataIO` are skipped
in the YAML and rendered as
:class:`~plistsync.core.config.JsonFileIO` in the Python snippet.

- ``:type: cli`` (default) renders YAML for the configuration file,
- ``:type: library`` renders a Python constructor call for configuring in
  code,
- ``:type: file`` renders Python code loading the config from the user
  config directory.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from dataclasses import MISSING, field, fields, is_dataclass, make_dataclass
from typing import Any, ClassVar, get_args, get_origin, get_type_hints

from docutils import nodes  # type: ignore[import-untyped]
from docutils.parsers.rst import directives  # type: ignore[import-untyped]
from eyconf.generate_yaml import dataclass_to_yaml
from sphinx.util.docutils import SphinxDirective
from sphinx.util.logging import getLogger

from plistsync.core.config import DataIO

logger = getLogger(__name__)


def _indent(text: str, spaces: int = 2) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" if line else "" for line in text.splitlines())


def _import_module_isolated(module_name: str) -> Any:
    """Import a module without executing its service package's ``__init__``.

    Config classes only depend on the core package, but importing
    ``plistsync.services.<service>.config`` normally runs the service package's
    ``__init__``, which imports optional runtime dependencies (for example
    ``lxml`` for traktor). Rendering docs must not require every service extra,
    so the package is temporarily replaced by a stub that only exposes its
    search path. Relative imports inside the config module still resolve.
    """
    package_name, separator, _ = module_name.rpartition(".")
    if not separator or package_name in sys.modules:
        return importlib.import_module(module_name)

    spec = importlib.util.find_spec(package_name)
    if spec is None or spec.submodule_search_locations is None:
        return importlib.import_module(module_name)

    stub = types.ModuleType(package_name)
    stub.__path__ = list(spec.submodule_search_locations)
    sys.modules[package_name] = stub
    try:
        return importlib.import_module(module_name)
    finally:
        if sys.modules.get(package_name) is stub:
            del sys.modules[package_name]


def _load_class(path: str) -> type:
    module_name, separator, class_name = path.rpartition(".")
    if not separator:
        raise ValueError(f"expected a fully qualified class path: {path!r}")

    cls = getattr(_import_module_isolated(module_name), class_name)
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
        "type": lambda value: directives.choice(value, ("cli", "library", "file")),
    }

    def run(self) -> list[nodes.Node]:
        class_path = self.arguments[0]

        try:
            if self.options.get("service") and self.options.get("section"):
                raise ValueError(":service: and :section: are mutually exclusive")

            code, language = _render(
                _load_class(class_path),
                self.options.get("type", "cli"),
                self.options.get("service"),
                self.options.get("section"),
            )
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


# ------------------------------ Render helpers ------------------------------ #


def _render(
    cls: type,
    kind: str,
    service: str | None = None,
    section: str | None = None,
) -> tuple[str, str]:
    """Render ``cls`` for the requested directive type and return the language."""
    if kind == "library":
        return dataclass_to_python(cls), "python"
    if kind == "file":
        return dataclass_to_file(cls), "python"

    code = dataclass_to_yaml(_without_dataio_fields(cls))
    if service:
        code = f"services:\n  {service}:\n{_indent(code, 4)}"
    elif section:
        code = f"{section}:\n{_indent(code)}"
    return code, "yaml"


def _import_block(*first_party: str, stdlib: tuple[str, ...] = ()) -> str:
    """Render sorted, deduplicated import groups separated by a blank line."""
    groups = ["\n".join(sorted(set(first_party)))]
    if stdlib:
        groups.insert(0, "\n".join(sorted(set(stdlib))))
    return "\n\n".join(group for group in groups if group)


def _dataio_model(annotation: Any) -> type | None:
    """Return the type wrapped in ``DataIO``, if the annotation contains one."""
    if get_origin(annotation) is DataIO:
        args = get_args(annotation)
        return args[0] if args else None

    for arg in get_args(annotation):
        if (model := _dataio_model(arg)) is not None:
            return model
    return None


def _dataio_fields(cls: type) -> dict[str, type]:
    """Map field names to the model wrapped in ``DataIO``, if any."""
    hints = get_type_hints(cls, include_extras=True)
    return {
        f.name: model
        for f in fields(cls)
        if (model := _dataio_model(hints.get(f.name))) is not None
    }


def _dataio_value(cls: type, field_name: str, model: type) -> str:
    """Render a ``DataIO`` field as a ``JsonFileIO`` for the library snippet."""
    module_parts = getattr(cls, "__module__", "").split(".")
    if module_parts[:2] == ["plistsync", "services"]:
        service = module_parts[2]
    else:
        service = cls.__name__.removesuffix("Config").strip("_").lower()

    file_name = f"{service}_{field_name}.json"
    return f"JsonFileIO[{model.__name__}](Path({file_name!r}))"


def _value(value: Any, indent: int = 0) -> str:
    """Render a field default, recursing into nested dataclasses."""
    if is_dataclass(value) and not isinstance(value, type):
        return _call(value, indent)
    return repr(value)


def _call(instance: Any, indent: int = 0) -> str:
    """Render a dataclass instance as a multiline constructor call."""
    cls = type(instance)
    dataio = _dataio_fields(cls)
    pad = " " * (indent + 4)

    args: list[str] = []
    for f in fields(cls):
        if not f.init:
            continue
        if f.name in dataio:
            value = _dataio_value(cls, f.name, dataio[f.name])
        else:
            value = _value(getattr(instance, f.name), indent + 4)
        args.append(f"{pad}{f.name}={value}")

    if not args:
        return f"{cls.__name__}()"
    separator = ",\n"
    return f"{cls.__name__}(\n{separator.join(args)},\n{' ' * indent})"


def _without_dataio_fields(cls: type) -> type:
    """Return a copy of ``cls`` without fields loaded through ``DataIO``."""
    dataio = _dataio_fields(cls)
    hints = get_type_hints(cls, include_extras=True)
    specs: list[Any] = []

    for f in fields(cls):
        if f.name in dataio:
            continue
        if f.default is not MISSING:
            spec = field(default=f.default)
        elif f.default_factory is not MISSING:
            spec = field(default_factory=f.default_factory)
        else:
            specs.append((f.name, hints[f.name]))
            continue
        specs.append((f.name, hints[f.name], spec))

    return make_dataclass(
        cls.__name__,
        specs,
        namespace={"__module__": cls.__module__, "__doc__": cls.__doc__},
    )


def dataclass_to_python(cls: type) -> str:
    """Render a dataclass as an import and constructor call.

    Fields typed as :class:`~plistsync.core.config.DataIO` are rendered with
    :class:`~plistsync.core.config.JsonFileIO`, pointing at the same
    ``<service>_<field>.json`` file the CLI uses.
    """
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")

    dataio = _dataio_fields(cls)
    stdlib: tuple[str, ...] = ()
    imports = [f"from {cls.__module__} import {cls.__name__}"]
    if dataio:
        stdlib = ("from pathlib import Path",)
        imports.append("from plistsync.core.config import JsonFileIO")
        imports.extend(
            f"from {model.__module__} import {model.__name__}"
            for model in dataio.values()
        )

    return f"{_import_block(*imports, stdlib=stdlib)}\n\nconfig = {_call(cls())}"


def dataclass_to_file(cls: type) -> str:
    """Render a dataclass as Python code loading it from the user config."""
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")

    imports = [
        "from plistsync.cli.config import UserDirConfigIO",
        f"from {cls.__module__} import {cls.__name__}",
    ]
    return (
        f"{_import_block(*imports)}\n\nconfig = UserDirConfigIO().load({cls.__name__})"
    )
