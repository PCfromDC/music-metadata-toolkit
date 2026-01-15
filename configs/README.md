# Configuration Files

This folder contains YAML configuration files for batch operations and API credentials.

## Folder Structure

```
configs/
├── README.md           # This file
├── templates/          # Configuration templates (copy to active/)
│   ├── batch_rename.yaml
│   ├── consolidation.yaml
│   ├── credentials.yaml.example
│   └── move_tracks.yaml
└── active/             # Your active configurations (gitignored)
    └── .gitkeep
```

## Usage

1. Copy a template from `templates/` to `active/`
2. Customize for your needs
3. Run the corresponding utility

```bash
# Example: Batch rename folders
cp configs/templates/batch_rename.yaml configs/active/my_renames.yaml
# Edit my_renames.yaml with your folder mappings
python utilities/process_batch_rename.py configs/active/my_renames.yaml
```

## Template Files

### credentials.yaml.example

API credentials for external services. Copy to `active/credentials.yaml` and fill in your keys.

| Service | Required | Purpose |
|---------|----------|---------|
| AcoustID | Optional | Audio fingerprinting for track identification |
| Discogs | Optional | Rare releases and detailed credits |
| MusicBrainz | No key | Just needs user agent string |
| iTunes | No key | Cover art and basic metadata |

**Setup:**
```bash
cp configs/templates/credentials.yaml.example configs/active/credentials.yaml
# Edit with your API keys
```

### batch_rename.yaml

Batch folder renaming operations.

```yaml
base_path: "/path/to/music/Various Artists"
renames:
  - from: "Old Folder Name"
    to: "New Folder Name"
```

### consolidation.yaml

Multi-disc album consolidation configuration.

```yaml
base_path: "/path/to/music/Various Artists"
consolidations:
  - source_folders:
      - "Album Name [Disc 1]"
      - "Album Name [Disc 2]"
    target_folder: "Album Name"
    metadata:
      album: "Album Name"
      albumartist: "Various Artists"
```

### move_tracks.yaml

Track movement between albums with metadata updates.

```yaml
moves:
  - source: "/path/to/track.mp3"
    dest_folder: "/path/to/destination/album"
    metadata:
      album: "Destination Album"
      albumartist: "Artist Name"
      tracknumber: "5/12"
```

## Security Notes

- **Never commit** files in `active/` - they may contain API keys or local paths
- The `active/` folder is gitignored by default
- `credentials.yaml.example` contains placeholder values only
