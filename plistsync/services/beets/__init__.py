from plistsync.errors import check_imports
from plistsync.services import Service

check_imports(
    service="beets",
    required_packages=["sqlalchemy"],
)

from .collection import BeetsCollection
from .database import BeetsDatabase
from .track import BeetsTrack


class BeetsService(Service):
    track_cls = BeetsTrack


__all__ = [
    "BeetsCollection",
    "BeetsDatabase",
    "BeetsService",
    "BeetsTrack",
]
