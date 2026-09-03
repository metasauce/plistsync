# Logging

`plistsync` provides a {py:func}`plistsync.logger.init_logging` function that configures logging for the plistsync logger based on a {py:class}`plistsync.config.LoggingConfig`. The CLI calls this function automatically; for scripts and library usage you should call it yourself.

You can retrieve the logger as usual:

```python
import logging

log = logging.getLogger("plistsync")
```

## Overview

```yaml
# ./config/config.yaml
logging:
  level: "INFO" # DEBUG, INFO, WARNING, ERROR, CRITICAL, NOTSET
  handler: "rich" # "rich" or "basic"
```

- `logging.level` controls how verbose the plistsync logger is.
- `logging.handler` selects the output style: `"rich"` for colorized console output (requires the `rich` library), or `"basic"` for plain standard-library formatting.

## Configuring logging from a script

Call {py:func}`plistsync.logger.init_logging` with a {py:class}`~plistsync.config.LoggingConfig` to set up the plistsync logger:

```python
from plistsync.config import LoggingConfig
from plistsync.logger import init_logging

# Use defaults (level="INFO", handler="rich")
init_logging()

# Or provide explicit settings
init_logging(LoggingConfig(level="DEBUG", handler="basic"))
```

The `log_level_offset` parameter shifts the configured level by multiples of 10 for fine-grained control (the CLI uses this for its `-v` verbosity flags):

```python
# Reduce the configured level by one step (e.g. INFO → DEBUG)
init_logging(LoggingConfig(level="INFO"), log_level_offset=1)
```

## Configure logging yourself

### Attach a handler only to the plistsync logger

```python
import logging
from plistsync.logger import log

handler = logging.FileHandler("plistsync.log")
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

log.addHandler(handler)
log.propagate = False  # avoid double logging via root handlers
```

### Configure root logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)
```
