# Logging

`plistsync` configures logging automatically at import time via `plistsync.logger.init_logging()` (called at the bottom of `plistsync/logger.py`). This gives you useful output by default, but it also means logging configuration can happen before your application/script code runs.

## Overview

By default, `plistsync` automatically configures logging based on your configuration file.  
This includes choosing:

```yaml
# ./config/config.yaml
logging:
  level: "INFO" # DEBUG ...
  handler: "rich" # basic or none
```

This means that in most cases, you don’t need to write any logging setup code yourself, everything is handled when your application starts.

- `handler: "rich"`: Colorized console output using [rich](https://rich.readthedocs.io/en/stable/introduction.html) text.
- `handler: "basic"`: Standard `logging.StreamHandler` with a timestamped formatter.
- `handler: "none"`: Does not attach any handler.

## Customizing logging

Sometimes you’ll want more control, for example, if your application already sets up a global logging configuration and you dont want to use our setup.

You can do this by setting the handler to `"none"`.

```yaml
# ./config/config.yaml
logging:
  handler: "none"
```

With this setting:

- `plistsync` **does not touch** Python’s global logging configuration.
- You can configure and attach your own handlers, formatters, or log filters freely.
- The `plistsync` logger (`logging.getLogger("plistsync")`) will integrate seamlessly with your custom logging setup.

### Reconfigure root logging after importing plistsync

```python
import logging

# triggers plistsync's init_logging side effect which wont do anything
# if handler is set to none in the config
import plistsync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)
```

### Attach your own handler only to the plistsync logger

```python
import logging
from plistsync.logger import log, set_log_level

handler = logging.FileHandler("plistsync.log")
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

log.addHandler(handler)
log.propagate = False  # prevent double logging via root handlers (if any)
```

```{note}
If log messages happen **before**` init_logging()` ran at import time, you’ll not see those early logs or they will use the default/configured level unless you apply global verbosity **very early**. This shouldn't be an issue normally but might be relevant for debugging startup issues.
```
