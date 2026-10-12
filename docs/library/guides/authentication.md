# Authentication

Services like Spotify, Tidal, and Plex need an access token to talk to their API. Others,
like Traktor, need none. The token is stored in the service config through the
{py:class}`DataIO <plistsync.core.config.DataIO>` abstraction. It can be read lazily from
a file on first access, and it is saved back when it changes.

```{note}
Authenticating is easier from the CLI. `plistsync spotify auth` handles the browser flow
for you, and `--mode manual` works on machines without a browser.
```

## From Python

An auth provider runs the flow for a service and only needs an implementation of
{py:class}`Interaction <plistsync.core.auth.Interaction>` for the user-facing parts:

```python
from plistsync.cli.service_commands.auth import CLIInteraction
from plistsync.services.spotify import SpotifyAuth, SpotifyConfig, SpotifyLibrary

config = SpotifyConfig()
config.token = SpotifyAuth(config).authenticate(CLIInteraction())
library = SpotifyLibrary.from_config(config)
```

`CLIInteraction` is the implementation the CLI uses. It opens the URL in a browser and
prompts on the terminal, and on a remote machine you can use
`CLIInteraction(mode="manual")` to paste a URL instead.

## Custom interactions

{py:class}`Interaction <plistsync.core.auth.Interaction>` is a small interface that the
caller implements. A provider uses whichever primitives its flow needs:

- `open_url(url)`: open or print a URL for the user.
- `show(message)`: display instructions, for example a device code.
- `ask(message)`: ask the user for a value, for example a pasted URL.
- `capture_redirect(redirect_uri)`: wait for the browser callback and return it raw.

Implement these to fit your environment, for example a web app that opens the
authorization page and captures the callback on its own route. `CLIInteraction` is a
ready-made example.
