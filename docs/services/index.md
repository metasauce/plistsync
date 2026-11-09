```{eval-rst}
.. meta::
   :description: Overview of the services plistsync can talk to, and what each one supports.
```

# Service overview

A **service** is a music platform, or a source of music on your own computer, that
`plistsync` can work with. Spotify, Tidal and Plex are online platforms with user
accounts, Traktor is a DJ library kept in a file, and `local` is simply a folder of audio
files.

Connecting a service is a one-time job: install its extra, and log in if it needs an
account. Afterwards the same service is available everywhere, in the
[command line](../cli/getting-started.md) and in the
[Python library](../library/getting-started.md).

## What each service supports

Services differ in what they can do. The table below shows which features each one has, so
you can check whether a service fits what you want to do before setting it up.

```{div} capability-table
| Service | Authentication | Playlist editing | Tracks by ID | Tracks by metadata |
| --- | :---: | :---: | :---: | :---: |
| {doc}`Spotify <spotify/index>` | <span class="cap yes">✓</span> | <span class="cap yes">✓</span> | <span class="cap yes">✓</span> | <span class="cap yes">✓</span> |
| {doc}`Tidal <tidal/index>` | <span class="cap yes">✓</span> | <span class="cap yes">✓</span> | <span class="cap yes">✓</span> | <span class="cap no">—</span> |
| {doc}`Plex <plex/index>` | <span class="cap yes">✓</span> | <span class="cap yes">✓</span> | <span class="cap yes">✓</span> | <span class="cap yes">✓</span> |
| {doc}`Traktor <traktor/index>` | <span class="cap no">—</span> | <span class="cap yes">✓</span> | <span class="cap yes">✓</span> | <span class="cap no">—</span> |
| {doc}`Local <local/index>` | <span class="cap no">—</span> | <span class="cap no">—</span> | <span class="cap yes">✓</span> | <span class="cap no">—</span> |
```

_✓ supported · — not available_

### What the columns mean

Authentication
: The service requires you to log in before `plistsync` can use it, usually with the
  account you already have there. See
  {doc}`Authentication <../library/guides/authentication>`.

Playlist editing
: You can list, create, change, and delete playlists on the service, including the tracks
  they contain and the order of those tracks. See {ref}`CLI <cli_playlist_editing>` and
  {doc}`Python <../library/guides/playlists>`.

Tracks by ID
: You can find a track by an identifier instead of by its name. An identifier is a value
  that points at exactly one track, for example an ISRC, a code that identifies a
  recording, or the ID a service uses internally. Some identifiers work across services,
  others only in one place. See {ref}`global identifiers <global_identifiers>` and
  {ref}`local identifiers <local_identifiers>`.

Tracks by metadata
: You can search for a track by what it is called and who made it, meaning its title,
  artist, or album. This helps when you do not have an identifier at hand. See
  {ref}`metadata matching <metadata_lookup>`.

## Sync is different

{doc}`Sync <sync/index>` is implemented as a service, but it is an abstraction layer
over the services above rather than a music source of its own: it has no catalog,
no configuration, and requires no login.

Start with the {doc}`sync service <sync/index>`.
