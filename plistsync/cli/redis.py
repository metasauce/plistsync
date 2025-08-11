import os
from typing import Optional

import typer

from ..logger import log

redis_cli = typer.Typer(
    rich_markup_mode="rich",
    help="Interact with redis.",
)


@redis_cli.command()
def start_workers(n: Optional[int] = None):
    """Launch redis workers.

    Launches redis workers via python, instead of cli. The advantage is
    that this way we can read the package config, (and, e.g. set the number of workers and logging there).
    """
    if n is None:
        n = int(os.environ.get("NUM_REDIS_WORKERS", 4))

    log.info(f"Starting {n} redis workers")
    for i in range(n):
        worker_name = "Package_worker" + str(i)
        os.system(
            f'rq worker QVA --log-format "Preview worker $i: %(message)s" > /dev/null &'
        )
    log.info(f"Started {n} redis workers")


if __name__ == "__main__":
    redis_cli()
