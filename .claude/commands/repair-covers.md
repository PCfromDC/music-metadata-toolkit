# Repair Covers Command

Detect and repair corrupted embedded album art (width=0/height=0, missing, or
undecodable cover art) across a music library.

## Usage

```
/repair-covers <path>
/repair-covers <path> --scan-only
/repair-covers <path> --dry-run
```

## Examples

```
/repair-covers /path/to/music/Various Artists
/repair-covers D:/music/Artist Name --scan-only
```

## Background

The toolkit previously embedded invalid album art that ffprobe (the engine
Jellyfin uses) reports as `width=0, height=0`. This command finds those tracks
using ffprobe ground-truth detection cross-checked against the validated core
pipeline, then re-fetches a real cover and re-embeds it safely.

## Instructions

When this command is invoked with a path argument: $ARGUMENTS

**Path Normalization:**
Replace all backslashes (`\`) with forward slashes (`/`).

**Execute the repair workflow (FULLY AUTONOMOUS - no permission needed):**

1. **Scan for corrupted album art** (report only):
   ```bash
   cd "D:\music cleanup" && python cli.py repair-covers "<normalized_path>" --scan-only
   ```

2. **Review flagged albums.** Each flagged track is one of:
   - **corrupt**: ffprobe reports a cover stream with non-positive dimensions,
     or the embedded bytes fail to decode.
   - **missing**: no embedded cover bytes at all.

3. **Repair all flagged albums** (no confirmation needed):
   ```bash
   cd "D:\music cleanup" && python cli.py repair-covers "<normalized_path>"
   ```
   For each flagged album this:
   - Reads album/artist from track metadata.
   - Fetches a validated cover (iTunes -> MusicBrainz Cover Art Archive -> Discogs).
   - Backs up every audio file to a sibling `backups/` folder (MANDATORY).
   - Re-embeds through the validated core pipeline so the post-write ffprobe
     read-back proves real dimensions.

4. **Report summary**:
   - Album folders scanned: N
   - Albums needing repair: N
   - Albums repaired: N
   - Tracks re-embedded: N
   - Albums skipped (no cover found): N
   - Albums failed: N

## Flags

| Flag | Effect |
|------|--------|
| `--scan-only` | Detect and report corrupted albums; make no changes. |
| `--dry-run` | Detect, read metadata, and show the repair plan; make no changes. |

## Autonomous Behavior

This command runs **fully autonomously**:
- No permission prompts for re-embedding cover art.
- Every audio file is backed up before modification.
- All cover bytes pass through the validated core pipeline; invalid art is
  never embedded.
- Rate limits, missing API keys, and "no result" leave files untouched, log,
  and continue. A single album never crashes the batch.

## Safety

- **Backups**: the first run copies pristine tracks to `<album>/backups/` and
  never overwrites an existing backup.
- **Validation**: detection and re-embed both use `utilities/core/cover_art.py`;
  bytes are never embedded without `validate_image` passing and ffprobe
  confirming real dimensions on read-back.
