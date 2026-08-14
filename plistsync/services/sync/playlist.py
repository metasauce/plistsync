from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from plistsync.core import PlaylistID
from plistsync.core.diff import DeleteOp as DiffDeleteOp
from plistsync.core.diff import InsertOp as DiffInsertOp
from plistsync.core.diff import MoveOp as DiffMoveOp
from plistsync.core.diff import list_diff_eq
from plistsync.core.playlist import (
    Playlist,
    PlaylistInfo,
)
from plistsync.core.track import OfflineTrack
from plistsync.logger import log
from plistsync.services.sync.crdt import Fugue, LWWRegister

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence
    from pathlib import Path

    from plistsync.core import Track
    from plistsync.core.matching import Matches
    from plistsync.core.playlist import (
        ServicePlaylist,
    )
    from plistsync.services.sync.crdt import DeleteOp as CRDTDeleteOp
    from plistsync.services.sync.crdt import InsertOp as CRDTInsertOp
    from plistsync.services.sync.crdt import RegisterOp

ReplicaID = int


@dataclass
class _TrackLink:
    """Helper to associate tracks with multiple service-specific playlists.

    This is a wrapper around :class:`OfflineTrack` that hold references to the playlists
    across services to which this tracks belongs.

    However, even if a track holds a reference to a service playlist, it is not
    guaranteed, that the track is still in this playlist (it might have been in
    that playlist once, and now has been removed).
    """

    track: OfflineTrack
    playlists: set[PlaylistID]


@dataclass(frozen=True)
class SyncedPlaylistID(PlaylistID):
    """Unique identifier for a synced playlist."""

    id: UUID

    @classmethod
    def new(cls) -> SyncedPlaylistID:
        """Generate a new unique ID for a synced playlist."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> SyncedPlaylistID:
        """Parse from a string representation of a UUID."""

        if value.startswith(cls.prefix()):
            value = value[len(cls.prefix()) + 1 :]
        return cls(UUID(value))

    @property
    def serial(self) -> str:
        """Plistsync's internal representation (here matches canonical UUID)."""
        return f"{self.prefix()}:{self.id!s}"

    def __str__(self) -> str:
        """Compact display (just the raw UUID)."""
        return str(self.id)


