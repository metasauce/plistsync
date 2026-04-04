import pytest
from plistsync.services.tidal.api_types import (
    AlbumAttributes,
    AlbumResource,
    ArtistResource,
    ExternalLink,
    LinkObject,
    MetaObject,
    MultiRelationshipDataDocument,
    PlaylistAttributes,
    PlaylistRelationships,
    PlaylistResource,
    PlaylistsItemsMultiRelationshipDataDocument,
    PlaylistsItemsResourceIdentifier,
    ResourceIdentifier,
    TrackAttributes,
    TrackResource,
)


# Type alias for the lookup dict
ItemsLookup = dict[tuple[str, str], ArtistResource | AlbumResource | TrackResource]


@pytest.fixture
def external_link() -> ExternalLink:
    """Create an example external link."""
    return ExternalLink(href="https://tidal.com/playlist/12345", meta="")


@pytest.fixture
def link_object() -> LinkObject:
    """Create an example link object."""
    return LinkObject(
        self="https://api.tidal.com/v1/playlists/12345",
        next="https://api.tidal.com/v1/playlists/12345?cursor=next",
    )


@pytest.fixture
def meta_object() -> MetaObject:
    """Create an example meta object."""
    return MetaObject(totalItems=42, totalPages=1)


@pytest.fixture
def resource_identifier() -> ResourceIdentifier:
    """Create an example resource identifier."""
    return ResourceIdentifier(id="track-001", type="TRACKS")


@pytest.fixture
def multi_relationship_data() -> MultiRelationshipDataDocument:
    """Create an example multi-relationship data document."""
    return MultiRelationshipDataDocument(
        data=[ResourceIdentifier(id="artist-001", type="ARTISTS")],
        links=LinkObject(self="https://api.tidal.com/v1/artists/artist-001"),
    )


@pytest.fixture
def album_attributes() -> AlbumAttributes:
    """Create example album attributes."""
    return AlbumAttributes(
        title="Led Zeppelin IV",
        year=1971,
        duration=2538000,
        searchable=True,
        explicit=False,
    )


@pytest.fixture
def artist_resource() -> ArtistResource:
    """Create an example artist resource."""
    return ArtistResource(
        id="artist-001",
        type="ARTISTS",
        attributes={"name": "Led Zeppelin"},
    )


@pytest.fixture
def album_resource(album_attributes: AlbumAttributes) -> AlbumResource:
    """Create an example album resource."""
    return AlbumResource(
        id="album-001",
        type="ALBUMS",
        attributes=album_attributes,
    )


@pytest.fixture
def track_attributes() -> TrackAttributes:
    """Create example track attributes."""
    return TrackAttributes(
        title="Stairway to Heaven",
        duration=482000,
        explicit=False,
        isrc="GBUM71002904",
        bpm=82.5,
        key="E",
        keyScale="MAJOR",
        mediaTags=["LOSSLESS", "HI_RES"],
        popularity=0.95,
        externalLinks=[],
    )


@pytest.fixture
def track_resource(
    track_attributes: TrackAttributes,
    multi_relationship_data: MultiRelationshipDataDocument,
) -> TrackResource:
    """Create an example track resource."""
    return TrackResource(
        id="track-001",
        type="TRACKS",
        attributes=track_attributes,
        relationships={
            "albums": multi_relationship_data,
            "artists": multi_relationship_data,
            "credits": MultiRelationshipDataDocument(data=[], links=LinkObject()),
            "genres": MultiRelationshipDataDocument(data=[], links=LinkObject()),
            "lyrics": MultiRelationshipDataDocument(data=[], links=LinkObject()),
            "owners": MultiRelationshipDataDocument(data=[], links=LinkObject()),
            "providers": MultiRelationshipDataDocument(data=[], links=LinkObject()),
            "radio": MultiRelationshipDataDocument(data=[], links=LinkObject()),
            "shares": MultiRelationshipDataDocument(data=[], links=LinkObject()),
            "similarTracks": MultiRelationshipDataDocument(data=[], links=LinkObject()),
            "replacement": {"data": {"id": "", "type": ""}},
            "sourceFile": {"data": {"id": "", "type": ""}},
            "trackStatistics": {"data": {"id": "", "type": ""}},
        },
    )


@pytest.fixture
def items_lookup(
    artist_resource: ArtistResource,
    album_resource: AlbumResource,
    track_resource: TrackResource,
) -> ItemsLookup:
    """Create an example lookup dict for playlist items.

    This matches the structure returned by api.get_items() and is used
    by TidalPlaylistTrack to resolve related resources.
    """
    return {
        ("ARTISTS", "artist-001"): artist_resource,
        ("ALBUMS", "album-001"): album_resource,
        ("TRACKS", "track-001"): track_resource,
    }


@pytest.fixture
def playlist_attributes(external_link: ExternalLink) -> PlaylistAttributes:
    """Create example playlist attributes."""
    return PlaylistAttributes(
        accessType="STREAM",
        bounded=False,
        createdAt="2024-01-15T10:30:00Z",
        lastModifiedAt="2024-06-20T14:22:00Z",
        name="My Favorite Rock Songs",
        numberOfFollowers=1542,
        playlistType="USER",
        description="A collection of classic rock tracks",
        duration="PT2H30M15S",
        numberOfItems=42,
        externalLinks=[external_link],
    )


@pytest.fixture
def playlist_item_identifier() -> PlaylistsItemsResourceIdentifier:
    """Create an example playlist item identifier with meta."""
    return PlaylistsItemsResourceIdentifier(
        id="track-001",
        type="TRACKS",
        meta={
            "addedAt": "2024-03-01T08:00:00Z",
            "itemId": "item-001",
        },
    )


@pytest.fixture
def playlist_relationships(
    multi_relationship_data: MultiRelationshipDataDocument,
    playlist_item_identifier: PlaylistsItemsResourceIdentifier,
) -> PlaylistRelationships:
    """Create example playlist relationships."""
    return PlaylistRelationships(
        coverArt=multi_relationship_data,
        ownerProfiles=multi_relationship_data,
        owners=multi_relationship_data,
        items=PlaylistsItemsMultiRelationshipDataDocument(
            data=[playlist_item_identifier],
            links=LinkObject(
                self="https://api.tidal.com/v1/playlists/12345/relationships/items",
                next="https://api.tidal.com/v1/playlists/12345/relationships/items?cursor=next",
            ),
        ),
    )


@pytest.fixture
def playlist_resource(
    playlist_attributes: PlaylistAttributes,
    playlist_relationships: PlaylistRelationships,
) -> PlaylistResource:
    """Create an example playlist resource."""
    return PlaylistResource(
        id="12345",
        type="PLAYLISTS",
        attributes=playlist_attributes,
        relationships=playlist_relationships,
    )
