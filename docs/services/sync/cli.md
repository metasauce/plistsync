# CLI

The sync workflow is available as `plistsync sync` commands, for interactive use and scripting. This page walks through each command; if you are new to synced playlists, start with [Getting started](getting-started).

All commands below identify a synced playlist by its _name_ or its _ID_. Names are convenient but not guaranteed to be unique, so when in doubt (or when two playlists share a name) use the ID.

## Create a synced playlist

```bash
plistsync sync create "My Mix" -d "The tracks we both like"
```

This creates a new synced playlist with a unique ID and stores it locally:

```text
Created synced playlist My Mix
  ID:   1f4d7e2c-8a51-4b0e-9f3d-2c6a9b4e7f10
```

```{note}
The synced playlist is saved as a JSON file in your user config directory (`~/.config/plistsync/sync/` on Linux). Pass `-j`/`--json` to get the result, including the file path, as machine-readable JSON for scripting.
```

## Link playlists

Register "real" playlists from your services as replicas of the synced playlist. The playlist argument accepts a URL, URI, serial, or raw ID; the owning service is detected automatically:

```bash
plistsync sync register "My Mix" "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
plistsync sync register "My Mix" "https://tidal.com/playlist/..."
```

Registration is a full round-trip: the playlist's tracks are merged into the internal collection, and the internal state is pushed back to the linked playlist. From the very first `register` on, the linked playlist already mirrors the synced playlist, including its name and description. Pass `-j`/`--json` for the result as JSON.

```{note}
If several services could parse the identifier, `register` fails and asks for the full URL or URI to disambiguate. If none can parse it, the command fails and asks for a valid URL, URI, serial, or raw ID; this also happens when the owning service could not be loaded, for example because its dependencies are missing.
```

## Inspect

```bash
plistsync sync list
```

lists all synced playlists with their descriptions and number of linked playlists:

```text
Synced playlists
  Name    Description             Registered Plists  ID
  My Mix  The tracks we both like                 2  1f4d7e2c-...
```

Pass `-j`/`--json` for the same data as JSON.

while

```bash
plistsync sync show "My Mix"
```

prints a per-track matrix with one column per linked playlist, marking where each track is present:

```text
                Synced playlist: My Mix (ID: 1f4d7e2c-...)
  Title      Artist        spotify     tidal
 ───────────────────────────────────────────────
  Song A     Artist A          ✓         ✗
  Song B     Artist B          ✓         ✓
```

A ✗ marks drift: the track is missing from that service and will be added on the next synchronisation, if it can be matched there.

## Run the synchronisation

```bash
plistsync sync run "My Mix"
```

pulls every linked playlist, merges external changes (tracks added, removed, or reordered in one service show up in the others), and pushes the result back to all linked playlists. Pass several names/IDs to synchronise a subset, or omit the argument to synchronise every synced playlist at once:

```bash
plistsync sync run "My Mix" "Holiday Hits"
plistsync sync run
```

```{note}
Because `run` only applies CRDT operations, running it from two machines, or interleaving it with edits made directly in a service's app, converges to the same collection everywhere instead of conflicting.
```

## Remove

```bash
plistsync sync remove "My Mix"
```

removes the synced playlist and its stored state. You are prompted for confirmation; use `-y`/`--confirm` to skip the prompt. The linked playlists on your services are left untouched; only the synced playlist's bookkeeping is deleted. Pass `-j`/`--json` for the result as JSON.

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
