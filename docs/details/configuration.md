```{eval-rst}
.. meta::
   :description: Configuration guide for plistsync library.
```

# Configuration

`plistsync` uses a YAML configuration file to manage service settings, logging, and other options. We use the [EYConf](https://eyconf.readthedocs.io/en/latest/) library for configuration management. This guide explains the configuration file location, structure, and how to manage it using the CLI.

## Config File Location

The configuration file is automatically located in the following order of precedence:

1. **Environment Variable**: If the `PSYNC_CONFIG_DIR` environment variable is set to a **non-empty, non-whitespace** path, the config file is expected at `$PSYNC_CONFIG_DIR/config.yml`.
2. **Local Directory**: If a `./config` directory exists in the current working directory, the config file is expected at `./config/config.yml`.
3. **Global Directory**: Otherwise, the OS-specific user config directory is used (via `platformdirs`).

The global config directory and environment variable directory are automatically created if they don't exist.
