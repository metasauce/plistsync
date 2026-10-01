```{eval-rst}
.. meta::
   :description: Configuration guide for plistsync library.
```

# Configuration

`plistsync` uses a YAML configuration file to manage service settings, logging, and other options. We use the [EYConf](https://eyconf.readthedocs.io/en/latest/) library for configuration management. This guide explains the configuration file location, structure, and how to manage it using the CLI.

## Config File Location

The configuration file is automatically located in the following order of precedence:

1. **Environment Variable**: If the `PSYNC_CONFIG_DIR` environment variable is set to a **non-empty, non-whitespace** path, the config file is expected at `$PSYNC_CONFIG_DIR/config.yml`.
2. **Global Directory**: Otherwise, the OS-specific user config directory is used (via `platformdirs`).

The global config directory and environment variable directory are automatically created if they don't exist.

## Logging

The CLI writes its logs to stderr, controlled by the `logging` section of the configuration file:

```{plistsync-config} plistsync.config.LoggingConfig
:section: logging
```

- `logging.level` controls how verbose the output is.
- `logging.handler` selects the output style: `rich` for colorized console output, or `basic` for plain formatting.

The `-v` flag makes the CLI more verbose on the spot. Every `-v` shifts the log level one step down (for example `INFO` to `DEBUG`), up to three times. For library usage, logging is configured in code instead, see the [logging guide](../library/advanced/logging.md).
