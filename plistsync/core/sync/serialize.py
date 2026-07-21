"""Serialization layer for :class:`SyncedPlaylist`.

Composes with :class:`FugueSerializer` for the internal CRDT and provides
round-trip dump/load via plain TypedDict states.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypedDict, TypeVar

from plistsync.core import PlaylistID, TrackID
from plistsync.core.crdt.serialize import (
    FugueSerializer,
    LWWSerializer,
    Serializer,
)
from plistsync.core.sync.playlist import (
    SyncedPlaylist,
    SyncedPlaylistID,
    _TrackLink,
)
from plistsync.core.track import OfflineTrack
from plistsync.services import ServiceLoader

if TYPE_CHECKING:
    from plistsync.core.crdt.serialize import (
        FugueState,
        LWWRegisterState,
    )
    from plistsync.core.playlist import PlaylistInfo

S = TypeVar("S")  # serialized track format (e.g. dict or str)


class SyncedPlaylistState(TypedDict, Generic[S]):
    """Serialized form of a :class:`SyncedPlaylist`."""

    version: int
    """Version of the serialized state. Used for compatibility checks."""

    id: str
    """Unique identifier for the synced playlist."""

    info: LWWRegisterState[PlaylistInfo]
    """Serialized LWW register for the playlist's info."""

    fugue: FugueState[S]
    """Serialized Fugue state for the playlist's track list."""

    linked_playlists: dict[int, str]
    """Mapping of replica IDs to linked playlist serials."""


class TrackLinkSerializer(Serializer[_TrackLink, dict]):
    """Serializer for :class:`_TrackLink` instances."""

    def dump(self, value: _TrackLink) -> dict:
        return {
            "track": {
                "ids": [id.serial for id in value.track.ids],
                "info": value.track.info,
            },
            "in_playlists": [pid.serial for pid in value.playlists],
        }

    def load(self, data: dict) -> _TrackLink:
        track_ids: list[TrackID] = []
        for id in data["track"]["ids"]:
            if not (track_id := TrackID.from_serial(id)):
                raise ValueError(f"Invalid track ID serial {id!r}")
            track_ids.append(track_id)

        playlist_ids: list[PlaylistID] = []
        for pid in data["in_playlists"]:
            if not (playlist_id := PlaylistID.from_serial(pid)):
                raise ValueError(f"Invalid playlist ID serial {pid!r}")
            playlist_ids.append(playlist_id)

        return _TrackLink(
            track=OfflineTrack(
                ids=track_ids,
                info=data["track"]["info"],
            ),
            playlists=set(playlist_ids),
        )


class SyncedPlaylistSerializer(Serializer[SyncedPlaylist, SyncedPlaylistState[dict]]):
    """Round-trip serializer for :class:`SyncedPlaylist`."""

    def __init__(
        self,
    ) -> None:
        self._fugue_ser: FugueSerializer[_TrackLink, dict] = FugueSerializer(
            TrackLinkSerializer()
        )
        self._lww_ser: LWWSerializer[PlaylistInfo, PlaylistInfo] = LWWSerializer()

    def dump(self, value: SyncedPlaylist) -> SyncedPlaylistState[dict]:
        linked_playlists: dict[int, str] = {
            rid: pid.id.serial for rid, pid in value._linked_playlists.items()
        }

        return SyncedPlaylistState(
            version=1,
            id=value.id.serial,
            info=self._lww_ser.dump(value._info),
            fugue=self._fugue_ser.dump(value._fugue),
            linked_playlists=linked_playlists,
        )

    def load(
        self,
        data: SyncedPlaylistState[dict],
    ) -> SyncedPlaylist:
        sp = SyncedPlaylist(
            name="",
            description="",
        )

        # Override auto-generated ID with the persisted one.
        sp._id = SyncedPlaylistID.parse(data["id"])
        sp._fugue = self._fugue_ser.load(data["fugue"])
        sp._info = self._lww_ser.load(data["info"])

        for rid_str, pid_serial in data["linked_playlists"].items():
            service_pl_id = PlaylistID.from_serial(pid_serial)
            if service_pl_id is None:
                raise ValueError(
                    f"Invalid linked playlist serial {pid_serial!r}"
                    f" for replica {rid_str!r}"
                )

            if not (service := ServiceLoader.get(service_pl_id.service())):
                raise ValueError(
                    f"Service {service_pl_id.service()!r} not available"
                    f" maybe the service is not installed or configured?"
                )

            if not (library_cls := service.library()):
                raise ValueError(
                    f"Service {service_pl_id.service()!r} has no library"
                    f" maybe the service is not installed or configured?"
                )

            # TODO:
            # Currently libraries are a bit of annoying as in theory
            # a library can be created with different config options
            # we assume that the config is the same as when the playlist
            # was serialized. This may or may not be wrong...
            playlist = library_cls().get_playlist_or_raise(id=service_pl_id)
            sp._linked_playlists[int(rid_str)] = playlist

        return sp
