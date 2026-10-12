# Configuration

The quickstart builds a library from a config. Every service follows the same pattern:
`from_config` is the alternative constructor that takes a service config, while the
regular constructor takes internal objects such as an API session. It never reads files
or environment variables, keeping IO out of the core library so each application decides
where its config comes from.

## From a file

The CLI ships {py:class}`UserDirConfigIO <plistsync.cli.config.UserDirConfigIO>`, one
implementation of the {py:class}`ConfigIO <plistsync.core.config.ConfigIO>` interface
that reads and writes the config in your user config directory. You can write your own,
for example for environment variables or a secret manager.

```python
from plistsync.cli.config import UserDirConfigIO
from plistsync.services.spotify import SpotifyConfig, SpotifyLibrary

config = UserDirConfigIO().load(SpotifyConfig)
library = SpotifyLibrary.from_config(config)
```

## Inline

Configs are plain dataclasses, so you can also construct one directly, for example when
embedding `plistsync` in your own application. `client_id` and `redirect_port` default
to the built-in Spotify app, and the token can be read from a file with `JsonFileIO`:

```python
from pathlib import Path

from plistsync.core.config import JsonFileIO
from plistsync.services.spotify import SpotifyConfig, SpotifyLibrary
from plistsync.utils.auth.oauth2 import OAuth2Token

config = SpotifyConfig(
    client_id="<your client id>",
    redirect_port=20556,
    token=JsonFileIO[OAuth2Token](Path("spotify_token.json")),
)
library = SpotifyLibrary.from_config(config)
```

`JsonFileIO` is the file-backed {py:class}`DataIO <plistsync.core.config.DataIO>`
implementation, so the token is only read when the library needs it. The file uses the
same JSON format that the CLI writes, which you can also produce yourself.

To obtain a token from code, see the [Authentication](authentication.md) guide.
