# How it Works

The sync service is built around one idea: give a group of playlists on different services a **single, service-agnostic source of truth**, and express every update to that source of truth as an operation on a _conflict-free replicated data type_ (CRDT). That way, edits made in one service, or directly in a service's own app, can be merged without a central coordinator and without manual conflict resolution.

## The internal track collection

The heart of a synced playlist is its internal track collection: an ordered list of _track links_. Each track link holds

- the track's **global IDs** as {py:class}`TrackID <plistsync.core.ids.TrackID>` instances (e.g. ISRC, Spotify/Tidal IDs) and **metadata** as an offline, service-agnostic representation, and
- the **set of linked playlists** the track currently appears in, as {py:class}`PlaylistID <plistsync.core.ids.PlaylistID>` instances.

The list of track links is the single source of truth for both _which_ tracks a synced playlist contains and _in which order_. The per-service playlists are nothing but projections of it.

## CRDTs

### Fugue: the track list

Track membership and ordering live in a **Fugue**, a list CRDT from [_The Art of the Fugue_](https://arxiv.org/pdf/2305.00583) (Weidner & Kleppmann), which minimises interleaving of concurrent edits. Every element is addressed by a position encoded over a tree of nodes that are identified by `(replica ID, counter)` pairs, so any two replicas that apply the same set of operations converge to the same list, in the same order.

- _Inserts_ create a new node between two existing positions.
- _Deletes_ mark a node as removed.
- _Moves_ are expressed as a delete plus an insert, so re-orderings from different replicas merge instead of clobbering each other.

### LWW register: the playlist metadata

Name and description live in an op-based **last-writer-wins register**. Each field keeps the value of the operation with the highest version, where versions are ordered Lamport-style by counter first and replica ID as a tie-breaker; concurrent updates therefore converge to the same winner on every replica. The full operation history is retained so replicas merge by replaying the operations they have not seen yet.

Note that the register has no deletion semantics: clearing a description is an explicit write of `None`, while fields a service does not report at all are left untouched.

## Replicas

The synced playlist itself acts as replica `0`. Every linked playlist gets its own replica ID when it is registered, and each replica's _view_ of the collection is the projection of the track list onto the playlists it is linked to. This is what makes it possible to tell _whose_ edit an incoming change is: operations produced by a replica's fork carry that replica's ID, and only changes a replica actually made since its last write are merged back.

## The synchronisation pipeline

`SyncedPlaylist.sync()` runs four phases:

```{mermaid}
flowchart TD
    A[fetch: pull linked playlists from their services] --> B[merge: reconcile changes into the Fugue and info register]
    B --> C[enrich: match tracks to fill in IDs and associations]
    C --> D[push: rewrite all linked playlists from the reconciled collection]
```

| Phase      | What happens                                                                                                                                                                                                                                                                                                                                                                                                              |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **fetch**  | Every linked playlist is re-fetched from its service, picking up changes made outside `plistsync`, e.g. in another app, on a phone, or in a web UI.                                                                                                                                                                                                                                                                       |
| **merge**  | Each playlist's current tracks are diffed against its replica view (compared by the intersection of their IDs) and the difference becomes Fugue insert/delete/move operations applied to the internal collection. Name/description changes become register operations, but only for fields the replica actually changed since its last write, so an unchanged playlist never clobbers a newer value from another replica. |
| **enrich** | Tracks not yet associated with a service's playlist are matched against it, the playlist first and then the service's full library, to fill in global IDs and playlist membership.                                                                                                                                                                                                                                        |
| **push**   | Each linked playlist is rewritten from the reconciled collection: tracks are resolved back to that service (playlist first, then library), and the playlist's tracks and metadata are updated in one edit. A track that cannot be matched in a service has its association to that playlist removed (and a warning is logged) instead of aborting the push.                                                               |

Because merge only ever applies CRDT operations, running `sync()` concurrently from two machines, or interleaving it with edits made directly in a service's UI, converges to the same collection everywhere.

## Persistence

The state of a synced playlist is serialised as a JSON document containing the version, the synced playlist ID, the LWW register operations, the Fugue operations, and a replica → playlist-serial map. The CLI stores one file per synced playlist in the user config directory:

| Platform | Path                                                     |
| -------- | -------------------------------------------------------- |
| Linux    | `~/.config/plistsync/sync/<id>.json`                     |
| macOS    | `~/Library/Application Support/plistsync/sync/<id>.json` |
| Windows  | `%LOCALAPPDATA%\plistsync\sync\<id>.json`                |

```{note}
Because the serialisation includes the full operation history, not just a snapshot, `load_from` restores the exact CRDT state and can keep merging with operations produced later. Loading also requires the services of all linked playlists to be installed and configured, since the playlists are re-resolved from their services.
```
