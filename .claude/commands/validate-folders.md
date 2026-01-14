# Validate Folders Command

Scan and auto-fix folder names that don't match album metadata.

## Usage

```
/validate-folders <path>
```

## Examples

```
/validate-folders /path/to/music/Various Artists
/validate-folders D:/music/Artist Name
```

## Instructions

When this command is invoked with a path argument: $ARGUMENTS

**Path Normalization:**
Replace all backslashes (`\`) with forward slashes (`/`).

**Execute the validation workflow (FULLY AUTONOMOUS - no permission needed):**

1. **Scan all folders** in the path:
   ```bash
   cd "D:\music cleanup" && python utilities/folder_validator.py "<normalized_path>" --scan-only
   ```

2. **Review the issues found** and categorize them:
   - **Truncated**: Folder name is shorter than metadata (cut off)
   - **Substitution**: Character differences (_, café vs cafe, etc.)
   - **Multi-disc**: Contains disc indicators (skip - use /consolidate-all)
   - **Mismatch**: General name mismatch

3. **Auto-fix all issues** (no confirmation needed):
   ```bash
   cd "D:\music cleanup" && python utilities/folder_validator.py "<normalized_path>"
   ```

4. **Report summary**:
   - Folders scanned: N
   - Issues found: N
   - Fixed: N
   - Skipped: N (multi-disc albums)

## Autonomous Behavior

This command runs **fully autonomously**:
- No permission prompts for renames
- No confirmation dialogs
- Automatically applies Windows-safe transformations
- Skips multi-disc albums (handled by /consolidate-all)

## What Gets Fixed

| Issue Type | Example | Fix Applied |
|------------|---------|-------------|
| Truncated | `Album - Long Na...` → `Album - Long Name Complete` | Use full metadata name |
| Underscore | `Album_ Subtitle` → `Album - Subtitle` | Replace `_` with ` -` |
| Accent | `Café Music` → `Cafe Music` | Normalize to ASCII |
| Colon | `Album: Part 2` → `Album - Part 2` | Windows-safe substitution |
