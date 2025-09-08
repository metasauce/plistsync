from plistsync.core import Track


class SpotifyTrack(Track):
    """A track in Spotify.

    Represents a Spotify track object as returned by the Spotify Web API.
    """

    def __init__(self, data: dict):
        raise NotImplementedError("SpotifyTrack is not implemented yet")
