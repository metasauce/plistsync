"""Collection Protocols for Track Management.

This module defines a set of protocols that model different capabilities a track
collection might support. These protocols use Python's structural subtyping (PEP 544)
rather than inheritance-based interfaces, offering flexibility in composing complex
behaviors while maintaining strong type safety and clarity.

Key Design Principles:
----------------------
1. Capability-based Design:
   Collections declare what operations they support by implementing specific protocols:

   - **IDLookup**: Enables exact matching via track identifiers (global or local).
   - **InfoLookup**: Facilitates metadata-based similarity searches.
   - **TrackStream**: Provides iteration and bulk processing abilities.

2. Progressive Enhancement:
   Collections can implement additional protocols for more sophisticated matching
   strategies, all while maintaining backward compatibility with basic iteration.

3. Runtime Flexibility:
   The ``@runtime_checkable`` decorator allows collections to be verified at runtime,
   while static type checkers can verify protocol compliance during development.

The main :py:class:`Collection` abstract base class (ABC) demonstrates the integration
of these protocols into a comprehensive track matching strategy via the `match` method.
Developers are encouraged to extend the :py:class:`Collection` class to create new
collection types with different internal storage strategies (e.g. in-memory, databases).

Usage Example:
--------------
Create a custom collection by implementing the desired protocols and extend the
:py:class:`Collection` ABC, ensuring that the ``match`` method efficiently leverages
all relevant capabilities offered by the collection.

.. code-block:: python

    class MyTrackCollection(Collection, IDLookup, TrackStream):
        # Implement required methods...
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import (
    TYPE_CHECKING,
    Concatenate,
    Generic,
    ParamSpec,
    Protocol,
    runtime_checkable,
)

from typing_extensions import TypeVar

from plistsync.services.registry import Registry

from .ids import Scope
from .matching import Matches, fuzzy_match
from .track import Track

R = TypeVar("R")
P = ParamSpec("P")
T = TypeVar("T", bound=Track, covariant=True)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from .ids import PlaylistID, TrackID
    from .matching import Similarity
    from .playlist import ServicePlaylist
    from .track import TrackInfo


Plist = TypeVar(
    "Plist", bound="ServicePlaylist", default="ServicePlaylist", covariant=True
)


@runtime_checkable
class IDLookup(Protocol, Generic[T]):
    """A collection that can find tracks by their :class:`TrackID` identifiers."""

    @abstractmethod
    def find_by_ids(self, ids: Iterable[TrackID]) -> T | None:
        """Find a single track by its identifiers."""
        ...

    def find_many_by_ids(
        self, track_ids_batch: Iterable[Iterable[TrackID]]
    ) -> Iterable[T | None]:
        """Find multiple tracks by their identifiers.

        Default implementation iterates over the provided list and calls
        ``find_by_ids`` for each entry. Collections can override this
        method to provide a more efficient batch lookup if supported.
        """
        for ids in track_ids_batch:
            yield self.find_by_ids(ids)


@runtime_checkable
class InfoLookup(Protocol, Generic[T]):
    """A collection that can search for tracks using metadata."""

    @abstractmethod
    def find_by_info(self, info: TrackInfo) -> Iterable[T]:
        """Find tracks matching the given metadata."""
        ...

    def find_many_by_info(
        self, track_infos_batch: Iterable[TrackInfo]
    ) -> Iterable[Iterable[T]]:
        """Find multiple tracks by their metadata.

        Default implementation iterates over the provided list and calls
        ``find_by_info`` for each entry. Collections can override this
        method to provide a more efficient batch lookup if supported.
        """
        for info in track_infos_batch:
            yield self.find_by_info(info)


@runtime_checkable
class TrackStream(Protocol, Generic[T]):
    """Supports iteration and parallel processing of tracks.

    A collection implementing this protocol must support iteration,
    yielding `Track` objects one by one. This makes it possible to
    traverse all tracks in the collection, for example when scanning
    a library or processing all items in a playlist.
    """

    @property
    @abstractmethod
    def tracks(self) -> Iterable[T]: ...

    def map_threadpool_chunked(
        self,
        func: Callable[Concatenate[T, P], R],
        chunk_size: int = 100,
        max_workers: int = 4,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Iterable[tuple[Sequence[R], Sequence[T]]]:
        """Map a function to each track in parallel.

        Iterate over all tracks in the collection and apply a function to each track.
        Use a threadpool to parallelize a computation. This method should be used to
        parallelize compute heavy operations on the collection or to speed up the
        processing of large collections.

        To allow processing large collections we process the collection in chunks of
        `chunk_size` tracks. This should help to reduce the memory footprint.

        Parameters
        ----------
        func: Callable[[Track], T]
            The function to apply to each element in the collection. First argument
            should be a track.
        chunk_size: int
            The maximum number of tracks to process in each chunk.
        **kwargs: Any
            Additional keyword arguments to passed to each function call.


        Example
        -------
        If you want to apply a function to each track in the collection, you can use
        this method like this:

        .. code-block:: python

            def heavy_computation(track: Track, *args) -> int:
                pass # Do some heavy computation on the track and return a result

            for results, tracks in collection.map_threadpool(
                heavy_computation,
                chunk_size=100,
                *args,
            ):
                # do something with the results and related tracks
                pass
        """
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            offset = 0
            while True:
                chunk = itertools.islice(self.tracks, offset, offset + chunk_size)

                futures = {
                    executor.submit(func, track, *args, **kwargs): track
                    for track in chunk
                }

                if len(futures) == 0:
                    break

                results = []
                tracks = []
                for future in as_completed(futures):
                    results.append(future.result())
                    tracks.append(futures[future])
                # We might still be able to optimize here if we want to
                # In theory we could already start to process the next chunk
                # before yielding the results
                yield results, tracks
                offset += chunk_size

    def map_threadpool(
        self,
        func: Callable[Concatenate[T, P], R],
        chunk_size: int = 100,
        max_workers: int = 4,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Iterable[tuple[R, T]]:
        """Map a function to each track in parallel and return a list of results.

        This is a convenience method that uses `map_threadpool_chunked` to process the
        entire collection and return a flat list of results.
        """
        for chunk in self.map_threadpool_chunked(
            func, chunk_size, max_workers, *args, **kwargs
        ):
            yield from zip(*chunk)


def _fuzzy_match_track(a: Track, b: Track) -> Similarity:
    return fuzzy_match(a.info, b.info)


class Collection(ABC, Generic[T]):
    """A generic data structure that allows lookup or iteration of tracks.

    Collections act as flexible track containers, accommodating multiple storage formats
    and sources, such as online databases or local files, without dictating a specific
    storage mechanism.

    This abstract base class is designed to support adaptable implementations for
    accessing and interacting with tracks in diverse ways, see protocols above.
    """

    def match(
        self,
        track: Track,
        skip_after_local_match: bool = True,
        skip_after_perfect_fuzzy_match: bool = True,
        cutoff=0.6,
    ) -> Matches[T]:
        """Potential matches for the given track based on different lookup strategies.

        The method checks for matches in this order:

        1. IDs with global scope (exact match, returns immediately if found)
        2. IDs with local scope (exact match with similarity check)
        3. Track info (similarity-based search)
        4. Fallback to iterating through all tracks if needed.
           This still uses the three methods above, but is way less efficient.

        Parameters
        ----------
        track
            The track to match against this collection
        skip_after_local_match
            If True, return after first successful match when searching local IDs
        skip_after_perfect_fuzzy_match
            If True, return after finding a perfect fuzzy match (similarity == 1.0)
        cutoff
            Minimum similarity score (0-1) for a match to be considered
        """
        # Initialize result containers
        found_tracks: list[T] = []
        similarities: list[Similarity] = []

        # Check capabilities of this collection,
        # protocol instance checks can be expensive
        has_id_lookup = isinstance(self, IDLookup)
        has_info_lookup = isinstance(self, InfoLookup)
        is_stream = isinstance(self, TrackStream)
        found_track: T

        # 1. ID lookup (global)
        # We search global ids first
        # (exact match, highest priority)
        global_ids = {id for id in track.ids if id.scope is Scope.GLOBAL}
        if has_id_lookup and global_ids:
            if found_track := self.find_by_ids(global_ids):  # type: ignore[attr-defined]
                return Matches(
                    truth=track, found=[found_track], found_similarities=[1.0]
                )

        # 2. ID lookup (local)
        # (exact match with similarity check)
        local_ids = {id for id in track.ids if id.scope is Scope.LOCAL}
        if has_id_lookup and local_ids:
            if found_track := self.find_by_ids(local_ids):  # type: ignore[attr-defined]
                similarity = _fuzzy_match_track(track, found_track)
                if similarity >= cutoff:
                    found_tracks.append(found_track)
                    similarities.append(similarity)

                    if skip_after_local_match:
                        return Matches(
                            truth=track,
                            found=found_tracks,
                            found_similarities=similarities,
                        )

                    if skip_after_perfect_fuzzy_match and similarity == 1.0:
                        return Matches(
                            truth=track,
                            found=found_tracks,
                            found_similarities=similarities,
                        )

        # 3. Try info-based search (similarity match)
        if has_info_lookup:
            for found_track in self.find_by_info(track.info):  # type: ignore[attr-defined]
                similarity = _fuzzy_match_track(track, found_track)
                if similarity >= cutoff:
                    found_tracks.append(found_track)
                    similarities.append(similarity)

                if skip_after_perfect_fuzzy_match and similarity == 1.0:
                    return Matches(
                        truth=track,
                        found=found_tracks,
                        found_similarities=similarities,
                    )

        # 4. Fallback to iterating through all tracks,
        # but only if the collection does not implement all other protocols
        # (in this case, we have already checked all three options)
        if is_stream and not (has_id_lookup and has_info_lookup):
            # TODO: we might to skip the fuzzy match for the global
            # id case
            for similarity, found_track in self.map_threadpool(  # type: ignore[attr-defined]
                _fuzzy_match_track, chunk_size=1000, b=track
            ):
                # Again global scope first
                if not has_id_lookup:
                    if global_ids & found_track.ids:  # Intersection
                        return Matches(
                            truth=track,
                            found=[found_track],
                            found_similarities=[1.0],
                        )

                if similarity < cutoff:
                    continue

                if not has_id_lookup:
                    if local_ids & found_track.ids:
                        found_tracks.append(found_track)
                        similarities.append(similarity)

                        if skip_after_local_match:
                            return Matches(
                                truth=track,
                                found=found_tracks,
                                found_similarities=similarities,
                            )

                if not has_info_lookup:
                    found_tracks.append(found_track)
                    similarities.append(similarity)

                if skip_after_perfect_fuzzy_match and similarity == 1.0:
                    return Matches(
                        truth=track,
                        found=found_tracks,
                        found_similarities=similarities,
                    )

        return Matches(
            truth=track,
            found=found_tracks,
            found_similarities=similarities,
        )

    def match_many(
        self,
        tracks: Iterable[Track],
        skip_after_local_match: bool = True,
        skip_after_perfect_fuzzy_match: bool = True,
        cutoff=0.6,
    ) -> Iterable[Matches[T]]:
        """Match multiple tracks against this collection.

        This method implements a batched matching strategy, yielding results for
        each track in the input iterable. Logic wise it should be equivalent to calling
        `match` for each track, but it can be more efficient for collections that
        implement batched lookup strategies.

        See also :py:meth:`match` for details on the matching strategy and order of
        operations.

        Parameters
        ----------
        tracks
            An iterable of tracks to match against this collection.
        skip_after_local_match
            If True, return after first successful match when searching local IDs.
        skip_after_perfect_fuzzy_match
            If True, return after finding a perfect fuzzy match (similarity == 1.0).
        cutoff
            Minimum similarity score (0-1) for a match to be considered.
        """
        tracks_list = list(tracks)

        # Check capabilities of this collection
        has_id_lookup = isinstance(self, IDLookup)
        has_info_lookup = isinstance(self, InfoLookup)
        is_stream = isinstance(self, TrackStream)

        # Accumulated results per track index
        found_map: defaultdict[int, list[T]] = defaultdict(list)
        sim_map: defaultdict[int, list[float]] = defaultdict(list)

        def record(idx: int, found_track, similarity: float) -> None:
            """Record an match for a track index."""
            found_map[idx].append(found_track)
            sim_map[idx].append(similarity)

        # Tracks still needing processing — pop from this set as each track
        # is fully resolved and should skip later stages.
        remaining: set[int] = set(range(len(tracks_list)))

        # 1. ID lookup (global)
        # We search global ids first
        # (exact match, highest priority)
        if has_id_lookup and remaining:
            indices: list[int] = []
            batches: list[set[TrackID]] = []
            for idx in remaining:
                gids = {
                    _id for _id in tracks_list[idx].ids if _id.scope is Scope.GLOBAL
                }
                if gids:
                    indices.append(idx)
                    batches.append(gids)

            found_tracks: Iterable[T | None] = self.find_many_by_ids(batches)  # type: ignore[attr-defined]
            for idx, found_track in zip(indices, found_tracks):
                if found_track is not None:
                    record(idx, found_track, 1.0)
                    remaining.discard(idx)

        # 2. ID lookup (local)
        # (exact match with similarity check)
        if has_id_lookup and remaining:
            indices = []
            batches = []
            for idx in remaining:
                lids = {_id for _id in tracks_list[idx].ids if _id.scope is Scope.LOCAL}
                if lids:
                    indices.append(idx)
                    batches.append(lids)

            found_tracks = self.find_many_by_ids(batches)  # type: ignore[attr-defined]
            for idx, found_track in zip(indices, found_tracks):
                if found_track is None:
                    continue
                similarity = _fuzzy_match_track(tracks_list[idx], found_track)
                if similarity >= cutoff:
                    record(idx, found_track, similarity)
                    if skip_after_local_match:
                        remaining.discard(idx)
                    if skip_after_perfect_fuzzy_match and similarity == 1.0:
                        remaining.discard(idx)

        # 3. Try info-based search (similarity match)
        # We might be able to optimize this a bit further
        if has_info_lookup and remaining:
            indices = []
            infos: list[TrackInfo] = []
            for idx in remaining:
                indices.append(idx)
                infos.append(tracks_list[idx].info)

            found_tracks_by_info: Iterable[Iterable[T]] = self.find_many_by_info(infos)  # type: ignore[attr-defined]
            for idx, found_tracks in zip(indices, found_tracks_by_info):
                for found_track in found_tracks:
                    similarity = _fuzzy_match_track(tracks_list[idx], found_track)
                    if similarity >= cutoff:
                        record(idx, found_track, similarity)
                        if skip_after_perfect_fuzzy_match and similarity == 1.0:
                            remaining.discard(idx)

        # 4. Fallback to iterating through all tracks,
        # but only if the collection does not implement all other protocols
        # (in this case, we have already checked all three options)
        if is_stream and not (has_id_lookup and has_info_lookup):
            for idx in list(remaining):  # list needed here for safe iteration
                track = tracks_list[idx]
                gids = {_id for _id in track.ids if _id.scope is Scope.GLOBAL}
                lids = {_id for _id in track.ids if _id.scope is Scope.LOCAL}

                for similarity, found_track in self.map_threadpool(  # type: ignore[attr-defined]
                    _fuzzy_match_track, chunk_size=1000, b=track
                ):
                    if not has_id_lookup and gids & found_track.ids:
                        record(idx, found_track, 1.0)
                        remaining.discard(idx)
                        break

                    if similarity < cutoff:
                        continue

                    if not has_id_lookup and lids & found_track.ids:
                        record(idx, found_track, similarity)
                        if skip_after_local_match:
                            remaining.discard(idx)
                            break

                    if not has_info_lookup:
                        record(idx, found_track, similarity)

                    if skip_after_perfect_fuzzy_match and similarity == 1.0:
                        remaining.discard(idx)
                        break

        # Yield results in the order of the input tracks
        for idx, track in enumerate(tracks_list):
            yield Matches(
                truth=track,
                found=found_map[idx],
                found_similarities=sim_map[idx],
            )


class Library(Generic[T, Plist], Collection[T], ABC, Registry):
    """Represents a collection of tracks in a library with playlist management.

    This class serves as a base for library collections across diverse services.
    It provides a framework for managing tracks and playlists, allowing each service
    to implement its specifics.
    """

    @property
    def name(self) -> str:
        """Name of the library, typically the service name."""
        return type(self).__name__.replace("Library", "")

    @property
    @abstractmethod
    def playlists(self) -> Iterable[Plist]:
        """Retrieve playlists associated with this library collection."""
        ...

    @abstractmethod
    def get_playlist(
        self,
        *,
        id: PlaylistID | str | None = None,
    ) -> Plist | None:
        """Get a playlist by identifier.

        Implement with kwargs like ``name=``, ``ids=``, ``url=``, or ``uri=``.
        Return ``None`` for searches that fail.
        """
        ...

    @abstractmethod
    def create_playlist(
        self,
        name: str,
        description: str | None = None,
        tracks: list[T] | None = None,
    ) -> Plist:
        """Create a new playlist."""
        ...

    def get_playlist_or_raise(
        self,
        *,
        id: PlaylistID | str | None = None,
        **kwargs,
    ) -> Plist:
        """Like get_playlist() but raises if no result is found."""
        playlist = self.get_playlist(id=id, **kwargs)
        if playlist is None:
            kwargs["id"] = id
            raise ValueError(f"Could not find playlist for {kwargs}")
        return playlist

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"
