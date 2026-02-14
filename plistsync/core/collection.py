"""Collection Protocols for Track Management.

This module defines a set of protocols that model different capabilities a track
collection might support. These protocols use Python's structural subtyping (PEP 544)
rather than inheritance-based interfaces, offering flexibility in composing complex
behaviors while maintaining strong type safety and clarity.

Key Design Principles:
----------------------
1. Capability-based Design:
   Collections declare what operations they support by implementing specific protocols:

   - **GlobalLookup**: Enables exact matching via globally unique identifiers.
   - **LocalLookup**: Supports context-specific identifier matching.
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

    class MyTrackCollection(Collection, GlobalLookup, LocalLookup, TrackStream):
        # Implement required methods...
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import (
    Concatenate,
    Generic,
    ParamSpec,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from .matching import Matches, Similarity, fuzzy_match
from .track import GlobalTrackIDs, LocalTrackIDs, Track, TrackInfo

R = TypeVar("R")
P = ParamSpec("P")


@runtime_checkable
class GlobalLookup(Protocol):
    """A collection that can find tracks using global unique IDs."""

    @abstractmethod
    def find_by_global_ids(self, global_ids: GlobalTrackIDs) -> Track | None:
        """Find a single track by its global identifiers."""
        ...

    def find_many_by_global_ids(
        self, global_ids_list: Iterable[GlobalTrackIDs]
    ) -> Iterable[Track | None]:
        """Find multiple tracks by their global identifiers.

        Default implementation iterates over the provided list and calls
        `find_by_global_ids` for each entry. Collections can override this
        method to provide a more efficient batch lookup if supported.
        """
        for global_ids in global_ids_list:
            yield self.find_by_global_ids(global_ids)


@runtime_checkable
class LocalLookup(Protocol):
    """A collection that can find tracks using local context-specific IDs."""

    @abstractmethod
    def find_by_local_ids(self, local_ids: LocalTrackIDs) -> Track | None:
        """Find a single track by its local identifiers."""
        # TODO: local ids might potentially return multiple tracks.
        # Not decided how to handle this 100% yet. For now, we raise warnings
        # and return the first match. (Same goes for global ids, actually.)
        ...

    def find_many_by_local_ids(
        self, local_ids_list: Iterable[LocalTrackIDs]
    ) -> Iterable[Track | None]:
        """Find multiple tracks by their local identifiers.

        Default implementation iterates over the provided list and calls
        `find_by_local_ids` for each entry. Collections can override this
        method to provide a more efficient batch lookup if supported.
        """
        for local_ids in local_ids_list:
            yield self.find_by_local_ids(local_ids)


@runtime_checkable
class InfoLookup(Protocol):
    """A collection that can search for tracks using metadata."""

    @abstractmethod
    def find_by_info(self, info: TrackInfo) -> Iterable[Track]:
        """Find tracks matching the given metadata."""
        ...


T = TypeVar("T", bound=Track)


@runtime_checkable
class TrackStream(Protocol[T]):
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
    ) -> Iterable[tuple[list[R], list[T]]]:
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


class Collection(ABC):
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
    ) -> Matches:
        """Potential matches for the given track based on different lookup strategies.

        The method checks for matches in this order:

        1. Global IDs (exact match, returns immediately if found)
        2. Local IDs (exact match with similarity check)
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
        found_tracks: list[Track] = []
        similarities: list[Similarity] = []

        # Check capabilities of this collection,
        # protocol instance checks can be expensive
        has_global_lookup = isinstance(self, GlobalLookup)
        has_local_lookup = isinstance(self, LocalLookup)
        has_info_lookup = isinstance(self, InfoLookup)
        is_stream = isinstance(self, TrackStream)

        # 1. Try global ID lookup first (exact match, highest priority)
        if has_global_lookup:
            if found_track := self.find_by_global_ids(track.global_ids):  # type: ignore[attr-defined]
                return Matches(
                    truth=track, found=[found_track], found_similarities=[1.0]
                )

        # 2. Try local ID lookup (exact match with similarity check)
        if has_local_lookup:
            if found_track := self.find_by_local_ids(track.local_ids):  # type: ignore[attr-defined]
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
        if is_stream and not (
            has_global_lookup and has_local_lookup and has_info_lookup
        ):
            # TODO: we might to skip the fuzzy match for the global
            # id case
            for similarity, found_track in self.map_threadpool(  # type: ignore[attr-defined]
                _fuzzy_match_track, chunk_size=1000, b=track
            ):
                if not has_global_lookup:
                    for key, value in track.global_ids.items():
                        if found_track.global_ids.get(key) == value:
                            return Matches(
                                truth=track,
                                found=[found_track],
                                found_similarities=[1.0],
                            )

                if similarity < cutoff:
                    continue

                if not has_local_lookup:
                    for key, value in track.local_ids.items():
                        if found_track.local_ids.get(key) == value:
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


C = TypeVar("C", bound=Collection)


class LibraryCollection(Generic[C], Collection, ABC):
    """Represents a collection of tracks in a library with playlist management.

    This class serves as a base for library collections across diverse services.
    It provides a framework for managing tracks and playlists, allowing each service
    to implement its specifics.
    """

    @property
    @abstractmethod
    def playlists(self) -> Iterable[C]:
        """Retrieve playlists associated with this library collection."""
        ...

    @abstractmethod
    def get_playlist(self, *args, **kwargs) -> C | None:
        """Get a playlist by identifier.

        Implement with kwargs like ``name=``, ``id=``, ``url=``, or ``uri=``.
        Return ``None`` for name searches that fail.
        """
        ...