class SyncedPlaylist(Playlist[OfflineTrack]):
    """Orchestrates cross-service playlist sync.

    Holds a :class:`Fugue` of :class:`_TrackLink` objects.
    The fugue is as the operation history, while the tracklinks


    TODO: Fixup/remove this and move it into the docs
    Concepts:
    - internal playlist:
        - ground truth of the playlist, with all tracks
          (independent of service availability)
        - determined by going through all operatioins of the fugue
        - think of it as the latest service-agnostic playlists that is
          derivable from the changelog
    - linked playlist:
        - service-specific reference to the internal playlist
        - may only contain a subset of all tracks of the interal playlist,
          i.e. if a track is missing from this particular service.
        - if sync worked, all tracks avaialable, pretty much a copy of internal playlist
          (or projection into the service)
    - fugue
        - think "history of track operations":
        - holds _tracklinks_ and their operation-history (op-history is append only)
        - crdt data-structure that holds operations and works regardless of their
          order (but still produces a correctly ordered internal playlist)
    - tracklinks
        - make the connection between a service-spanning track and the
          linked playlists on services.
    - fork and replica:
        - here pretty synonymous (only distinction is where is it located / kept)
        - a replica is a copy of the fugue that may receive different changes
          than other replicas (think git fork)
        - replicas can be merged _without_ conflicts via crdt
    """

    _fugue: Fugue[_TrackLink]

    _id: SyncedPlaylistID
    _info: LWWRegister

    # Replica ID -> linked playlist ID mapping. Each linked playlist is a sync target.
    _linked_playlists: dict[ReplicaID, ServicePlaylist[Track]]

    def __init__(
        self,
        name: str,
        description: str | None = None,
        tracks: Sequence[OfflineTrack] | None = None,
    ) -> None:
        """Initialize a new SyncedPlaylist."""
        self._info = LWWRegister()
        self._info.assign("name", name)
        self._info.assign("description", description)
        self._linked_playlists = {}
        self._fugue = Fugue()
        self._id = SyncedPlaylistID.new()

        # Initialize from tracks
        for i, track in enumerate(tracks or []):
            self._fugue.insert(i, _TrackLink(track=track, playlists=set()))

    # ----------------------- Required (Playlist protocol) ----------------------- #

    def _new_replica_id(self) -> ReplicaID:
        """Generate a new replica ID which isn't used yet."""
        return max([*list(self._linked_playlists.keys()), 0]) + 1

    @property
    def info(self) -> PlaylistInfo:
        return PlaylistInfo(**dict(self._info))  # type: ignore[typeddict-item]

    @info.setter
    def info(self, value: PlaylistInfo) -> None:
        for field, field_value in value.items():
            self._info.assign(field, field_value)

    @property
    def tracks(self) -> list[OfflineTrack]:
        return list(map(lambda t: t.track, self._fugue))

    @tracks.setter
    def tracks(self, value: Sequence[OfflineTrack]) -> None:
        raise NotImplementedError(
            "Directly setting tracks is not supported; use sync() instead."
        )

    @property
    def id(self) -> SyncedPlaylistID:
        return self._id

    @property
    def n_linked(self) -> int:
        """Return the number of linked playlists (replicas) for this synced playlist."""
        return len(self._linked_playlists)

    # ------------------------------- Sync specific ------------------------------ #

    def register(self, playlist: ServicePlaylist) -> None:
        """Register a playlist as a synchronization target.

        Existing tracks from the playlist are added to the internal collection.
        Tracks already in the internal collection but missing from the playlist
        are preserved.

        Name and description from the playlist are not used; the internal state is
        authoritative. Use :meth:`sync` to push the internal state back to the playlist.
        """
        replica_id = self._new_replica_id()
        self._linked_playlists[replica_id] = playlist

        if playlist.tracks:
            # Use a fork here so operations carry the new replica ID for versioning.
            fork = self._fugue.fork(replica_id)
            for track in playlist.tracks:
                op = fork.insert(
                    len(fork),
                    _TrackLink(
                        track=OfflineTrack.from_track(track), playlists={playlist.id}
                    ),
                )
                self._fugue.apply(op)

        self._enrich_internal_from(playlist)
        self._push_internal_to(playlist)

    def sync(self) -> None:
        """Synchronize linked playlists with the internal track collection.

        Refreshes linked playlists, merges external changes, enriches tracks with
        missing metadata, and pushes the resulting collection back to linked
        playlists.
        """
        # Get current playlist contents from services
        self.fetch()
        # Reconcile playlist changes into the Fugue (CRDT operations)
        self.merge()
        # Extend the internal state and match tracks between the playlists.
        self.enrich()
        # Push the updated internal state back to all linked playlists.
        self.push()

    def fetch(self) -> None:
        """Refresh linked playlists from their services.

        Fetches the current playlist contents to include changes made outside
        this library.
        """
        for replica_id, playlist in self._linked_playlists.items():
            self._linked_playlists[replica_id] = playlist.library.get_playlist_or_raise(
                id=playlist.id
            )

    def merge(self) -> None:
        """Merge changes from linked playlists into the internal collection.

        Reconciles both track membership (via the Fugue) and playlist
        metadata such as name/description (via the info register).
        """
        track_ops: list[CRDTInsertOp[_TrackLink] | CRDTDeleteOp] = []
        info_ops: list[RegisterOp[Any]] = []
        for replica_id, playlist in self._linked_playlists.items():
            for op in self._playlist_diff_ops(replica_id, playlist):
                track_ops.append(op)
            for op in self._info_diff_ops(replica_id, playlist):
                info_ops.append(op)

        for track_op in track_ops:
            self._fugue.apply(track_op)
        for info_op in info_ops:
            self._info.apply(info_op)

    def _info_diff_ops(
        self, replica_id: int, playlist: ServicePlaylist
    ) -> Iterable[RegisterOp[Any]]:
        """Produce register ops to reconcile *playlist*'s info with a fork.

        As for the track diff, an op is only produced for fields that
        actually changed on the service since this replica's last write, so
        unchanged playlists never clobber newer values from other replicas.
        An explicit None counts as a change (clearing e.g. a description);
        fields *absent* from the playlist's info are left untouched, as they
        may be unsupported by the service and the register has no deletion
        semantics.
        """
        fork = self._info.fork(replica_id)
        for field, value in playlist.info.items():
            last = self._info.last_op_by(field, replica_id)
            if last is None or last.value != value:
                yield fork.assign(field, value)

    def _playlist_diff_ops(
        self, replica_id: int, playlist: ServicePlaylist
    ) -> Iterable[CRDTInsertOp[_TrackLink] | CRDTDeleteOp]:
        """Produce CRDT ops to reconcile *playlist* with a fork."""
        fork = self._fugue.fork(replica_id)

        # Check which tracks of the current service playlist are already in the fugue
        # Projection for this playlist only, we skip tracks of all other playlists
        old: list[OfflineTrack] = [
            synced_track.track
            for synced_track in fork
            if playlist.id in synced_track.playlists
        ]

        new = [OfflineTrack.from_track(t) for t in playlist.tracks]
        diff_ops = list_diff_eq(
            old,
            new,
            # We compare via intersection of the IDs, as the same track may have
            # different subsets of the "true"
            eq_func=lambda t1, t2: bool(t1.ids & t2.ids),
        )

        for step in diff_ops.iter():
            op = step.op
            if isinstance(op, DiffInsertOp):
                yield fork.insert(
                    op.idx, _TrackLink(track=op.item, playlists={playlist.id})
                )
            elif isinstance(op, DiffDeleteOp):
                yield fork.delete(op.idx)
            elif isinstance(op, DiffMoveOp):
                yield fork.delete(op.old_idx)
                yield fork.insert(
                    op.new_idx, _TrackLink(track=op.item, playlists={playlist.id})
                )

    def enrich(self) -> None:
        """Enrich tracks with IDs and playlist associations from linked playlists.

        This is a one-way operation that updates the internal track collection
        based on the contents of the linked playlists. It does not push changes
        back to the linked playlists.
        """

        for playlist in self._linked_playlists.values():
            self._enrich_internal_from(playlist)

    def _batch_match(
        self,
        playlist: ServicePlaylist,
        linked_tracks: list[_TrackLink],
    ) -> list[Matches[Track]]:
        """Match *linked_tracks* against *playlist*, falling back to its library.

        First, batch-matches against the playlist. Any track still unmatched
        is then batch-matched against the library. Results are returned in the
        same order as *linked_tracks*.
        """
        queries = [lt.track for lt in linked_tracks]
        results: list[Matches] = list(playlist.match_many(queries))

        unmatched = [
            (i, queries[i]) for i, r in enumerate(results) if r.best_match is None
        ]
        if unmatched:
            indices, remaining = zip(*unmatched)
            for idx, match in zip(indices, playlist.library.match_many(remaining)):
                results[idx] = match

        return results

    def _enrich_internal_from(self, playlist: ServicePlaylist) -> None:
        """Enrich the internal track collection from a linked playlist."""
        to_match = [lt for lt in self._fugue if playlist.id not in lt.playlists]
        if not to_match:
            return

        for lt, match in zip(to_match, self._batch_match(playlist, to_match)):
            if match.best_match is not None:
                lt.track.enrich(match.best_match.ids)
                lt.playlists.add(playlist.id)
            else:
                log.debug(
                    f"No match found for {lt.track} in {playlist.id};"
                    " skipping enrichment."
                )

    def push(self) -> None:
        """Update linked playlists from the internal track collection.

        Resolves tracks for each service and aligns their playlist contents.
        """

        for playlist in self._linked_playlists.values():
            self._push_internal_to(playlist)

    def _push_internal_to(self, playlist: ServicePlaylist[Track]) -> None:
        """Update a linked playlist from the internal track collection."""
        to_match = [lt for lt in self._fugue if playlist.id in lt.playlists]
        if not to_match:
            with playlist.edit():
                playlist.name = self.name
                playlist.description = self.description
                playlist.tracks = []
            return

        new_tracks: list[Track] = []
        for lt, match in zip(to_match, self._batch_match(playlist, to_match)):
            if match.best_match is None:
                log.warning(
                    f"Track {lt.track} not found in {playlist.id}; "
                    "removing playlist association."
                )
                lt.playlists.remove(playlist.id)
            else:
                new_tracks.append(match.best_match)

        with playlist.edit():
            playlist.name = self.name
            playlist.description = self.description
            playlist.tracks = new_tracks

    def track_associations(
        self,
    ) -> Iterable[tuple[OfflineTrack, set[ServicePlaylist[Track]]]]:
        """Iterate all tracks, along with their associated playlists."""
        for linked_track in self._fugue:
            yield (
                linked_track.track,
                set(
                    filter(
                        lambda p: p.id in linked_track.playlists,
                        self._linked_playlists.values(),
                    )
                ),
            )

    def save_to(self, path: Path | str) -> None:
        """Serialize the synced playlist to a JSON-serializable object."""
        import json

        from .serialize import SyncedPlaylistSerializer

        serializer = SyncedPlaylistSerializer()
        serializable = serializer.dump(self)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=4)

    @classmethod
    def load_from(cls, path: Path | str) -> SyncedPlaylist:
        """Load a synced playlist from a JSON-serializable object."""
        import json

        from .serialize import SyncedPlaylistSerializer

        with open(path, encoding="utf-8") as f:
            serializable = json.load(f)

        serializer = SyncedPlaylistSerializer()
        return serializer.load(serializable)
