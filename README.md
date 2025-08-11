<!-- start intro -->
<p align="center">
    <h1 align="center">plistsync</h1>
</p>

<p align="center">
    <em><b>Toolbox for transferring, converting and matching music collections</b></em>
</p>

<!-- end intro -->


## Features

<!-- start features -->

-   todo

<!-- end features -->


## What works

-   cli command to export plex playlist as m3u:

```bash
plistsync -v plex playlist-as-m3u 108310 -o ./foo.m3u -rw /media/music/clean:/Volumes/music/clean
```

## Next steps:

-   manually sync (overwrite) playlist from plex to traktor
    How to write into traktor?
    -   assume traktor lib is up to date and has a container of all tracks
    -   delete content of old traktor playlist or create new playlist
    -   for each track:
        -   find track id that matches our file (via file path)
        -   insert track into traktor playlist
-   manually sync (overwrite) playlist from traktor to plex

- cleanup:
    - remove all flask routes as we are focusing on the package/cli functionality
    - remove all unused code
    - remove old tests

- tests:
    - create abc collection test to use with all services, migrate test_collections