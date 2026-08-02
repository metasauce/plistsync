from dataclasses import dataclass, field

from plistsync.config import ServiceConfig


@dataclass
class BeetsConfig(ServiceConfig):
    database: str = field(default="./config/beets/beets.db")
