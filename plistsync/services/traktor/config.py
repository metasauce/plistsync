from dataclasses import dataclass, field
from typing import Annotated

from plistsync.config import ServiceConfig


@dataclass
class TraktorConfig(ServiceConfig):
    path: Annotated[
        str,
        "The absolute path to the nml file you want to use as your default"
        "traktor library.",
    ] = field(default="/replace/me/with/a/path/to/nml.nml")

    backup_before_write: Annotated[
        bool,
        "Create a backup of the libraries nml file before every write.",
    ] = field(default=True)
