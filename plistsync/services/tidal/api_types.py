from __future__ import annotations

from typing import Any, Generic, NotRequired, TypedDict, TypeVar

T_Attribute = TypeVar("T_Attribute")
T_Resource = TypeVar("T_Resource")
T_Included = TypeVar("T_Included", bound="ResourceIdentifier")
T_Relationship = TypeVar("T_Relationship")

# Objects


class LinkObject(TypedDict):
    self: NotRequired[str]
    next: NotRequired[str]
    prev: NotRequired[str]


class MetaObject(TypedDict):
    totalItems: NotRequired[int]
    totalPages: NotRequired[int]


# Attributes


class NameAttribute(TypedDict):
    name: str


class UserAttributes(TypedDict):
    name: NotRequired[str]
    username: NotRequired[str]


class AlbumAttributes(TypedDict):
    title: str
    year: NotRequired[int]
    duration: int
    replayGain: NotRequired[float]
    peak: NotRequired[float]
    streamStartDate: NotRequired[str]
    streamEndDate: NotRequired[str]
    contentRating: NotRequired[str]
    explicit: NotRequired[bool]
    searchable: bool


class TrackAttributes(TypedDict):
    title: str
    version: NotRequired[str]
    duration: int
    replayGain: NotRequired[float]
    peak: NotRequired[float]
    searchable: bool
    explicit: NotRequired[bool]
    contentRating: NotRequired[str]
    year: NotRequired[int]
    streamStartDate: NotRequired[str]
    streamEndDate: NotRequired[str]
    saScore: NotRequired[int]
    saQuality: NotRequired[str]
    audioQuality: NotRequired[str]
    audioModes: NotRequired[list[str]]
    mediaMetadata: NotRequired[dict[str, Any]]
    cupEnabled: NotRequired[bool]
    allowExplicit: NotRequired[bool]


# Relationships
# Core relationship types matching schema


class ResourceIdentifier(TypedDict):
    id: str
    type: str


class MultiRelationshipDataDocument(TypedDict):
    data: list[ResourceIdentifier]
    links: LinkObject  # Contains next/self pagination URLs


class SingleRelationshipDataDocument(TypedDict):
    data: ResourceIdentifier
    links: NotRequired[LinkObject]


class TrackRelationships(TypedDict):
    album: MultiRelationshipDataDocument
    artists: MultiRelationshipDataDocument
    credits: MultiRelationshipDataDocument
    genres: MultiRelationshipDataDocument
    lyrics: MultiRelationshipDataDocument
    owners: MultiRelationshipDataDocument
    providers: MultiRelationshipDataDocument
    radio: MultiRelationshipDataDocument
    shares: MultiRelationshipDataDocument
    similarTracks: MultiRelationshipDataDocument

    # Single relationships
    replacement: SingleRelationshipDataDocument
    sourceFile: SingleRelationshipDataDocument
    trackStatistics: SingleRelationshipDataDocument


class AlbumRelationships(TypedDict):
    # Standard Multi_Relationship_Data_Document
    artists: MultiRelationshipDataDocument
    coverArt: MultiRelationshipDataDocument
    genres: MultiRelationshipDataDocument
    owners: MultiRelationshipDataDocument
    providers: MultiRelationshipDataDocument
    similarAlbums: MultiRelationshipDataDocument

    # Single relationships
    replacement: SingleRelationshipDataDocument

    # Special stuff: TODO
    # suggestedCoverArts
    # items


# Resources


class SimpleResource(TypedDict, Generic[T_Attribute]):
    id: str
    type: str
    attributes: T_Attribute


class RelatinionshipResource(TypedDict, Generic[T_Attribute, T_Relationship]):
    id: str
    type: str
    attributes: T_Attribute
    relationship: NotRequired[T_Relationship]


ArtistResource = SimpleResource[NameAttribute]
GenreResource = SimpleResource[NameAttribute]
UserResource = SimpleResource[UserAttributes]
AlbumResource = RelatinionshipResource[AlbumAttributes, AlbumRelationships]
TrackResource = RelatinionshipResource[TrackAttributes, TrackRelationships]

# Documents (highest level api response)


class SingleResourceDataDocument(TypedDict, Generic[T_Resource, T_Included]):
    data: T_Resource
    included: NotRequired[list[T_Included]]
    links: NotRequired[LinkObject]
    meta: NotRequired[MetaObject]


class MultiResourceDataDocument(TypedDict, Generic[T_Resource, T_Included]):
    data: list[T_Resource]
    included: NotRequired[list[T_Included]]
    links: NotRequired[LinkObject]
    meta: NotRequired[MetaObject]


# FIXME: Some include resource missing
AlbumIncludedResource = (
    ArtistResource | UserResource | GenreResource | TrackResource | AlbumResource
)
AlbumsDocument = SingleResourceDataDocument[AlbumResource, AlbumIncludedResource]
AlbumsListDocument = MultiResourceDataDocument[AlbumResource, AlbumIncludedResource]
TrackIncludedResource = AlbumResource | ArtistResource
TrackDocument = SingleResourceDataDocument[TrackResource, TrackIncludedResource]
TrackListDocument = MultiResourceDataDocument[TrackResource, TrackIncludedResource]
