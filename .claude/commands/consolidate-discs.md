# Consolidate Multi-Disc Albums Command

Consolidate separate disc folders into a single album folder with a disc-prefixed
(`{disc}-{track}`) filename format. This uses the canonical `disc_consolidator.py`
tool (the same engine behind `/consolidate-all` and `python cli.py consolidate`).

## Usage

```
/consolidate-discs <parent_path> [--album "Album Name"]
```

## Examples

```
/consolidate-discs /path/to/music/Various Artists
/consolidate-discs /path/to/music/Various Artists --album "70's Disco Ball Party Pack"
```

## Instructions

When this command is invoked with arguments: $ARGUMENTS

The first argument is `<parent_path>`. Optionally pass `--album "Album Name"` to
consolidate a single set instead of all detected sets.

Execute the multi-disc consolidation workflow:

1. **Preview the consolidation** first with `--dry-run`:
   ```bash
   cd "D:\music cleanup" && python utilities/disc_consolidator.py "<parent_path>" --dry-run
   ```

2. **Show the user** what will happen:
   - Source disc folders detected (and any orphaned discs)
   - New filename format: `{disc}-{track} Title.mp3`
   - Target folder location (the base album name)

3. **Execute the consolidation**:
   ```bash
   # All detected sets:
   cd "D:\music cleanup" && python utilities/disc_consolidator.py "<parent_path>"

   # A single set:
   cd "D:\music cleanup" && python utilities/disc_consolidator.py "<parent_path>" --album "Album Name"
   ```

4. **Verify the results**:
   - List the new consolidated folder
   - Confirm `discnumber` metadata was updated

## Output Format

Files are renamed from:
- `Album Disc 1/01 Track.mp3`
- `Album Disc 2/01 Track.mp3`

To:
- `Album/1-01 Track.mp3`
- `Album/2-01 Track.mp3`

## Metadata Updates

The tool also updates:
- `discnumber` tag: set to `disc/total` (e.g. "1/2", "2/2"); M4A uses the disk tuple
- Per-disc track numbers are preserved (not renumbered across discs)
- Cover art (folder.jpg / cover.jpg / album.jpg / front.jpg) is carried over
- Empty source folders are removed after their tracks move
