from __future__ import annotations

from typing import Generic, Literal, NotRequired, TypedDict, TypeVar

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
    country: str
    email: NotRequired[str]
    emailVerified: NotRequired[bool]
    firstName: NotRequired[str]
    lastName: NotRequired[str]
    nostrPublicKey: NotRequired[str]
    username: str


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
    accessType: NotRequired[str]
    availability: NotRequired[Literal["STREAM", "DJ", "STEM"]]
    bpm: NotRequired[float]
    createdAt: NotRequired[str]  # iso 8601
    duration: int
    explicit: bool
    externalLinks: list[ExternalLink]
    isrc: str
    key: Literal[
        "UNKNOWN",
        "C",
        "CSharp",
        "D",
        "Eb",
        "E",
        "F",
        "FSharp",
        "G",
        "Ab",
        "A",
        "Bb",
        "B",
    ]
    keyScale: Literal[
        "UNKNOWN",
        "MAJOR",
        "MINOR",
        "AEOLIAN",
        "BLUES",
        "DORIAN",
        "HARMONIC_MINOR",
        "LOCRIAN",
        "LYDIAN",
        "MIXOLYDIAN",
        "PENTATONIC_MAJOR",
        "PHRYGIAN",
        "MELODIC_MINOR",
        "PENTATONIC_MINOR",
    ]
    mediaTags: list[str]
    popularity: float  # 0-1
    spotlighted: NotRequired[bool]
    title: str
    toneTags: NotRequired[list[str]]
    version: NotRequired[str]

    # Special fields TODO
    # copyright


class PlaylistAttributes(TypedDict):
    # REQUIRED fields per schema
    accessType: str
    bounded: bool
    createdAt: str  # ISO date-time
    lastModifiedAt: str  # ISO date-time
    name: str
    numberOfFollowers: int
    playlistType: str  # enum, but keep as str for now

    # OPTIONAL fields
    description: NotRequired[str]
    duration: NotRequired[str]  # ISO 8601 duration (P30M5S)
    numberOfItems: NotRequired[int]

    externalLinks: list[ExternalLink]


# External Link type (from schema snippet)
class ExternalLink(TypedDict):
    href: str
    meta: str


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


class PlaylistsItemsResourceIdentifierMeta(TypedDict):
    addedAt: NotRequired[str]  # When item was added to playlist
    itemId: NotRequired[str]  # Original item ID


class PlaylistsItemsResourceIdentifier(ResourceIdentifier):
    meta: NotRequired[PlaylistsItemsResourceIdentifierMeta]


class PlaylistsItemsMultiRelationshipDataDocument(TypedDict):
    # e.g. Playlists_Items_Multi_Relationship_Data_Document
    data: NotRequired[list[PlaylistsItemsResourceIdentifier]]
    included: NotRequired[list[RelationshipResource]]
    links: LinkObject


class TrackRelationships(TypedDict):
    albums: MultiRelationshipDataDocument
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


class PlaylistRelationships(TypedDict):
    # Standard Multi_Relationship_Data_Document
    coverArt: MultiRelationshipDataDocument
    ownerProfiles: MultiRelationshipDataDocument
    owners: MultiRelationshipDataDocument
    items: PlaylistsItemsMultiRelationshipDataDocument


# Resources


class SimpleResource(TypedDict, Generic[T_Attribute]):
    id: str
    type: str
    attributes: T_Attribute


class RelationshipResource(TypedDict, Generic[T_Attribute, T_Relationship]):
    id: str
    type: str
    attributes: T_Attribute
    relationships: NotRequired[T_Relationship]


ArtistResource = SimpleResource[NameAttribute]
GenreResource = SimpleResource[NameAttribute]
UserResource = SimpleResource[UserAttributes]
AlbumResource = RelationshipResource[AlbumAttributes, AlbumRelationships]
TrackResource = RelationshipResource[TrackAttributes, TrackRelationships]
PlaylistResource = RelationshipResource[PlaylistAttributes, PlaylistRelationships]


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
PlaylistIncludedResource = AlbumResource | ArtistResource | TrackResource
PlaylistDocument = SingleResourceDataDocument[
    PlaylistResource, PlaylistIncludedResource
]
PlaylistListDocument = MultiResourceDataDocument[
    PlaylistResource, PlaylistIncludedResource
]
UserDocument = SingleResourceDataDocument[UserResource, UserResource]
