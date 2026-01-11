from plistsync.errors import check_imports

check_imports(
    service="beets",
    required_packages=["sqlalchemy"],
)

from .collection import BeetsCollection
from .database import BeetsDatabase
from .track import BeetsTrack

__all__ = ["BeetsCollection", "BeetsDatabase", "BeetsTrack"]
