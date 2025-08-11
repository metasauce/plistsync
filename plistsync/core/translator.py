"""Translator functions.

Not really an abstract base class, but placed it here for now.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable, List

from Levenshtein import ratio as levenshtein_ratio

from plistsync.logger import log

if TYPE_CHECKING:
    from .collection import Collection
    from .track import Track, TrackInfo


Similarity = float


@dataclass
class Match:
    truth: Track
    found: List[Track] = field(default_factory=list)
    found_similarities: List[Similarity] = field(default_factory=list)

    @property
    def similarity(self) -> Similarity:
        """Highest similarity value, corresponding to the best match.

        1.0 -> perfect match, `found` has len 1
        0.0 -> no match, `found` has len 0
        else -> multiple matches
        """
        if len(self.found_similarities) == 0:
            return 0.0
        return max(self.found_similarities)

    def to_dict(self) -> dict:
        """Convert to dictionary representation.

        Always assumes the multiple matches representation. I.e.
        similarity is a list of floats and found is a list of tracks.
        """

        f = self.found
        if not isinstance(f, list):
            f = [f]

        s = self.similarity
        if not isinstance(s, list):
            s = [s]

        return {
            "similarity": s,
            "truth": self.truth.to_dict(),
            "found": [t.to_dict() for t in f if t is not None],
        }


def match_collections(
    col1: Collection,
    col2: Collection,
) -> Iterable[Match]:
    """Match two collections.

    The first collection is always matched to the second collection. I.e. the first
    one has to be smaller than the second one.

    Parameters
    ----------
    col1: Collection
        The first collection to match. The first collection is always matched to the
        second collection. This collection has to be of finite Size!
    col2: Collection
        The second collection to match.
    """

    # The first collection has a (reasonable) finite length
    # otherwise matching is not possible
    # At the moment I expect any iterable collection to have a (reasonable) finite length
    # this might be a wrong assumption and should be checked in the future
    if not col1.is_iterable():
        raise ValueError("The first collection is not iterable.")

    # For the naive approach we iterate over all tracks in the first collection
    # and try to find a match in the second collection
    # We might want to revise this with some parallelization or other optimizations
    # in the future. I think just using numpy and a threadpool if there are many
    # tracks might be a good idea.
    for track in col1:
        # 1. We try to match by identifiers, this should be straight forward
        found_track = col2.find_by_identifiers(track.identifiers)
        if found_track is not None:
            # We found a match
            yield Match(
                truth=track,
                found=[found_track],
                found_similarities=[1.0],
            )
            continue

        # 2. We try to match by track metadata
        # In our approach this is called fuzzy matching
        # This is a bit more complicated and might need some more work
        similarities, tracks = col2.find_by_track(track, cutoff=0.6)
        if len(similarities) > 0 and len(tracks) > 0:
            # We found some matches
            yield Match(
                truth=track,
                found=tracks,
                found_similarities=similarities,
            )
            continue

        # 3. No match found!
        yield Match(
            truth=track,
        )


def fuzzy_match(a: Track, b: Track) -> Similarity:
    """Calculate the similarity between two tracks, given their metadata.

    Converts the tracks to a common format, i.e. an dict with all relevant
    metadata. Depending on the type of the metadata different algorithms are used to get the distance between the two records.

    Interpreting the results:
    - 1.0: Every found metadata is the same. Skipping each undefined metadata this includes empty strings and None values.
    - 0.0: No metadata is the same.

    Parameter:
    ----------
    a: Track
        The first track to compare.
    b: Track
        The second track to compare.

    Return:
    -------
    float
        The similarity metric between the two tracks.
    """

    metadata_a = a.info
    metadata_b = b.info
    distances: List[float] = []

    if len(metadata_a) > len(metadata_b):
        metadata_a, metadata_b = metadata_b, metadata_a

    for _, value, other_value in _matched_iter_items(metadata_a, metadata_b):
        # We calculate the distance between the two values
        # None values are undefined and are not considered
        d = distance(value, other_value)
        if d is not None:
            distances.append(d)

    if len(distances) == 0:
        return 0.0

    # We return the weighted average of the distances
    # At the moment every entry has the same weight
    # We might want to change this in the future
    return sum(distances) / len(distances)


def distance(a: str | list[str], b: str | list[str]) -> float | None:
    """Calculate the distance between two values.

    Return
    ------
    float
        The distance between the two values. Normalized to a ratio
        between 0 and 1.
    """

    if len(a) == 0 or len(b) == 0:
        return None

    # String values are compared with the Levenshtein distance
    if isinstance(a, str) and isinstance(b, str):
        # We use the jaro winkler distance for strings
        # is by far faster than the levenshtein distance
        # normalized to a similarity metric between 0 and 1
        # see https://rapidfuzz.github.io/Levenshtein/levenshtein.html
        return levenshtein_ratio(a, b)
    # List values are compared by their elements for each permutation
    if isinstance(a, list) and isinstance(b, list):
        if len(a) > len(b):
            a, b = b, a  # Ensure a is the shorter one

        permutations = itertools.permutations(b, len(a))

        # We calculate the distance for each permutation
        distances = []
        for perm in permutations:
            for i, j in zip(a, perm):
                d = distance(i, j)
                if d is not None:
                    distances.append(d)

        if len(distances) == 0:
            return None

        # We return the average distance
        return sum(distances) / len(distances)

    if a == b:
        return 1.0
    log.warning(
        f"Cannot calculate distance between {a} and {b}. Type '{type(a)}' and '{type(b)}' not supported."
    )
    return None


def _matched_iter_items(
    a: TrackInfo, b: TrackInfo
) -> Iterable[tuple[str, str | list[str], str | list[str]]]:
    """Iterate over the keys of two TrackInfo objects.

    Iterate over the keys of two TrackInfo objects and yield
    the key and the values of both objects if they are present in both.
    """
    for key in a.keys():
        value_a: str | list[str] = a[key]
        value_b: str | list[str] | None = b.get(key, None)
        if value_b is None:
            continue
        yield key, value_a, value_b
