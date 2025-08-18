# Matching Music Collections

When working across multiple collections finding consistent matches 
for the same track is a core challenge.  
Our toolbox uses a **three-layer matching strategy**:

## 1. Global Unique Identifiers

**Examples:** ISRC, Spotify ID, Tidal ID, MusicBrainz Recording ID

- Unique across services, stable across devices.  
- A match on one machine will always resolve elsewhere.  
- This is the most reliable and fastest form of matching.

## 2. Local Identifiers

**Examples:** file paths, Beets IDs, Plex IDs  

- Strong matching within one library.
- Paths may require prefix rewriting (different mount points).  
- IDs may be library-specific (Beets, Plex).  
- Can produce false positives across libraries.  

## 3. Metadata & Fuzzy Matching

**Examples:** artist, album, track title, duration, AcoustID  

- Used as a **fallback** when no unique IDs are matched.
- Relies on fuzzy string similarity, heuristics, duration checks.  
- Enables cross-library linking even with inconsistent metadata.  