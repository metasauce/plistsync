import typer

from plistsync.services.plex.authenticate import auth as plex_auth
from plistsync.services.spotify.authenticate import auth as spotify_auth
from plistsync.services.tidal.authenticate import auth as tidal_auth

# Wrapper for cli auth commands

app = typer.Typer(name="auth", add_completion=False)

app.command(name="tidal")(tidal_auth)
app.command(name="spotify")(spotify_auth)
app.command(name="plex")(plex_auth)


if __name__ == "__main__":
    app()
