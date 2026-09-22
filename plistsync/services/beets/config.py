from dataclasses import dataclass, field

from plistsync.core.config import ServiceConfig


@dataclass
class BeetsConfig(ServiceConfig):
    database: str = field(default="./config/beets/beets.db")
