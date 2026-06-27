# Consolidate All Multi-Disc Albums Command

Find and consolidate all multi-disc album sets into single folders.

## Usage

```
/consolidate-all <path>
```

## Examples

```
/consolidate-all /path/to/music/Various Artists
/consolidate-all D:/music/Artist Name
```

## Instructions

When this command is invoked with a path argument: $ARGUMENTS

**Path Normalization:**
Replace all backslashes (`\`) with forward slashes (`/`).

**Execute the consolidation workflow (FULLY AUTONOMOUS - no permission needed):**

1. **Detect multi-disc sets** in the path:
   ```bash
   cd "D:\music cleanup" && python utilities/disc_consolidator.py "<normalized_path>" --scan-only
   ```

2. **Review detected sets**:
   - Pattern: `[Disc N]`, `Disc N`, `CD N`
   - Only consolidate sets with 2+ discs
   - Show: Album name, disc count, track counts

3. **Consolidate all sets** (no confirmation needed):
   ```bash
   cd "D:\music cleanup" && python utilities/disc_consolidator.py "<normalized_path>"
   ```

4. **Report summary**:
   - Multi-disc sets found: N
   - Consolidated: N
   - Errors: N

## Autonomous Behavior

This command runs **fully autonomously**:
- No permission prompts
- Automatically renames files with disc prefix (1-01, 2-01)
- Automatically updates discnumber metadata
- Automatically removes empty source folders
- Preserves folder.jpg in target folder

## Consolidation Process

For each multi-disc set:

1. **Create target folder** (base album name without disc indicator)
2. **Process each disc**:
   - Add disc prefix to filenames: `01 Track.mp3` → `1-01 Track.mp3`
   - Move files to target folder
   - Update metadata:
     - `album`: Base album name
     - `discnumber`: `1/N`, `2/N`, etc.
3. **Clean up**:
   - Move folder.jpg to target (if not present)
   - Delete empty source folders

## Detected Patterns

| Pattern | Example |
|---------|---------|
| Bracket | `Album [Disc 1]`, `Album [CD 1]` |
| Paren | `Album (Disc 1)`, `Album (CD 1)` |
| Suffix | `Album Disc 1`, `Album Disk 1` |
| Suffix CD | `Album CD1`, `Album CD 1` |
| Dash | `Album - Disc 1`, `Album - CD 1` |
