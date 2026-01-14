# Suggest Fixes Command

Proactively scan for potential issues and suggest fixes based on learned patterns and knowledge base.

## Usage

```
/suggest-fixes <path>
```

## Examples

```
/suggest-fixes /path/to/music/Ben Harper
/suggest-fixes /path/to/music/Various Artists
```

## Instructions

When this command is invoked with a path argument: $ARGUMENTS

**Path Normalization:**
Replace all backslashes (`\`) with forward slashes (`/`).

### Step 1: Load Knowledge Base

Read the knowledge base files:
1. `D:\music cleanup\.claude\knowledge\corrections.json` - Previous corrections
2. `D:\music cleanup\.claude\knowledge\cover_art_mapping.json` - Known correct covers
3. `D:\music cleanup\.claude\knowledge\patterns.json` - Learned patterns

### Step 2: Scan Albums

For each album folder in the path:
1. Get folder name and basic metadata
2. Check for folder.jpg existence
3. Extract embedded cover art hash (if any)

### Step 3: Check Against Knowledge Base

For each album, check:

**Known Corrections:**
- Does this album match a previous correction in `corrections.json`?
- Has it been fixed since the logged correction?

**Cover Art Mapping:**
- Is this album in `cover_art_mapping.json`?
- Does current cover match the known correct URL/hash?

**Pattern Matching:**
- Does album match any pattern in `patterns.json`?
- Calculate confidence for each matched pattern

### Step 4: Generate Suggestions

Create a prioritized list of suggestions:

```markdown
## Suggested Fixes for [path]

### High Priority
| Album | Issue | Confidence | Suggested Fix |
|-------|-------|------------|---------------|
| ... | ... | ... | ... |

### Medium Priority
| Album | Issue | Confidence | Suggested Fix |
|-------|-------|------------|---------------|
| ... | ... | ... | ... |

### Low Priority
| Album | Issue | Confidence | Suggested Fix |
|-------|-------|------------|---------------|
| ... | ... | ... | ... |

### Commands to Apply Fixes
```bash
# Fix [Album 1]
python utilities/embed_cover.py "path" "url" --force

# Fix [Album 2]
...
```
```

### Step 5: Offer to Apply

For high-confidence suggestions (>90%), offer to apply automatically:
- Ask: "Would you like me to apply the high-priority fixes?"
- If yes, execute the fix commands

## Pattern Detection Logic

### wrong_embedded_cover
```python
# Check if cover exists but may be wrong
if has_cover and cover_size > 50000:
    # Search iTunes for this album
    # Compare hashes
    # If different, flag as potential issue
```

### truncated_folder_name
```python
# Check for truncation
if len(folder_name) > 50 and (folder_name.endswith('...') or looks_truncated):
    # Compare to track metadata album name
    # If metadata is longer, suggest rename
```

### missing_folder_jpg
```python
# Check for missing folder.jpg
if not folder_jpg_exists and has_embedded_cover:
    # Suggest syncing folder.jpg from embedded art
```

## Example Output

```
## Suggested Fixes for /path/to/music/Ben Harper

Scanned 4 albums. Found 2 potential issues.

### High Priority

| Album | Issue | Confidence | Suggested Fix |
|-------|-------|------------|---------------|
| Welcome to the Cruel World | Missing folder.jpg | 100% | Sync from embedded art |

### Medium Priority

| Album | Issue | Confidence | Suggested Fix |
|-------|-------|------------|---------------|
| (none) | | | |

### Low Priority

| Album | Issue | Confidence | Suggested Fix |
|-------|-------|------------|---------------|
| (none) | | | |

### Commands to Apply Fixes

```bash
# Sync folder.jpg for Welcome to the Cruel World
python utilities/embed_cover.py "/path/to/music/Ben Harper/Welcome to the Cruel World" --sync-folder
```

Would you like me to apply these fixes?
```

## Knowledge Base Updates

After applying fixes, update the knowledge base:
1. Log the correction in `corrections.json`
2. Add verified cover URLs to `cover_art_mapping.json`
3. Update pattern confidence based on results

## Autonomous Behavior

This command is **interactive**:
- Scans and analyzes autonomously
- Presents suggestions for review
- Asks before applying fixes
- Updates knowledge base after successful fixes
