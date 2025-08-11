import dataclasses
import json
import os
import pathlib
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Iterable, TypeVar


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)  # type: ignore
        return super().default(o)


def build_url(base_url: str, params: dict) -> str:
    """Construct a URL with a base hostname and a dictionary of parameters.

    Parameters
    ----------
    base_url (str): The base URL to which the parameters will be appended.
    params (dict): A dictionary of parameters to append to the URL.

    Returns
    -------
    str: The constructed URL.
    """
    if not params:
        return base_url

    url = base_url
    i = 0
    for key, value in params.items():
        # Encode the values for URLs
        if i == 0:
            url += f"?{key}={urllib.parse.quote(value)}"
            i += 1
        else:
            url += f"&{key}={urllib.parse.quote(value)}"
    return url


def get_config_dir() -> pathlib.Path:
    """Get the configuration directory.

    Returns
    -------
    str: The configuration directory.
    """
    o = os.getenv("PSYNC_CONFIG_DIR", "./config")
    os.makedirs(o, exist_ok=True)
    return pathlib.Path(o).resolve()


def camel_to_snake(text: str) -> str:
    """Convert camelCase to snake_case."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", text)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
    return re.sub("_+", "_", s2)


A = TypeVar("A")


def chunk_list(lst: list[A], chunk_size: int):
    """
    Chunk a list into smaller lists of the specified size.

    Parameters
    ----------
    lst: A
        List to be chunked
    chunk_size: int
        Maximum size of each chunk

    """
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        else:
            # If the class has already been instantiated, reinitialize it
            # This reloads the config file
            cls._instances[cls].__init__(*args, **kwargs)
        return cls._instances[cls]
