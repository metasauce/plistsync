from __future__ import annotations

import enum
from typing import Required, TypedDict

# ---------------------------------- Tracks ---------------------------------- #


class PlexApiTrackResponse(TypedDict, total=False):
    ratingKey: Required[str]  # '106387'
    key: str  # '/library/metadata/106387'
    parentRatingKey: str  # '106386'
    grandparentRatingKey: str  # '55906'
    guid: str  # 'local://106387'
    parentGuid: str  # 'local://106386'
    grandparentGuid: str  # 'plex://artist/5d07bbfc403c6402904a5ec9'
    parentStudio: str  # 'Symmetry Recordings'
    type: str  # 'track'
    title: str  # 'If I Could'
    grandparentKey: str  # '/library/metadata/55906'
    parentKey: str  # '/library/metadata/106386'
    grandparentTitle: str  # 'Various Artists'
    parentTitle: str  # '10 Years of Symmetry'
    originalTitle: str  # 'Break, Jack Boston, Kyo'
    summary: str  # ''
    index: int  # 1
    parentIndex: int  # 1
    viewCount: int  # 3
    lastViewedAt: int  # 1734679522
    parentYear: int  # 2016
    thumb: str  # '/library/metadata/106386/thumb/1734353417'
    art: str  # '/library/metadata/55906/art/1713284398'
    parentThumb: str  # '/library/metadata/106386/thumb/1734353417'
    grandparentThumb: str  # '/library/metadata/55906/thumb/1713284398'
    grandparentArt: str  # '/library/metadata/55906/art/1713284398'
    duration: int  # 294990
    addedAt: int  # 1734353414
    musicAnalysisVersion: str  # '1'
    Media: list[PlexApiTrackMedia]
    Image: list[PlexApiTrackImage]
    Genre: list[dict[str, str]]  # [{'tag': 'Jungle'}, {'tag': 'Drum And Bass'}]}
    librarySectionID: int  # 5
    librarySectionKey: str  # '/library/sections/5'
    librarySectionTitle: str  # 'Music'


class PlexApiPlaylistTrackResponse(PlexApiTrackResponse, total=False):
    playlistItemID: int  # needed e.g. for deletion
    ratingCount: int
    updatedAt: int


class PlexApiTrackMedia(TypedDict, total=False):
    id: int  # 106686
    duration: int  # 294990
    bitrate: int  # 1048
    audioChannels: int  # 2
    audioCodec: str  # 'flac'
    container: str  # 'flac'
    hasVoiceActivity: bool  # False
    Part: list[PlexApiTrackPart]


class PlexApiTrackPart(TypedDict, total=False):
    id: int  # 152858
    key: str  # '/library/parts/152858/1735423490/file.flac'
    duration: int  # 294990
    file: str  # '/media/music/clean/01[1047kbps].flac'
    size: int  # 38826912
    container: str  # 'flac'
    hasThumbnail: str | bool  # '1'


class PlexApiTrackImage(TypedDict, total=False):
    alt: str  # 'If I Could'
    type: str  # 'coverPoster' or 'background'
    url: str  # '/library/metadata/55906/thumb/1713284398'


# --------------------------------- Playlist --------------------------------- #


class PlexApiPlaylistResponse(TypedDict, total=False):
    ratingKey: Required[str]  # '109486'
    key: str  # '/playlists/109486/items'
    guid: str  # 'com.plexapp.agents.none://0579aebf-a0f0-4ffb-bdc7-a69685a69adf'
    title: Required[str]  # 'm-tech'
    type: str  # 'playlist'
    summary: str  # ''
    smart: bool  # False
    playlistType: str  # 'audio'
    composite: str  # '/playlists/109486/composite/1755201015'
    duration: int  # 9145000
    leafCount: int  # 21
    addedAt: int  # 1754943684
    updatedAt: int  # 1755201015
    # not included in the /playlists/id endpoint, only in /playlists:
    icon: str  # 'playlist://image.smart'
    viewCount: int  # 34
    lastViewedAt: int  # 1748772887


# --------------------------------- Resources -------------------------------- #


class PlexApiConnection(TypedDict, total=False):
    protocol: str  # http / https
    address: str  # ip
    port: int
    uri: str  # http://192.168.0.103:32400
    local: bool
    relay: bool
    IPv6: bool


class PlexApiResourcesResponse(TypedDict, total=False):
    name: str  # 'pauls_media_server'
    product: str  # 'Plex Media Server'
    productVersion: str  # '1.42.1.10060-4e8b05daf'
    platform: str  # 'Linux'
    platformVersion: str  # '6.8.0-60-generic'
    device: str  # 'Docker Container'
    clientIdentifier: str  # hex string, for servers matches machine id
    provides: str  # 'server' or 'client,player,pubsub-player' (plexamp)
    ownerId: str | None
    sourceTitle: str | None
    publicAddress: str  # '77.23.79.193'
    accessToken: str  # 'xxx-yyyyyyyyy'
    searchEnabled: bool
    createdAt: str  # '2023-03-05T15:32:25Z'
    lastSeenAt: str  # '2026-01-09T18:56:49Z'
    owned: bool
    home: bool
    synced: bool
    relay: bool
    presence: bool
    httpsRequired: bool
    publicAddressMatches: bool
    dnsRebindingProtection: bool
    natLoopbackSupported: bool
    connections: list[PlexApiConnection]


class PlexServerIdentity(TypedDict):
    apiVersion: str  # '1.23.5.4852'
    machineIdentifier: str  # 'XXXXXXXXXXXX
    claimed: bool
    version: str  # '1.28.5.6758-85f0f3f4e'


class PlexMediaTypes(enum.Enum):
    """Plex media types.

    https://developer.plex.tv/pms/#section/API-Info/Types
    """

    MOVIE = 1
    SHOW = 2
    SEASON = 3
    EPISODE = 4
    TRAILER = 5
    PERSON = 7
    ARTIST = 8
    ALBUM = 9
    TRACK = 10
    CLIP = 12
    PHOTO = 13
    PHOTO_ALBUM = 14
    PLAYLIST = 15
    PLAYLIST_FOLDER = 16
    COLLECTION = 18
