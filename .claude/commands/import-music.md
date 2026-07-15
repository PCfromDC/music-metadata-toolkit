# Import Music Command

Import ALBUMS from an external source (e.g. an iTunes Music backup) into the music
library, de-duplicating by AUDIO QUALITY. Calls the Python service
(`python cli.py import`), which handles the copy + quality comparison + naming +
enrichment. Does NOT reimplement any of that logic.

## Usage

```
/import-music [source]
```

If `source` is omitted, use `import.itunes_source` from `music-config.yaml`
(default `//your-nas/backups/iTunes/Music`). The library root comes from
`library.root` in the config; pass `--dest` if that is a placeholder.

## Examples

```
/import-music
/import-music //your-nas/backups/iTunes/Music
```

## What it does (rules)

iTunes holds a mix of individual purchased **songs** and full **albums**, so the
unit of import is the **track**:

- **Copy only** - the source (e.g. the iTunes backup) is left completely intact.
- **NEW album** (artist/album not in the library) -> import all of its tracks.
- **EXISTING album** (matches a library album) -> **merge per track**:
  - a source track that matches an existing track and is **higher audio quality**
    **upgrades** that one track (even a single-song source folder upgrades the one
    matching track in a full album);
  - a source track the library album is **missing** is **added**;
  - equal-or-lower-quality tracks are left as-is;
  - a track that is not in the source is **never touched** (no track is ever lost).
- **Audio-quality rank (per track):** lossless (FLAC/ALAC/WAV/AIFF/APE) beats lossy;
  within lossless higher bit-depth x sample-rate wins (24/96 > 16/44.1); within
  lossy the codec-efficiency-adjusted bitrate wins - AAC/Vorbis/Opus are weighted up
  vs MP3, so **AAC 256k ranks >= MP3 320k** (a more-efficient codec is not
  downgraded to a higher-bitrate-but-less-efficient one).
- On a track upgrade, the old track is **deleted only AFTER** the new copy is
  size-verified in place.
- **Duplicate album match** is by MusicBrainz album id (when the tags carry one)
  then normalized `Artist - Album`. Track match within a matched album is by
  disc/track number then normalized title (so it works across `.m4a`/`.mp3`).
- **Enrichment** on each imported/updated album (reuses the existing pipeline;
  fail-soft, and the metadata check is flag-only, it never auto-edits tags):
  - **Covers:** `folder.jpg` from validated embedded art + `sync-covers` so every
    track matches `folder.jpg`.
  - **Metadata (default on):** validate album/artist/year vs MusicBrainz/iTunes and
    a folder-name-matches-metadata check; anything below the auto-approve bar is
    listed as a **review flag** in the report. Skip with `--no-metadata`; skip all
    enrichment with `--no-enrich`.

## Write policy

Never modifies the source. In the library it ADDS new `Artist/Album` folders, ADDS
missing tracks to existing albums, and on a verified quality upgrade replaces the
single lower-quality track. It never deletes a track that is not being upgraded and
never touches an existing higher-or-equal-quality track. Copies use a chunked
read/write loop (NOT `shutil.copy2`, which a Samba NAS rejects on a same-server
share->share copy) with retry on transient SMB drops, and check free space first.

## Workflow (assisted human-gate)

When invoked with an optional source argument: $ARGUMENTS

**Path Normalization:** replace backslashes (`\`) with forward slashes (`/`).

### Step 1: Dry-run to see the plan
```bash
cd "D:\music cleanup" && python cli.py import "<source>" --dest "//your-nas/music" --dry-run
```
This lists each source album with its decision:
`[NEW] Artist - Album  AAC 256k (12 trk)` /
`[MERGE] Artist - Album  +2 upgraded, +1 added  vs existing '...' MP3 192k` /
`[SKIP] Artist - Album  (already current)`. Nothing is copied.

### Step 2: Present + confirm
Summarize the plan: how many NEW albums, how many MERGED (with total tracks
upgraded / added), how many SKIPPED, and the total size. **Call out that a track
upgrade deletes the single old lower-quality track** (after the new one verifies);
no full album or un-replaced track is ever deleted. Get approval before writing.

### Step 3: Execute (after approval)
```bash
cd "D:\music cleanup" && python cli.py import "<source>" --dest "//your-nas/music" --execute
```
Large copies run over the network - expect this to take a while.

### Step 4: Confirm completion
Report per-album results (new / merged / skipped / failed, plus tracks upgraded /
added) and any **review flags** from the metadata check (albums below the
auto-approve bar, folder-name mismatches). Spot-check a few new `Artist/Album/`
folders for the tracks + `folder.jpg` + tags.

## Error handling

Fail-soft per album: a bad album is logged and skipped, never aborting the batch.
Never deletes a source file; never deletes an existing copy that is not being
upgraded; never deletes an old copy until the new one is verified in place.
