# CLI

The sync workflow is available as `plistsync sync` commands, for interactive use and scripting. This page walks through each command; if you are new to synced playlists, start with [Getting started](getting-started).

All commands below identify a SyncedPlaylist by its _name_ or its _ID_. Names are convenient but not guaranteed to be unique, so when in doubt (or when two playlists share a name) use the ID.

## Create a SyncedPlaylist

```bash
plistsync sync create "My Mix" --description "The tracks we both like"
```

This creates a new SyncedPlaylist with a unique ID and stores it locally:

```text
Created synced playlist My Mix
  ID:   1f4d7e2c-8a51-4b0e-9f3d-2c6a9b4e7f10
```

```{note}
The SyncedPlaylist is saved as a JSON file in your user config directory (`~/.config/plistsync/sync/` on Linux). Pass `-j`/`--json` to get the result, including the file path, as machine-readable JSON for scripting.
```

## Link playlists

Register "real" playlists from your services as replicas of the SyncedPlaylist. The playlist argument accepts a URL, URI, serial, or raw ID; the owning service is detected automatically:

```bash
plistsync sync register "My Mix" "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
plistsync sync register "[Name]" "[ID, URL, etc ...]"
```

Registration is a full round-trip: the service playlist's tracks are merged into the SyncedPlaylist, and the updated track list is pushed back to the linked playlist.
After the first `register`, the linked playlist already mirrors the SyncedPlaylist, including its name and description.

If several services could parse a given ID-argument, `register` will ask you for the full URL to pick the right service.

```{warning}
Registering service playlists to a SyncedPlaylist will immediately sync them.
This will likely change their tracks, name, and description.

Your music apps (tidal \*cough\*) might need a restart/reload to show the changes.
```

## Inspect

```bash
plistsync sync list
```

will list all SyncedPlaylists with their descriptions and number of linked playlists:

```text
Synced playlists
  Name    Description             Registered Plists  ID
  My Mix  The tracks we both like                 2  1f4d7e2c-...
```

Pass `-j`/`--json` for the same data as JSON.


```bash
plistsync sync show "My Mix"
```

will print a per-track matrix with one column per linked playlist, marking where each track is present:

```text
                Synced playlist: My Mix (ID: 1f4d7e2c-...)
  Title      Artist        spotify     tidal
 ───────────────────────────────────────────────
  Song A     Artist A          ✓         ✗
  Song B     Artist B          ✓         ✓
```

An ✗ marks drift: the track is missing from that service and will be added on the next synchronisation, if it can be matched there.

## Run the synchronisation

```bash
plistsync sync run "My Mix"
```

pulls every linked playlist, merges external changes (tracks added, removed, or reordered in one service show up in the others), and pushes the result back to all linked playlists.
Pass several names/IDs to synchronise a subset, or omit the argument to synchronise all SyncedPlaylists you have set up:

```bash
plistsync sync run "My Mix" "Holiday Hits"
plistsync sync run
```

```{admonition} Nerd-fact 🤓
The `run` command applies CRDT operations.
Calling it from two machines, or interleaving it with edits made directly in a service's app, converges to the same collection everywhere instead of conflicting.
```

## Remove

```bash
plistsync sync remove "My Mix"
```

removes the SyncedPlaylist and its stored state.
You are prompted for confirmation.
The linked playlists on your services are left untouched.
Only the bookkeeping for the SyncedPlaylist is deleted from the local disk.

## Full command reference

<div class="only-light">

```{typer} plistsync.cli.commands.sync:sync_app
---
prog: plistsync sync
theme: light
width: 80
---
```

</div>

<div class="only-dark">

```{typer} plistsync.cli.commands.sync:sync_app
---
prog: plistsync sync
theme: dark
width: 80
---
```

</div>
