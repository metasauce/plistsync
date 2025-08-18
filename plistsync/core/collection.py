from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import (
    Callable,
    Concatenate,
    Generator,
    List,
    ParamSpec,
    Sequence,
    Tuple,
    TypeVar,
)

import numpy as np
import numpy.typing as npt

from plistsync.logger import log

from .track import Track, TrackIdentifiers
from .matching import Similarity, fuzzy_match

R = TypeVar("R")
P = ParamSpec("P")


class Collection(ABC):
    """A data structure that holds tracks.

    Collections can be thought of as libraries, playlists, or databases that contain tracks.
    They provide methods to access, filter, and iterate over the tracks in a collection.

    For this ABC there is no specific requirements in how the tracks are stored, e.g. in a database, in memory, or on disk.
    The only requirement is that the collection should be iterable and provide a way to find tracks by their identifiers.
    """

    def find_by_identifiers(self, identifiers: TrackIdentifiers) -> Track | None:
        """Return the track with the given identifier if it exists in the collection.

        This method return only one track, as each identifier's value should uniquely identify a track.
        The default implementation iterates over all tracks in linear time. For large collections,
        override this method to use optimized lookups (e.g., database indices).

        Parameters
        ----------
        identifier
            The identifier to search for. I.e. a dictionary containing the identifier keys and values. E.g. {"isrc": "USAT29900609"}
        """
        for track in self:
            for key, value in identifiers.items():
                if track.identifiers.get(key) == value:
                    return track

        return None

    def find_by_track(
        self,
        track: Track,
        cutoff: float = 0.6,
        max_matches: int = 3,
    ) -> Tuple[List[Similarity], List[Track]]:
        """Find the most similar tracks to a given one.

        Search for the most similar tracks to the given one in this collection. Defaults to a relative slow iterative approach, but parent classes can override this method with a more efficient implementation.

        Before using this method try the `find_by_identifiers` method as it is probably faster.

        See `translator.fuzzy_match` for details on the matching algorithm.

        Parameters
        ----------
        track
            The track to compare to.
        cutoff
            The similarity cutoff. Only tracks with a similarity greater than or equal to this cutoff are returned.
        n_matches
            The maximum number of matches to return. If None all matches that are above the cutoff are returned.

        Return:
        -------
        List[Match]
            A list of matches containing the similar tracks and their similarity metric. The list is sorted by similarity in descending order. I.e. the first element is the most similar track!
        """
        similarities: list[Similarity] = []
        tracks: list[Track] = []
        for similarities_chunk, tracks_chunk in self.iter_threadpool(
            fuzzy_match,
            chunk_size=1000,
            b=track,
        ):
            # We should be able to optimize this with numpy if
            # we have performance issues
            for s, t in zip(similarities_chunk, tracks_chunk):
                if s >= cutoff:
                    similarities.append(s)
                    tracks.append(t)

        # Sort by similarities in descending order
        sorted_pairs = sorted(
            zip(similarities, tracks), key=lambda x: x[0], reverse=True
        )
        similarities, tracks = zip(*sorted_pairs) if sorted_pairs else ([], [])  # pyright: ignore[reportAssignmentType]

        return list(similarities)[:max_matches], list(tracks)[:max_matches]

    def get_similarities(
        self,
        tracks: Sequence[Track],
    ) -> Tuple[Sequence[Track], npt.NDArray[np.float64]]:
        r"""Track similarities matrix.

        Get a matrix of similarities between the given tracks and the tracks in this collection. The matrix is of shape (len(tracks), len(self)) and contains the similarity values between each track in `tracks` and each track in the collection.

        We might also need a function to get for multiple tracks at once. Think about playlists with multiple tracks which you want to match with a collection most efficiently.

        Notes
        -----
        This might be a memory intensive operation, e.b. 300 tracks playlist with 100k tracks in the collection would be a 300x100k matrix, I don't think we want to store this in memory. Only the similarities for the tracks are :math:`300 * 100k * 8 \text{bytes} = 229 \text{MB}`.
        """
        raise NotImplementedError("This method is not implemented yet.")

    def is_iterable(self) -> bool:
        """Check if the collection is iterable.

        True if the collection is iterable, False otherwise.
        """
        try:
            iter(self)
            return True
        except NotImplementedError:
            return False

    def iter_threadpool(
        self,
        func: Callable[Concatenate[Track, P], R],
        chunk_size: int = 100,
        max_workers=4,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Generator[Tuple[List[R], List[Track]], None, None]:
        """Apply a function to each track in parallel.

        Iterate over all tracks in the collection and apply a function to each track. Use a threadpool to parallelize a computation.This method should be used to parallelize compute heavy operations on the collection or to speed up the processing of large collections.

        To allow processing large collections we process the collection in chunks of `chunk_size` tracks. This should help to reduce the memory footprint.

        Parameters
        ----------
        func: Callable[[Track], T]
            The function to apply to each element in the collection. First argument should be a track.
        chunk_size: int
            The maximum number of tracks to process in each chunk.
        **kwargs: Any
            Additional keyword arguments to passed to each function call.


        Example
        -------
        If you want to apply a function to each track in the collection, you can use this method like this:

        .. code-block:: python

            def heavy_computation(track: Track, *args) -> int:
                pass # Do some heavy computation on the track and return a result

            for results, tracks in collection.iter_threadpool(heavy_computation, chunk_size=100, *args):
                # do something with the results and related tracks
                pass
        """
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            offset = 0
            while True:
                chunk = itertools.islice(self, offset, offset + chunk_size)

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

    def __iter__(self) -> Generator[Track, None, None]:
        """Return an iterator over all tracks in the collection.

        Throws and not implemented error if the collection is not iterable, e.g. remote collections.
        """
        raise NotImplementedError("This collection is not iterable.")
