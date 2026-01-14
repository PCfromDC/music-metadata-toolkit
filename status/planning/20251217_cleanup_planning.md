# Media Library Cleanup Expansion Plan
**Date:** 2025-12-17
**Status:** Planning Phase
**Version:** 1.0

## Executive Summary

This document outlines the plan to scale the music metadata cleanup project from a single-artist focus (U2: 261 tracks) to handle the entire music library (930 artists, 17,274 tracks) and add movie library support (169 movies). The project will eventually be renamed to "media cleanup" to reflect its expanded scope.

**Strategy:** Maintain the proven semi-automated workflow from the U2 cleanup while adding batch orchestration, progress tracking, external API integration (MusicBrainz, TMDb), and consolidated reporting.

---

## Library Scale Analysis

### Music Library
- **Total Files:** 17,274 audio tracks
- **Total Artists:** 930 artist directories
- **Format Distribution:** 91.8% MP3, 8.2% M4A (plus minor: M4P, WMA, FLAC)
- **Organization:** Hierarchical Artist > Album > Tracks structure
- **Scale Factor:** 66x larger than U2 collection
- **Estimated Size:** 75-100+ GB

### Movie Library
- **Total Files:** 169 video files
- **Format Distribution:** 89.5% M4V, 10.5% MP4
- **Organization:** Flat alphabetical structure by movie title
- **Current State:** NO metadata files present (no NFO, XML, JSON, cover art)
- **Size:** ~240 GB
- **Issues:** Filename inconsistencies, missing years, quality notation variations

### Current State (Baseline)
- ✅ U2 collection: 261 tracks fully cleaned (1.5% of total library)
- ✅ Proven workflow: extract → review → fix → verify
- ✅ Tools: 4 Python utilities supporting MP3/M4A/FLAC
- ✅ Documentation: README.md, CLAUDE.md, issue tracking system

---

## Implementation Strategy

### Phase 1: Music Library Expansion (Weeks 1-8)

#### Week 1: Infrastructure Setup
**Goal:** Build queue management and progress tracking foundation

**Deliverables:**
1. **Status folder structure** (COMPLETED)
   ```
   status/
   ├── planning/20251217_cleanup_planning.md
   ├── music/
   │   ├── processing_queue.json
   │   ├── session_logs/
   │   └── checkpoints/
   ├── movies/
   ├── cache/
   └── reports/
   ```

2. **Queue Management System** (`utilities/music_queue_manager.py`)
   - Scan /path/to/music for all 930 artists
   - Initialize processing queue with statuses: pending/in_progress/completed/error
   - CRUD operations: create, read, update queue state
   - Summary statistics: completed count, pending count, progress percentage
   - Mark U2 as completed (carry over existing work)

3. **Progress Dashboard** (`utilities/media_dashboard.py`)
   - Real-time CLI visualization of library processing status
   - Show: total artists, completed %, tracks processed, issues found/fixed
   - Estimated time remaining based on processing rate
   - Separate music and movie sections

**Success Criteria:** Queue system operational, U2 marked complete, 929 artists pending

#### Week 2: Single-Artist Automation
**Goal:** Automated workflow for processing individual artists

**Deliverables:**
1. **MusicBrainz API Integration** (`utilities/musicbrainz_lookup.py`)
   - Artist lookup by name → MusicBrainz artist ID
   - Album lookup by artist + album → release ID + cover art URL
   - Cover art download from Cover Art Archive
   - Rate limiting: 1 request/second (MusicBrainz policy)
   - Caching: `status/cache/musicbrainz_cache.json` to avoid re-lookups

