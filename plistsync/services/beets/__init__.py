from plistsync.errors import check_imports
from plistsync.services import Service

check_imports(
    service="beets",
    required_packages=["sqlalchemy"],
)

from .collection import BeetsCollection
from .config import BeetsConfig
from .database import BeetsDatabase
from .track import BeetsTrack


class BeetsService(Service):
    pass


__all__ = [
    "BeetsCollection",
    "BeetsConfig",
    "BeetsDatabase",
    "BeetsService",
    "BeetsTrack",
]
