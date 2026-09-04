"""Auth command group."""

import importlib

import typer

from plistsync.errors import DependencyError
from plistsync.logger import log

auth_app = typer.Typer(
    name="auth",
    help="Authentication for services.",
    no_args_is_help=True,
)

# Map of module location → CLI command name. To allow partial dependencies
# we only register a service's auth command if the import is successful.
# TODO: This should go into the service abstraction and be automatic
_IMPORTS: dict[str, str] = {
    "plistsync.services.plex.authenticate:auth": "plex",
    "plistsync.services.spotify.authenticate:auth": "spotify",
    "plistsync.services.tidal.authenticate:auth": "tidal",
}

for module_str, name in _IMPORTS.items():
    module_name, func_name = module_str.split(":")
    try:
        module = importlib.import_module(module_name)
        auth_app.command(name=name)(getattr(module, func_name))
    except DependencyError:
        log.debug(f"Skipping '{module_name}.{func_name}' due to missing dependencies.")
