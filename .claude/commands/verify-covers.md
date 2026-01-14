# Verify Covers Command

Visually verify that folder.jpg files match their album names.

## Usage

```
/verify-covers <path>
```

## Examples

```
/verify-covers /path/to/music/Ben Harper
/verify-covers /path/to/music/Various Artists
```

## Instructions

When this command is invoked with a path argument: $ARGUMENTS

**Path Normalization:**
Replace all backslashes (`\`) with forward slashes (`/`).

**Execute the verification workflow:**

1. **Find all folder.jpg files** in the path:
   - Recursively scan for `folder.jpg` files
   - Note the parent folder name (album name) for each

2. **For each folder.jpg found:**
   - Read the image file using the Read tool
   - Visually examine the cover art
   - Compare against the folder name (album name)

3. **Evaluate each cover:**
   - Does the image look like album cover art?
   - Does any visible text match the album/artist name?
   - Is the image quality acceptable (not blurry, corrupted, watermarked)?

4. **Report findings:**

   | Status | Album | Notes |
   |--------|-------|-------|
   | ✓ | Album Name | Cover matches |
   | ⚠ | Album Name | Text doesn't match / suspicious |
   | ✗ | Album Name | Clearly wrong cover |

5. **For flagged albums**, provide fix commands:
   ```bash
   # Search iTunes for correct cover
   python -c "import requests; r=requests.get('https://itunes.apple.com/search?term=Artist+Album&entity=album'); print([a['artworkUrl100'].replace('100x100','1200x1200') for a in r.json()['results'][:3]])"

   # Embed correct cover
   python utilities/embed_cover.py "path/to/album" "correct_url" --force
   ```

## Verification Criteria

**CORRECT (✓):**
- Album/artist name visible and matches folder name
- Professional album artwork appearance
- Good image quality

**SUSPICIOUS (⚠):**
- No text visible to verify
- Generic image that could be any album
- Low resolution or quality issues

**WRONG (✗):**
- Different album/artist name visible
- Clearly incorrect imagery
- Corrupted or placeholder image

## Why This Matters

From the Ben Harper cleanup session (2026-01-13), we learned that embedded cover art can be technically valid (good size, full coverage) but visually WRONG for the album. This command catches those cases through visual inspection.
