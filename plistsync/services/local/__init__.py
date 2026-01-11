from plistsync.errors import check_imports

check_imports(
    service="local",
    required_packages=["tinytag"],
)

from .collection import LocalCollection
from .track import LocalTrack

__all__ = ["LocalCollection", "LocalTrack"]
