# Clean Music Command

**FULLY AUTONOMOUS** - Clean and validate music metadata for the specified folder path.

## Usage

```
/clean-music <path>
```

## Examples

```
/clean-music /path/to/music/Various Artists
/clean-music /path/to/music/Various Artists/50 Hip Hop Classics
/clean-music /path/to/music
```

## Instructions

When this command is invoked with a path argument: $ARGUMENTS

**Path Normalization (IMPORTANT):**
Replace all backslashes (`\`) with forward slashes (`/`).
- UNC paths: `\\openmediavault\music\...` → `/path/to/music/...`
- Local paths: `D:\music_backup\...` → `D:/music_backup/...`

---

## FULLY AUTONOMOUS WORKFLOW

**This command requires NO user confirmation for any step.**

### Step 1: Run Metadata System
```bash
cd "D:\music cleanup" && python orchestrator/music_metadata_system.py --path "<normalized_path>"
```

### Step 2: Auto-Fix Folder Names (NO PERMISSION NEEDED)
```bash
cd "D:\music cleanup" && python utilities/folder_validator.py "<normalized_path>"
```

This automatically:
- Scans all folders
- Compares folder names to album metadata
- Fixes truncated names
- Applies Windows-safe character substitutions
- Reports all changes made

### Step 3: Auto-Consolidate Multi-Disc Albums (NO PERMISSION NEEDED)
```bash
cd "D:\music cleanup" && python utilities/disc_consolidator.py "<normalized_path>"
```

This automatically:
- Detects multi-disc sets ([Disc 1], [Disc 2], etc.)
- Adds disc prefix to filenames (1-01, 2-01)
- Consolidates into single folder
- Updates discnumber metadata
- Removes empty folders

### Step 4: Auto-Fix Missing Cover Art (NO PERMISSION NEEDED)
If any albums are missing cover art:

1. **Search sources in order**:
   - iTunes API: `https://itunes.apple.com/search?term={album}&media=music&entity=album`
     - Get artworkUrl100, replace "100x100" with "1200x1200"
   - MusicBrainz Cover Art Archive
   - Discogs

2. **Download and embed**:
   - Prefer 600x600 or larger resolution
   - Embed APIC frame into all MP3 tracks
   - Create/update folder.jpg

3. **Report**: source, file size, tracks updated

### Step 5: Verify Cover Art (VISUAL CHECK)

**IMPORTANT**: After cover art processing, verify each album's cover art is correct.

For each album processed:

1. **Read the folder.jpg** using the Read tool to view the image

2. **Visually verify** the cover matches the album:
   - Does visible text match the album/artist name?
   - Does it look like professional album artwork?
   - Is the image quality acceptable?

3. **If cover looks WRONG**:
   - Search iTunes for the correct cover:
     ```bash
     python -c "import requests; r=requests.get('https://itunes.apple.com/search?term=Artist+Album&entity=album'); print([a['artworkUrl100'].replace('100x100','1200x1200') for a in r.json()['results'][:3]])"
     ```
   - Re-embed with correct cover:
     ```bash
     python utilities/embed_cover.py "path/to/album" "correct_url" --force
     ```

4. **Flag suspicious albums** for user review in the summary

**Why this matters**: From Ben Harper cleanup (2026-01-13), we learned embedded art can be technically valid but visually wrong. Size/coverage checks alone are not sufficient.

### Step 6: Generate Summary Report

Report all changes made:
- Albums processed: N
- Folders renamed: N
- Multi-disc sets consolidated: N
- Cover art embedded: N
- Issues remaining: N (if any)

---

## Autonomous Behavior Summary

| Action | Permission Required |
|--------|---------------------|
| Run metadata system | NO |
| Rename folders | NO |
| Consolidate multi-disc | NO |
| Fetch cover art | NO |
| Embed cover art | NO |
| Verify cover art visually | NO |
| Fix incorrect cover art | NO |
| Delete empty folders | NO |

All operations run without prompts or confirmations.

---

## Output Location

Reports saved to: `D:\music cleanup\outputs\`
- `{album}_audit.json` - Per-album detailed report
- `processing_summary.json` - Overall summary

---

## Error Handling

If any step fails:
- Log the error
- Continue with remaining steps
- Include failures in final summary
- Do NOT stop the workflow
