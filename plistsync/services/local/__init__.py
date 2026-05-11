from plistsync.errors import check_imports
from plistsync.services import Service

check_imports(
    service="local",
    required_packages=["tinytag"],
)

from .collection import LocalCollection
from .track import LocalTrack


class LocalService(Service):
    track_cls = LocalTrack


__all__ = [
    "LocalCollection",
    "LocalService",
    "LocalTrack",
]
