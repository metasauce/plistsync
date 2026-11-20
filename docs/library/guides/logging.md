# Logging

For library usage, logging is configured in code. The CLI configures its own logging
from the configuration file, see the
[CLI configuration guide](../../cli/configuration.md).

`plistsync` provides {py:func}`init_logging <plistsync.logger.init_logging>` to
configure the `plistsync` logger from a
{py:class}`LoggingConfig <plistsync.logger.LoggingConfig>`. Call it from your script
to set up the logger:

```python
from plistsync.logger import LoggingConfig, init_logging

# Use defaults (level="INFO", handler="rich")
init_logging()

# Or provide explicit settings
init_logging(LoggingConfig(level="DEBUG", handler="basic"))
```

You can retrieve the logger as usual:

```python
import logging

log = logging.getLogger("plistsync")
```

## Attach a handler to the plistsync logger

Add a handler directly to the `plistsync` logger to keep it separate from the root
logger:

```python
import logging

from plistsync.logger import log

handler = logging.FileHandler("plistsync.log")
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

log.addHandler(handler)
log.propagate = False  # avoid double logging via root handlers
```

## Configure root logging

Alternatively, configure the root logger and let `plistsync` records propagate to it:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)
```