2. **Single-Artist Processor** (`utilities/process_artist.py`)
   - Wrapper around extract_metadata.py with intelligence layer
   - Workflow:
     1. Extract metadata for all tracks
     2. Analyze for simple issues (auto-fixable)
     3. Analyze for complex issues (manual review)
     4. Auto-fix simple issues (if enabled)
     5. Generate issue report in issues/{artist}_library_issues.md
     6. Update queue status

   **Auto-fixable Issues (Conservative):**
   - Missing cover art → MusicBrainz lookup and embed
   - Genre = "Other" → Infer from artist (e.g., U2 → Rock)
   - Track number format ("01/12" → "1")
   - External cover art file → Embed in audio file

   **Manual Review Required (Too Risky to Auto-Fix):**
   - Title typos (e.g., "Fortuante Son")
   - Artist name variations (collaborations, featuring)
   - Incomplete albums (missing tracks 1-5, 7-10)
   - Duplicate tracks across albums

3. **Modify extract_metadata.py**
   - Add argparse: `python extract_metadata.py <artist_path> --output-name <custom> --quiet --json-only`
   - Return exit codes: 0=success, 1=error
   - Parameterize output filenames for automation
   - Quiet mode: suppress console output except errors

**Success Criteria:** Process 10 test artists end-to-end with auto-fixes + manual review queue

#### Week 3: Batch Orchestration
**Goal:** Batch processing with aggregated reporting

**Deliverables:**
1. **Batch Orchestrator** (`utilities/process_music_batch.py`)
   - Process N artists from queue (default: 10)
   - For each artist:
     - Get next pending from queue
     - Run process_artist.py
     - Update queue status
     - Log session activity
   - Aggregate manual review items across all processed artists
   - Generate batch summary report
   - Create checkpoint every 50 artists

   **User Workflow:**
   ```bash
   # Process 10 artists
   python utilities/process_music_batch.py --batch-size 10

   # Output:
   # Processing 10 artists...
   # [1/10] The Beatles: 215 tracks, 3 auto-fixes, 2 manual reviews
   # [2/10] Radiohead: 180 tracks, 5 auto-fixes, 0 manual reviews
   # ...
   # BATCH COMPLETE: 10/930 artists (1.1%)
   # Auto-fixed: 27 issues
   # Manual review needed: 8 issues (see outputs/manual_review_needed.json)

   # Review and fix flagged issues
   cat outputs/manual_review_needed.json
   python utilities/fix_metadata.py title "path/to/track.mp3" "Correct Title"

   # Continue
   python utilities/process_music_batch.py --batch-size 10
   ```

2. **Enhance Existing Utilities**

   **batch_fix_metadata.py:**
   - Add M4A support (currently MP3-only)
   - Add fields: album, track number, date (beyond genre)
   - Add `--dry-run` mode: preview changes without applying
   - Add JSON input: read batch fixes from structured file

   **embed_cover.py:**
   - Integrate MusicBrainz: auto-lookup if URL not provided
   - Add batch mode: process multiple albums from JSON list
   - Add `--skip-existing`: don't re-embed if already present

   **fix_metadata.py:**
   - Add M4A format support
   - Add album field support
   - Add CSV batch mode: `python fix_metadata.py --from-csv fixes.csv`

3. **Master Reporting** (`utilities/music_master_report.py`)
   - Aggregate all artist JSONs into single master database
   - Generate library-wide statistics
   - Identify cross-artist issues (duplicates, compilations)
   - Outputs:
     - `outputs/music_library_master.json` - All 17,274 tracks
     - `outputs/music_library_master.csv` - Flat export
     - `outputs/music_library_statistics.json` - Stats (total tracks, albums, genres, issues)
     - `status/reports/{date}_weekly_progress.md` - Human-readable weekly summary

**Success Criteria:** 50-100 artists processed as pilot, documented workflow validated

#### Weeks 4-8: Full Library Scale-Up
**Goal:** Process all 930 artists with ongoing manual review

**Execution:**
- Batch process in groups of 50-100 artists
- Handle manual review queues daily (estimated 10-20 hours total user time)
- Refine auto-fix rules based on edge cases discovered
- Generate weekly progress reports
- Create checkpoints every 100 artists for safety

