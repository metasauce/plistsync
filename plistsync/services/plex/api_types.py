from __future__ import annotations

from typing import List, Required, TypedDict, Union


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
    Media: List[PlexApiTrackMedia]
    Image: List[PlexApiTrackImage]


class PlexApiTrackMedia(TypedDict, total=False):
    id: int  # 106686
    duration: int  # 294990
    bitrate: int  # 1048
    audioChannels: int  # 2
    audioCodec: str  # 'flac'
    container: str  # 'flac'
    hasVoiceActivity: bool  # False
    Part: List[PlexApiTrackPart]


class PlexApiTrackPart(TypedDict, total=False):
    id: int  # 152858
    key: str  # '/library/parts/152858/1735423490/file.flac'
    duration: int  # 294990
    file: str  # '/media/music/clean/Various Artists/10 Years of Symmetry/01 If I Could [1047kbps].flac'
    size: int  # 38826912
    container: str  # 'flac'
    hasThumbnail: Union[str, bool]  # '1'


class PlexApiTrackImage(TypedDict, total=False):
    alt: str  # 'If I Could'
    type: str  # 'coverPoster' or 'background'
    url: str  # '/library/metadata/55906/thumb/1713284398'


# --------------------------------- Playlist --------------------------------- #


class PlexApiPlaylistResponse(TypedDict, total=False):
    ratingKey: Required[str]  # '109486'
    key: str  # '/playlists/109486/items'
    guid: str  # 'com.plexapp.agents.none://0579aebf-a0f0-4ffb-bdc7-a69685a69adf'
    type: str  # 'playlist'
    title: str  # 'm-tech'
    summary: str  # ''
    smart: bool  # False
    playlistType: str  # 'audio'
    composite: str  # '/playlists/109486/composite/1755201015'
    duration: int  # 9145000
    leafCount: int  # 21
    addedAt: int  # 1754943684
    updatedAt: int  # 1755201015
