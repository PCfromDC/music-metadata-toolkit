# Consolidate Multi-Disc Albums Command

Consolidate separate disc folders into a single album folder with `{disc}-{track}` filename format.

## Usage

```
/consolidate-discs <parent_path> <album_name>
```

## Examples

```
/consolidate-discs /path/to/music/Various Artists "70's Disco Ball Party Pack"
/consolidate-discs /path/to/music/Various Artists "Greatest Hits"
```

## Instructions

When this command is invoked with arguments: $ARGUMENTS

The arguments should be: `<parent_path>` `<album_name>`

Execute the multi-disc consolidation workflow:

1. **Preview the consolidation** first:
   ```bash
   cd "D:\music cleanup" && python utilities/consolidate_discs.py --preview $ARGUMENTS
   ```

2. **Show the user** what will happen:
   - Source disc folders found
   - New filename format: `{disc}-{track} Title.mp3`
   - Target folder location

3. **Ask for confirmation** before executing

4. **Execute the consolidation**:
   ```bash
   cd "D:\music cleanup" && python utilities/consolidate_discs.py --consolidate $ARGUMENTS
   ```

5. **Verify the results**:
   - List the new consolidated folder
   - Confirm disc metadata was updated
   - Remind user to delete original folders after verification

## Output Format

Files will be renamed from:
- `Album Disc 1/01 Track.mp3`
- `Album Disc 2/01 Track.mp3`

To:
- `Album/1-01 Track.mp3`
- `Album/2-01 Track.mp3`

## Metadata Updates

The utility also updates:
- `discnumber` tag: Set to disc number (e.g., "1/2", "2/2")
- Files are copied (not moved) for safety
- Original folders preserved until manual deletion