**Timeline:**
- Per-artist average: 10-15 minutes automated processing
- 930 artists × 12 minutes = 11,160 minutes = **186 hours**
- Realistic: 20-30 hours computer time per week over 6-8 weeks
- User time: 2-3 hours per week reviewing flagged issues

**Success Criteria:** 930/930 artists completed, comprehensive music library database

---

### Phase 2: Movie Library Support (Weeks 9-10)

#### Week 9: Video Metadata Foundation
**Goal:** Extract technical metadata and integrate TMDb API

**Deliverables:**
1. **Video Metadata Extractor** (`utilities/extract_video_metadata.py`)
   - Dependency: `pymediainfo` (install: `pip install pymediainfo`)
   - Extract technical metadata:
     - Video: codec (H.264, HEVC), resolution (1080p, 4K), bitrate, frame rate
     - Audio: codec (AAC, DTS), channels, bitrate
     - Subtitles: embedded subtitle tracks
     - Duration, file size
   - Parse filename for title/year/quality:
     - "Inception (2010) (1080p HD).m4v" → Title: Inception, Year: 2010, Quality: 1080p HD
     - "The Dark Knight.mp4" → Title: The Dark Knight, Year: unknown, Quality: unknown
   - Generate scan report: `outputs/movies_library_scan.csv`

