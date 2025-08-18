from __future__ import annotations

from typing import Generator, List, Self

from plistsync.core import Track, GlobalTrackIDs

from ...errors import NotFoundError
from ...logger import log


class TidalTrack(Track):
    """TidalTrack is a track object that represents a track we got from the tidal api.

    We opted to just use the returned data and included relationships from the tidal api as it is. For simplicity and interoperability, we do not to parse it into a more usable format.

    As usual with all Track objects, this class implements all abstract methods from the Track class to get the different properties of the track if available.
    """

    data: dict
    included: list[dict]

    def __init__(self, data: dict, included: List[dict]):
        self.data = data
        self.included = included

    @classmethod
    def from_tracks_response(cls, data: list[dict], included: list[dict]) -> List[Self]:
        """Create TidalTrack objects from a tidal https://openapi.tidal.com/v2/tracks response.

        Requires to have optional included data in the response if you want to have the artists and albums in the track object.

        Keeps the order of the tracks in the response.

        E.g.:
        -----
        ```python
        res = requests.get(
            f"https://openapi.tidal.com/v2/tracks",
            params={
                "filter[id]": ",".join(track_ids),
                "include": "albums,artists",
                "countryCode": "US",
            },
            auth=token,
        )

        if res.status_code != 200:
            raise Exception("Failed to fetch tracks from tidal")

        data = res.json().get("data", [])
        included = res.json().get("included", [])

        tracks = TidalTrack.from_tracks_response(data, included)
        ```
        """

        tracks = []
        for item in data:
            """
            "relationships": {
                "albums": {
                    "data": [{"id": "333365055", "type": "albums"}]
                },
                "artists": {
                    "data": [{"id": "34372436", "type": "artists"}, ... ]
                },
                ...other unused relationships
            },
            """
            # Get relationship keys (ids and types) for matching
            track_relationships = item.get("relationships", {})
            track_relationships = [
                *track_relationships.get("albums", {}).get("data", []),
                *track_relationships.get("artists", {}).get("data", []),
            ]

            track_included = []
            for inc in included:
                inc_id = inc.get("id")
                inc_type = inc.get("type")
                if inc_id is None or inc_type is None:
                    log.warning(
                        f"Metadata from tidal api missing id or type for included {inc=}"
                    )
                    continue

                for rel in track_relationships:
                    if inc_id == rel.get("id") and inc_type == rel.get("type"):
                        track_included.append(inc)
                        break

            tracks.append(cls(item, track_included))
        return tracks

    # ---------------------------------------------------------------------------- #
    #                        Helper methods (tidal specific)                       #
    # ---------------------------------------------------------------------------- #
    @property
    def _raw_artists(self) -> Generator[dict, None, None]:
        for artist_rel in (
            self.data.get("relationships", {}).get("artists", {}).get("data", [])
        ):
            for artist in self.included:
                if artist.get("id") == artist_rel.get("id"):
                    yield artist

    @property
    def _raw_albums(self) -> Generator[dict, None, None]:
        for album_rel in (
            self.data.get("relationships", {}).get("albums", {}).get("data", [])
        ):
            for album in self.included:
                if album.get("id") == album_rel.get("id"):
                    yield album

    # ---------------------------------------------------------------------------- #
    #                                 ABC methods                                  #
    # ---------------------------------------------------------------------------- #

    @property
    def title(self) -> str:
        t = self.data.get("attributes", {}).get("title")
        if t is None:
            raise NotFoundError("Title not found")
        return t

    @property
    def artists(self) -> List[str]:
        return [
            str(a.get("attributes", {}).get("name"))
            for a in self._raw_artists
            if a.get("attributes", {}).get("name") is not None
        ]

    @property
    def albums(self) -> List[str]:
        return [
            str(a.get("attributes", {}).get("title"))
            for a in self._raw_albums
            if a.get("attributes", {}).get("title") is not None
        ]

    @property
    def global_ids(self) -> GlobalTrackIDs:
        idents: GlobalTrackIDs = {}

        if isrc := self.data.get("attributes", {}).get("isrc"):
            idents["isrc"] = isrc

        if tidal_id := self.data.get("id"):
            idents["tidal"] = tidal_id

        return idents

    def serialize(self) -> dict:
        return {
            "data": self.data,
            "included": self.included,
        }

    @classmethod
    def deserialize(cls, data: dict) -> Self:
        return cls(data["data"], data["included"])
