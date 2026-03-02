# Logging

By default, `plistsync` can configure logging automatically based on your config file. If your application already sets up logging (handlers/formatters/filters), you can disable `plistsync`’s logging setup and manage logging yourself.

## Overview

```yaml
# ./config/config.yaml
logging:
  enabled: true
  level: "INFO" # DEBUG, INFO, WARNING, ERROR, CRITICAL, NOTSET
  handler: "rich" # "rich" or "basic"
```

If `logging.enabled` is set to `false`, plistsync will not perform any automatic logging setup and you’re expected to configure logging in your application. The `logging.level` setting controls how verbose plistsync’s logs are, and `logging.handler` selects the output style: use `"rich"` for a more readable, colorized console experience, or `"basic"` for plain standard output formatting.

## Disable plistsync logging setup (recommended if your app configures logging)

```yaml
logging:
  enabled: false
```

You can also override `enabled` via environment variable:

- `PLSYNC_LOGGING=true|1|t` enables
- `PLSYNC_LOGGING=false|0|...` disables

## Configure logging yourself

### Configure root logging (after importing plistsync)

```python
import logging
import plistsync  # calls init_logging(), but it does nothing if enabled=false

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)
```

### Attach a handler only to the plistsync logger

```python
import logging
from plistsync.logger import log

handler = logging.FileHandler("plistsync.log")
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

log.addHandler(handler)
log.propagate = False  # avoid double logging via root handlers (if configured)
```
