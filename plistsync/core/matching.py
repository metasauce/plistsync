"""Translator functions.

Not really an abstract base class, but placed it here for now.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable, Iterator, Sequence

from Levenshtein import ratio as levenshtein_ratio

from plistsync.logger import log

if TYPE_CHECKING:
    from .track import Track, TrackInfo


Similarity = float


@dataclass
class Matches:
    truth: Track
    found: Sequence[Track] = field(default_factory=list)
    found_similarities: list[Similarity] = field(default_factory=list)

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

    def __iter__(self) -> Iterator[tuple[Track, Similarity]]:
        """Iterate over the found tracks."""
        # TODO: sort by similarity, best matches first
        return iter(zip(self.found, self.found_similarities))


def fuzzy_match(a: TrackInfo, b: TrackInfo) -> Similarity:
    """Calculate the similarity between two track infos.

    Interpreting the results:
    - 1.0: Every found metadata is the same. Skipping each undefined metadata this includes empty strings and None values.
    - 0.0: No metadata is the same.

    Return:
    -------
    float
        The similarity metric between the two tracks.
    """

    distances: list[float] = []

    if len(a) > len(b):
        a, b = b, a

    for _, value, other_value in _matched_iter_items(a, b):
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

    Lists are permutation invariant.

    Return
    ------
    float or None
        The distance between the two values. Normalized to a ratio
        between 0 and 1, where 0 is no match and 1 is a perfect match.
        Returns None when invalid objects are passed or empty strings
        (or empty lists) are compared.

    """

    a_seq = isinstance(a, Sequence)
    b_seq = isinstance(b, Sequence)

    if a_seq and b_seq and len(a) == 0 or len(b) == 0:
        return None

    if a == b:
        return 1.0

    # String values are compared with the Levenshtein distance
    if isinstance(a, str) and isinstance(b, str):
        # We use the jaro winkler distance for strings
        # is by far faster than the levenshtein distance
        # normalized to a similarity metric between 0 and 1
        # see https://rapidfuzz.github.io/Levenshtein/levenshtein.html
        return levenshtein_ratio(a, b)

    # List values are compared by their elements for each permutation
    if a_seq and b_seq:
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

        # We return the max with a penalty if list have different lengths
        return max(distances) * (len(a) / len(b))

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
    for key in a:
        value_a: str | list[str] = a[key]  # type: ignore
        value_b: str | list[str] | None = b.get(key, None)  # type: ignore
        if value_b is None:
            continue
        yield key, value_a, value_b
