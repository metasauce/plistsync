# We do not import from the different submodules as they
# might raise with check_dependencies.

import importlib
import pkgutil
from functools import cache

from plistsync.errors import DependencyError


@cache
def available_services() -> list[pkgutil.ModuleInfo]:
    """Get the available services.

    Skips modules where dependencies are missing.
    """
    valid_services = []
    for module_info in pkgutil.iter_modules(__path__, __name__ + "."):
        try:
            # Test import - catches missing deps (beets, plex, etc.)
            importlib.import_module(module_info.name)
            valid_services.append(module_info)
        except DependencyError:
            # Skip services with missing dependencies
            pass

    return valid_services
