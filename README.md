<p align="center">
    <h1 align="center">plistsync</h1>
</p>

[![Python checks](https://github.com/metasauce/plistsync/actions/workflows/python.yml/badge.svg?branch=main)](https://github.com/metasauce/plistsync/actions/workflows/python.yml)

<p align="center">
    <em><b>
<!-- start intro -->
Toolbox for transferring, converting and matching music collections
<!-- end intro -->
    </b></em>
</p>


<p align="center">
    <img src="./docs/_static/icon_ven.png" alt="plistsync logo" width="200" align="center">
</p>

## Features

<!-- start features -->

-   Transfer playlists and collections between different music services:
    -   Spotify
    -   Tidal
    -   Plex
    -   Traktor

<!-- end features -->

## What works

- One one playlist transfer from spotify to tidal [notebook](notebook/top100dnb.ipynb)


## Next steps:

-   manually sync (overwrite) playlist from plex to traktor
    How to write into traktor?
    -   assume traktor lib is up to date and has a container of all tracks
    -   delete content of old traktor playlist or create new playlist
    -   for each track:
        -   find track id that matches our file (via file path)
        -   insert track into traktor playlist
-   manually sync (overwrite) playlist from traktor to plex
-   tests:
    -   create abc collection test to use with all services, migrate test_collections

## Developing

```
pip install -e '.[dev]'
cd plistsync
mypy .
```
