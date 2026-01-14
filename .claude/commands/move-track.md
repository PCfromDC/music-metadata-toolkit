# Move Track Command

Move a track from one album to another with metadata update.

## Usage

```
/move-track <source_track> <destination_folder>
```

## Examples

```
/move-track "/path/to/music/Various Artists/Natural Acoustic/01 Song.mp3" "/path/to/music/Ben Harper/Welcome to the Cruel World"
```

## Instructions

When this command is invoked with arguments: $ARGUMENTS

**Path Normalization:**
Replace all backslashes (`\`) with forward slashes (`/`).

**Gather Required Information:**

1. **Identify source track** from the first argument
2. **Identify destination folder** from the second argument
3. **Ask for metadata updates** using AskUserQuestion:
   - New album name (required)
   - Album artist (required)
   - Track number (e.g., "5/12")
   - Year/date (optional)
   - Genre (optional)

**Execute the move:**

```bash
cd "D:\music cleanup" && python utilities/track_mover.py "<source>" "<dest>" --album "<album>" --artist "<artist>" --number "<track_number>"
```

**Report the result:**
- Source track path
- Destination path
- Metadata updates applied
- Whether source folder was removed (if empty)

## Workflow

1. **Validate paths** exist
2. **Move the file** to destination
3. **Update metadata**:
   - Album name
   - Album artist
   - Track artist (same as album artist unless specified)
   - Track number
   - Date/year
   - Genre
4. **Clean up**:
   - Check if source folder is now empty
   - Remove empty folder (preserving nothing but .jpg files)

## Use Cases

- **Misplaced tracks**: Move a track that ended up in the wrong compilation
- **Artist extraction**: Move tracks from "Various Artists" to proper artist folders
- **Album reorganization**: Move bonus tracks to deluxe edition folders