2. **TMDb API Integration** (`utilities/tmdb_lookup.py`)
   - Register for free TMDb API key (https://www.themoviedb.org/settings/api)
   - Implement functions:
     - `search_movie(title, year=None)` → List of matches with confidence scores
     - `get_movie_details(tmdb_id)` → Complete metadata (plot, cast, director, genres, runtime, ratings)
     - `download_poster(tmdb_id, output_path)` → Fetch poster (500x750)
     - `download_fanart(tmdb_id, output_path)` → Fetch backdrop (1920x1080)
   - Rate limiting: 40 requests per 10 seconds (token bucket algorithm)
   - Caching: `status/movies/tmdb_cache.json` for all responses
   - Confidence scoring: Exact title+year match = 100%, fuzzy match = 60-80%

3. **Manual TMDb Matching**
   - For failed auto-matches, generate `outputs/movies_failed_lookups.csv`
   - User manually searches TMDb and provides IDs
   - Tool reads CSV and processes: `python tmdb_lookup.py --from-csv failed_lookups.csv`

**Success Criteria:** Complete movie scan, >95% successful TMDb auto-matches

#### Week 10: Movie Enrichment & Sidecar Generation
**Goal:** Generate metadata files and download artwork for all movies

**Deliverables:**
1. **NFO Generator** (`utilities/generate_nfo.py`)
   - Generate Kodi-compatible NFO XML files
   - Alternative: JSON sidecar files (more flexible, easier to parse)

   **NFO Format (Kodi Standard):**
   ```xml
   <movie>
     <title>Inception</title>
     <originaltitle>Inception</originaltitle>
     <year>2010</year>
     <plot>A thief who steals corporate secrets through dream-sharing technology...</plot>
     <runtime>148</runtime>
     <genre>Action</genre>
     <genre>Sci-Fi</genre>
     <director>Christopher Nolan</director>
     <actor>
       <name>Leonardo DiCaprio</name>
       <role>Dom Cobb</role>
     </actor>
     <tmdbid>27205</tmdbid>
     <imdbid>tt1375666</imdbid>
   </movie>
   ```

   **JSON Format (Alternative):**
   ```json
   {
     "title": "Inception",
     "year": 2010,
     "tmdb_id": 27205,
     "imdb_id": "tt1375666",
     "genres": ["Action", "Sci-Fi", "Thriller"],
     "runtime": 148,
     "plot": "A thief who steals corporate secrets...",
     "director": "Christopher Nolan",
     "cast": [
       {"name": "Leonardo DiCaprio", "role": "Dom Cobb"},
       {"name": "Ellen Page", "role": "Ariadne"}
     ],
     "poster": "Inception-poster.jpg",
     "fanart": "Inception-fanart.jpg",
     "ratings": {"tmdb": 8.3},
     "technical": {
       "resolution": "1080p",
       "codec": "H.264",
       "duration": "2:28:00",
       "file_size": "2.1 GB"
     }
   }
   ```

2. **Movie Orchestrator** (`utilities/process_movies.py`)
   - Complete workflow per movie:
     1. Extract technical metadata (pymediainfo)
     2. Parse filename for title/year
     3. Search TMDb for matches
     4. Present top 3 matches with confidence scores
     5. User confirms or selects correct match (semi-automated)
     6. Download poster + fanart to movie directory
     7. Generate NFO and JSON sidecar files

   **Semi-Automated Workflow:**
   ```bash
   python utilities/process_movies.py --batch-process --confirm-each

   # For each movie:
   # Parsed: "Inception (2010)"
   # TMDb search results:
   #   1. Inception (2010) - Christopher Nolan [MATCH: 100%]
   #   2. Inception (2014) - Indie film [MATCH: 40%]
   # Select match [1-2, 's' to skip]: 1
   #
   # Downloading poster... DONE
   # Downloading fanart... DONE
   # Generating Inception.nfo... DONE
   # Creating Inception-metadata.json... DONE
   #
   # [1/169] Inception - COMPLETE
   ```

3. **Movie Master Report** (`utilities/movie_master_report.py`)
   - Generate consolidated movie library database
   - Outputs:
     - `outputs/movies_library_master.json` - All movies with metadata
     - `outputs/movies_library_master.csv` - Flat export
     - `outputs/movies_failed_lookups.csv` - Failed TMDb matches for manual resolution

**Result:** Each movie directory contains:
```
/path/to/movies/Inception/
├── Inception (2010) (1080p HD).m4v         # Original video file
├── Inception (2010).nfo                    # Kodi metadata
├── Inception (2010)-metadata.json          # Structured metadata
├── Inception (2010)-poster.jpg             # 500x750 poster
└── Inception (2010)-fanart.jpg             # 1920x1080 backdrop
```

**Timeline:**
- Per-movie automated: 10-15 seconds (metadata + downloads)
- Manual confirmations: 20-40 seconds per movie if enabled
- 169 movies × 30 seconds = **85 minutes = 1.5 hours**
- Total with manual review: **2-3 hours**

**Success Criteria:** 169/169 movies with complete metadata, >98% TMDb match success

---

### Phase 3: Project Finalization (Week 11)

#### Tasks
1. **Generate Final Reports**
   - Completion summary: total tracks/movies processed, issues resolved
   - Before/after comparison: metadata completeness, cover art coverage
   - Statistics: most common issues, auto-fix success rate

2. **Update Documentation**
   - **README.md:** Update project scope (music → media), add movie sections, update case study results
   - **CLAUDE.md:** Add comprehensive movie utility documentation, update workflows, add new sections for queue management and batch processing

3. **Project Rename**
   ```bash
   # Rename directory
   mv "D:\music cleanup" "D:\media cleanup"

   # Update all hardcoded paths in Python scripts
   # Use regex: s|D:\\music cleanup|D:\\media cleanup|g

   # Update documentation references
   # README.md, CLAUDE.md: s/Music Library/Media Library/g
   ```

4. **Version Control**
   ```bash
   cd "D:\media cleanup"
   git init
   git add .
   git commit -m "Initial commit: Music + Movie cleanup system"

   # Tag major milestones
   git tag -a v1.0.0 -m "U2 collection cleanup complete"
   git tag -a v2.0.0 -m "Full music library processing complete (930 artists)"
   git tag -a v3.0.0 -m "Movie library support added (169 movies)"
   ```

5. **Archive Session Logs**
   - Keep all session logs in `status/music/session_logs/` and `status/movies/`
   - Preserve checkpoints in case rollback is needed
   - Generate final weekly progress report summarizing entire project

**Success Criteria:** Complete documentation, git repository established, project renamed

---

## Technical Architecture

### Data Flow

#### Music Processing Flow
```
1. User runs: python utilities/process_music_batch.py --batch-size 10
2. Batch orchestrator queries queue: get_next_artist() × 10
3. For each artist:
   a. process_artist.py calls extract_metadata.py → outputs/{artist}_audit.json
   b. Analyze JSON for simple issues (missing cover art, genre="Other")
   c. For simple issues: call musicbrainz_lookup.py → auto-fix
   d. For complex issues: append to manual_review_needed.json
   e. Update queue: update_artist_status(artist, "completed")
4. Generate batch summary report
5. Every 50 artists: create checkpoint snapshot
```

#### Movie Processing Flow
```
1. User runs: python utilities/process_movies.py --batch-process --confirm-each
2. Scan movie library: find all .m4v/.mp4 files
3. For each movie:
   a. extract_video_metadata.py → technical metadata
   b. Parse filename → title, year, quality
   c. tmdb_lookup.py search_movie(title, year) → candidates
   d. Display top matches, user confirms
   e. Download poster + fanart
   f. generate_nfo.py → create NFO and JSON sidecars
4. Generate movie master report
```

### Queue State Management

**Queue JSON Structure:**
```json
{
  "library_path": "/path/to/music",
  "created": "2025-12-17T10:00:00",
  "last_updated": "2025-12-17T15:30:00",
  "artists": {
    "U2": {
      "status": "completed",
      "path": "/path/to/music/U2",
      "track_count": 261,
      "album_count": 20,
      "issues_found": 6,
      "issues_resolved": 6,
      "auto_fixed": 4,
      "manual_reviews": 2,
      "processed_date": "2025-12-16T14:00:00"
    },
    "The Beatles": {
      "status": "in_progress",
      "path": "/path/to/music/The Beatles",
      "track_count": 215,
      "started_date": "2025-12-17T15:25:00"
    },
    "Radiohead": {
      "status": "pending",
      "path": "/path/to/music/Radiohead"
    },
    "AC/DC": {
      "status": "error",
      "path": "/path/to/music/AC_DC",
      "error_message": "File access denied",
      "error_date": "2025-12-17T10:10:45"
    }
  },
  "summary": {
    "total_artists": 930,
    "completed": 1,
    "in_progress": 1,
    "pending": 928,
    "error": 0,
    "completion_percentage": 0.1
  }
}
```

**Status Transitions:**
- `pending` → `in_progress` (when processing starts)
- `in_progress` → `completed` (successful processing)
- `in_progress` → `error` (critical failure)
- `error` → `pending` (after manual fix, user resets status)

### Caching Strategy

**MusicBrainz Cache (`status/cache/musicbrainz_cache.json`):**
```json
{
  "artists": {
    "U2": {
      "mbid": "a3cb23fc-acd3-4ce0-8f36-1e5aa6a18432",
      "name": "U2",
      "cached_date": "2025-12-17T10:00:00"
    }
  },
  "albums": {
    "The Joshua Tree": {
      "mbid": "6b60e42e-8f1f-4d20-8b1f-d7f5a7a5f5d7",
      "artist": "U2",
      "cover_art_url": "https://coverartarchive.org/release/...",
      "cached_date": "2025-12-17T10:05:00"
    }
  }
}
```

**TMDb Cache (`status/movies/tmdb_cache.json`):**
```json
{
  "searches": {
    "Inception|2010": {
      "results": [
        {"id": 27205, "title": "Inception", "year": 2010, "confidence": 100}
      ],
      "cached_date": "2025-12-17T12:00:00"
    }
  },
  "movies": {
    "27205": {
      "title": "Inception",
      "year": 2010,
      "plot": "A thief who steals...",
      "genres": ["Action", "Sci-Fi"],
      "runtime": 148,
      "director": "Christopher Nolan",
      "poster_url": "https://image.tmdb.org/t/p/original/...",
      "cached_date": "2025-12-17T12:01:00"
    }
  }
}
```

**Cache Invalidation:** Never auto-expire (assume metadata doesn't change). Manual cache clear if needed.

---

## Risk Mitigation

### Risk 1: Network Interruptions
**Impact:** Interrupted processing, corrupted queue state
**Likelihood:** Medium (NAS access over network)

**Mitigation:**
- Atomic queue updates: write to temp file, then rename (atomic operation)
- Checkpoint every 50 artists with full queue snapshot
- Resume capability: batch processor checks queue state and continues from last pending
- Session logs: track every operation for manual recovery if needed

### Risk 2: API Rate Limits Exceeded
**Impact:** Processing halted, incomplete metadata, account suspension
**Likelihood:** Medium (MusicBrainz: 1 req/sec, TMDb: 40 req/10 sec)

**Mitigation:**
- Implement rate limiting with delays: MusicBrainz (1 sec), TMDb (token bucket)
- Exponential backoff for API errors (429 status)
- Comprehensive caching: cache ALL responses indefinitely
- Batch processing with delays between artists (natural rate limiting)
- Manual fallback: if API unavailable, generate list for later processing

### Risk 3: Incorrect Auto-Fixes
**Impact:** Corrupted metadata requiring manual reversal
**Likelihood:** Low (conservative auto-fix rules)

**Mitigation:**
- Conservative auto-fix rules: only obvious cases (missing cover art, genre="Other")
- Dry-run mode: test automation rules on 10-20 artists first
- Original metadata preservation: keep JSON snapshots before modifications
- Rollback capability: checkpoints allow restoration to previous state
- Manual review queue: flag uncertain cases for user decision

### Risk 4: Filename Parsing Failures (Movies)
**Impact:** Wrong TMDb matches, incorrect metadata
**Likelihood:** Medium (169 movies, some with non-standard naming)

**Mitigation:**
- Manual confirmation mode: user approves each TMDb match (default for first 50 movies)
- Confidence scoring: display match confidence % (100% = exact, <60% = uncertain)
- Failed lookups CSV: generate list of movies needing manual TMDb ID assignment
- Skip option: user can skip problematic movies and handle later
- Regex pattern testing: validate filename parsing on full list before processing

### Risk 5: User Burnout (Manual Reviews)
**Impact:** Project stalls due to overwhelming review backlog
**Likelihood:** Medium (10-20 hours manual review time for music)

**Mitigation:**
- Batch size control: process 5-50 artists per session (user choice)
- Weekly progress reports: visualize completion % for motivation
- Aggressive auto-fix: minimize manual work by auto-fixing safe issues
- Batch manual fixes: generate CSV of all similar issues for one-time bulk fix
- Spread over time: 2-3 hours per week over 2 months (manageable)

---

## Success Metrics

### Music Library Success Criteria
- [ ] **Completeness:** 930/930 artists processed
- [ ] **Metadata quality:** <1% tracks with missing critical metadata (artist/album/title)
- [ ] **Cover art:** >95% albums with embedded cover art
- [ ] **Genre standardization:** All genres standardized, no "Other" genre
- [ ] **Master database:** Single JSON/CSV with all 17,274 tracks
- [ ] **Progress tracking:** Weekly progress reports for full timeline
- [ ] **Documentation:** Updated README.md and CLAUDE.md

### Movie Library Success Criteria
- [ ] **Completeness:** 169/169 movies processed
- [ ] **TMDb matching:** >98% successful TMDb matches (manual review for failures)
- [ ] **Sidecar files:** All movies with NFO or JSON sidecar files
- [ ] **Artwork:** All movies with poster and fanart downloaded
- [ ] **Master database:** Single CSV with complete movie metadata
- [ ] **Kodi integration:** NFO files successfully imported into Kodi/Jellyfin/Plex

### Project Health Criteria
- [ ] **Error rate:** <5% error rate during processing (artists/movies with failures)
- [ ] **Resume capability:** Checkpoint system tested and working
- [ ] **Session logs:** All processing sessions logged to status/
- [ ] **Documentation:** Complete documentation (README + CLAUDE.md + this plan)
- [ ] **Version control:** Git repository with tagged versions (v1.0, v2.0, v3.0)
- [ ] **Backward compatibility:** U2 audit files preserved as historical reference

---

## Dependencies

### Python Packages
```bash
# Existing (already installed)
pip install mutagen requests

# New for movies
pip install pymediainfo
```

### External APIs
1. **MusicBrainz API**
   - URL: https://musicbrainz.org/doc/MusicBrainz_API
   - Authentication: None required
   - Rate limit: 1 request per second
   - Coverage: Millions of albums with cover art

2. **TMDb API**
   - URL: https://www.themoviedb.org/settings/api
   - Authentication: Free API key required (register account)
   - Rate limit: 40 requests per 10 seconds (free tier)
   - Coverage: Comprehensive movie database with posters/fanart

---

## Estimated Timeline Summary

| Phase | Duration | Description |
|-------|----------|-------------|
| **Setup** | Week 1 | Status infrastructure, queue system, dashboard |
| **Single Artist** | Week 2 | MusicBrainz integration, process_artist.py, test 10 artists |
| **Batch Processing** | Week 3 | Batch orchestrator, enhance existing utilities, pilot 50-100 artists |
| **Music Scale-Up** | Weeks 4-8 | Process all 930 artists (186 hours processing, 10-20 hours manual review) |
| **Movie Foundation** | Week 9 | Video extraction, TMDb integration, test filename parsing |
| **Movie Enrichment** | Week 10 | NFO generation, process all 169 movies (~2-3 hours) |
| **Finalization** | Week 11 | Documentation, project rename, git repository, final reports |

**Total Timeline:** 11 weeks (2.5 months)
**User Time Investment:** 30-50 hours (manual reviews, oversight, testing)
**Computer Processing Time:** 200+ hours (mostly automated, can run overnight)

---

## Open Questions for User

1. **Auto-fix aggressiveness:** Should we be conservative (fewer auto-fixes, more manual reviews) or aggressive (more automation, higher risk)?
   - Current plan: Conservative approach (only obvious fixes)

2. **Movie metadata format:** Prefer NFO files (Kodi standard) or JSON sidecars (more flexible)?
   - Current plan: Generate both (NFO for Kodi, JSON for programmatic access)

3. **Batch size preference:** Process 10, 50, or 100 artists per session?
   - Current plan: Default 10, user configurable

4. **Priority artists:** Should certain artists be processed first (most listened, favorites)?
   - Current plan: Alphabetical order (simplest, no prioritization)

5. **MusicBrainz auto-lookup:** Enable automatic cover art lookup or keep manual URL input?
   - Current plan: Auto-lookup enabled, with manual fallback option

---

## Next Steps (Immediate Actions)

1. ✅ Create status/ folder structure
2. ✅ Write this comprehensive planning document
3. ⏳ Create status/README.md explaining status folder purpose
4. ⏳ Implement utilities/music_queue_manager.py
5. ⏳ Test queue system with 5-10 artists
6. ⏳ Implement utilities/musicbrainz_lookup.py
7. ⏳ Implement utilities/process_artist.py
8. ⏳ Begin Week 1 deliverables

---

## Changelog

**2025-12-17:**
- Initial planning document created
- Library exploration completed (17,274 audio files, 169 movies)
- Architecture designed: queue system, batch processing, API integration
- Timeline estimated: 11 weeks to completion
- Status folder structure created

---

**Document Version:** 1.0
**Last Updated:** 2025-12-17
**Author:** Claude (with user collaboration)
**Status:** Planning Complete → Ready for Implementation
