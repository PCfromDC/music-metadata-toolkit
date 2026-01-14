# Status Folder

This folder contains progress tracking, session logs, and planning documents for the media library cleanup project.

## Purpose

The `status/` folder serves as the central hub for:
- **Planning documents** - Implementation designs and architecture decisions
- **Processing queues** - Track which artists/movies have been processed
- **Session logs** - Record of all processing activities
- **Checkpoints** - Periodic snapshots for recovery
- **API caches** - Store MusicBrainz and TMDb responses
- **Progress reports** - Weekly summaries and statistics

## Directory Structure

```
status/
├── README.md                           # This file
├── planning/
│   └── 20251217_cleanup_planning.md   # Comprehensive implementation plan
├── music/
│   ├── processing_queue.json          # Artist queue with statuses
│   ├── session_logs/                  # Processing session logs
│   └── checkpoints/                   # Periodic queue snapshots
├── movies/
│   ├── processing_queue.json          # Movie processing state
│   └── tmdb_cache.json                # Cached TMDb API responses
├── cache/
│   └── musicbrainz_cache.json         # Cached MusicBrainz API responses
└── reports/
    └── YYYY-MM-DD_weekly_progress.md  # Weekly progress summaries
```

## File Descriptions

### planning/
Contains design documents and architectural decisions for the project.

**20251217_cleanup_planning.md:**
- Complete implementation plan for scaling music cleanup to 930 artists
- Movie library support design (169 movies with TMDb integration)
- Technical architecture, workflows, and risk mitigation
- Timeline: 11 weeks to completion

### music/
Tracks processing state for the music library (930 artists, 17,274 tracks).

**processing_queue.json:**
- Master queue of all artists with statuses: pending/in_progress/completed/error
- Tracks: artist path, track count, issues found/resolved, processing dates
- Updated after each artist is processed
- Used by `music_queue_manager.py` and `process_music_batch.py`

**session_logs/:**
- Timestamped logs of each processing session
- Format: `YYYYMMDD_session_NNN.log`
- Contains: start/end times, artists processed, errors encountered
- Used for debugging and progress tracking

**checkpoints/:**
- Full queue snapshots taken every 50 artists
- Format: `checkpoint_YYYY-MM-DD_artist_NNN.json`
- Used for recovery if processing is interrupted
- Contains complete queue state at time of checkpoint

### movies/
Tracks processing state for the movie library (169 movies).

**processing_queue.json:**
- Queue of all movies with processing status
- Tracks: movie path, TMDb ID, metadata files created, processing date

**tmdb_cache.json:**
- Cached responses from TMDb API
- Contains: movie searches, detailed metadata, poster/fanart URLs
- Prevents redundant API calls (rate limit: 40 req/10 sec)

### cache/
API response caches to avoid redundant lookups and respect rate limits.

**musicbrainz_cache.json:**
- Cached artist and album lookups from MusicBrainz
- Contains: artist MBIDs, album MBIDs, cover art URLs
- Never expires (metadata doesn't change)
- Rate limit: 1 request per second

### reports/
Human-readable progress summaries and statistics.

**Weekly progress reports:**
- Generated automatically every week
- Format: `YYYYMMDD_weekly_progress.md`
- Contains: artists completed, tracks processed, issues resolved, time invested
- Used for motivation and project tracking

## Usage

### View Current Progress
```bash
# Show queue summary
python utilities/music_queue_manager.py --show-summary

# Display dashboard
python utilities/media_dashboard.py
```

### Review Session Logs
```bash
# View latest session log
cat status/music/session_logs/20251217_session_001.log

# View all logs
ls status/music/session_logs/
```

### Inspect Queue State
```bash
# View full queue JSON
cat status/music/processing_queue.json

# Count completed artists
grep -c "\"status\": \"completed\"" status/music/processing_queue.json
```

### Check Checkpoints
```bash
# List all checkpoints
ls status/music/checkpoints/

# View specific checkpoint
cat status/music/checkpoints/checkpoint_2025-12-20_artist_100.json
```

### Clear Caches (if needed)
```bash
# Remove MusicBrainz cache (will re-lookup on next run)
rm status/cache/musicbrainz_cache.json

# Remove TMDb cache
rm status/movies/tmdb_cache.json
```

## Maintenance

### Backup Strategy
The entire `status/` folder should be backed up regularly:
- Before major processing sessions (e.g., processing 100 artists)
- After completing major milestones (e.g., 50% of library)
- Weekly backups recommended during active processing

### Cleanup Old Files
Session logs and checkpoints accumulate over time. Archive older files periodically:
```bash
# Archive logs older than 30 days
find status/music/session_logs/ -name "*.log" -mtime +30 -exec mv {} archive/ \;

# Keep only recent checkpoints (last 5)
ls -t status/music/checkpoints/*.json | tail -n +6 | xargs rm
```

## Recovery Procedures

### If Processing Fails Mid-Batch
1. Check session log for error details
2. View queue state: `cat status/music/processing_queue.json`
3. Identify failed artist (status = "error" or "in_progress")
4. Reset status manually if needed: `python utilities/music_queue_manager.py --reset-artist "Artist Name"`
5. Resume processing: `python utilities/process_music_batch.py --batch-size 10`

### If Queue JSON is Corrupted
1. Restore from most recent checkpoint: `cp status/music/checkpoints/checkpoint_*.json status/music/processing_queue.json`
2. Verify restoration: `python utilities/music_queue_manager.py --validate-queue`
3. Resume processing from restored state

### If Cache is Corrupted
1. Delete corrupted cache file: `rm status/cache/musicbrainz_cache.json`
2. Cache will rebuild automatically on next API call
3. Note: This will re-fetch data from API (respect rate limits)

## Important Notes

- **Do not manually edit queue JSON files** - Use `music_queue_manager.py` CLI tools
- **Do not delete checkpoints** - They are critical for recovery
- **Session logs are append-only** - Never modify existing logs
- **Caches never expire** - Manual deletion required if refresh needed
- **Weekly reports are auto-generated** - Do not manually create/edit

## Integration with Other Folders

The `status/` folder works alongside:
- **utilities/** - Scripts read/write queue and cache files
- **outputs/** - Generated metadata CSVs and JSONs (separate from status tracking)
- **issues/** - Per-artist issue reports (referenced in queue status)

## Version History

**2025-12-17:** Initial status folder created
- Planning document: 20251217_cleanup_planning.md
- Directory structure established
- README documentation written

---

For questions or issues with the status folder, refer to the main project documentation in `README.md` and `CLAUDE.md`.
