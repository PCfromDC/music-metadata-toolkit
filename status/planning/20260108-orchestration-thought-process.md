# Music Library Orchestration - Design Thought Process

**Date:** 2026-01-08
**Author:** Claude (AI Assistant)
**Context:** Redesigning music cleanup system for professional audio engineer

---

## Starting Point

### User Context
The user is a music producer/audio engineer with:
- 930+ artists in their collection
- 17,274+ tracks
- Network-attached storage (openmediavault)
- Professional requirements for metadata accuracy and presentation

### What We Had
17 standalone Python scripts that worked but required manual coordination:
- `extract_metadata.py` - Good at scanning, outputs JSON/CSV
- `validate_various_artists.py` - MusicBrainz integration working
- `fix_metadata.py` - Mutagen-based fixes working
- `embed_cover.py` - Cover art embedding working

### Core Problems Identified
1. **No orchestration** - Scripts don't talk to each other
2. **No persistence** - Can't resume interrupted sessions
3. **No confidence scoring** - All corrections treated equally
4. **Manual review bottleneck** - Human must coordinate everything
5. **Windows limitations** - Colon restrictions breaking renames

---

## Design Philosophy

### Why Agent-Based Architecture?

I considered three approaches:

1. **Monolithic Script** - One big Python file
   - Pros: Simple, no dependencies between modules
   - Cons: Hard to maintain, can't run partial operations
   - **Rejected**: Doesn't scale, hard to test

2. **Pipeline with Bash** - Chain existing scripts
   - Pros: Reuses existing code, simple orchestration
   - Cons: No state persistence, error handling difficult
   - **Rejected**: Too fragile for professional use

3. **Agent-Based Architecture** - Specialized agents coordinated by orchestrator
   - Pros: Modular, testable, resumable, extensible
   - Cons: More initial setup, more files
   - **Selected**: Best fit for professional requirements

### Key Design Decisions

#### Decision 1: Confidence Scoring System

**Problem:** Not all metadata matches are equal. Some are clearly correct, others need human verification.

**Options Considered:**
- Binary matching (match/no match)
- Three-tier (auto/review/reject)
- Continuous scoring with configurable thresholds

**Choice:** Three-tier with configurable thresholds (95%/70%)

**Reasoning:**
- 95%+ matches are safe to auto-apply (formatting differences only)
- 70-95% need human eyes (could be wrong release)
- Below 70% likely wrong match, shouldn't even offer as option
- Thresholds are configurable for user preference

#### Decision 2: State Persistence Strategy

**Problem:** Operations on 17,000+ tracks can take hours. Need to survive interruptions.

**Options Considered:**
- SQLite database
- JSON files per album
- Single large JSON file

**Choice:** JSON files per album + session state

**Reasoning:**
- JSON is human-readable (can debug without special tools)
- Per-album files allow concurrent access
- Session state tracks overall progress
- Easy to implement, easy to migrate later if needed

#### Decision 3: Windows Path Handling

**Problem:** Windows doesn't allow `:` in filenames. MusicBrainz returns titles like "Album: Subtitle".

**Options Considered:**
- Replace `:` with nothing ("Album Subtitle")
- Replace `:` with `-` ("Album-Subtitle")
- Replace `:` with ` - ` ("Album - Subtitle")
- Keep underscores as-is

**Choice:** Replace `:` with ` - `

**Reasoning:**
- Maintains visual separation (better than nothing)
- Looks professional (better than underscore)
- Consistent with how subtitles are often written
- User can override via config if they prefer different

#### Decision 4: Audio Fingerprinting Integration

**Problem:** Some tracks have no metadata or wrong metadata. Traditional lookup fails.

**Options Considered:**
- Shazam API (requires partnership, not public)
- ACRCloud (commercial, paid)
- AcoustID/Chromaprint (free, open source)

**Choice:** AcoustID with Chromaprint

**Reasoning:**
- Free API key (just register)
- Open source fingerprinting (Chromaprint)
- Integrates with MusicBrainz (returns MB IDs)
- Large database of fingerprints
- Python library available (pyacoustid)

#### Decision 5: Data Source Priority

**Problem:** Multiple sources available. Which to trust?

**Priority Order:**
1. MusicBrainz (primary) - Most comprehensive, community-curated
2. iTunes Search API (fallback) - High-quality commercial data, free
3. Discogs (fallback) - Good for obscure releases
4. AcoustID (special case) - Only for unknown/disputed tracks

**Reasoning:**
- MusicBrainz has release IDs we can use consistently
- iTunes has great cover art and metadata for commercial releases
- Discogs fills gaps for vinyl-only or rare releases
- Fingerprinting is expensive (CPU + network), use sparingly

#### Decision 6: Backup Strategy

**Problem:** User's livelihood depends on this data. Mistakes can't be undone.

**Choice:** Automatic backups before any modification

**Implementation:**
- Copy file before modifying
- Store in `D:\music_backup` (separate drive ideal)
- Include timestamp for rollback options
- User can disable if storage is concern

**Reasoning:**
- Professional audio engineer's collection is irreplaceable
- Disk space is cheap, lost work is expensive
- Better safe than sorry

---

## What I Learned from Previous Session

### Successful Patterns to Preserve

1. **MusicBrainz Search Strategy**
   - Search by album name + "Various Artists"
   - Filter to VA-type releases
   - Get release ID for cover art lookup
   - Works well for 98% of albums

2. **Mutagen for Metadata**
   - Handles MP3, M4A, FLAC consistently
   - EasyID3 interface for common tags
   - Direct access for specialized tags (TPOS for disc numbers)

3. **Dry-Run Mode**
   - Always preview before applying
   - User builds trust in the system
   - Catches edge cases early

### Failures to Address

1. **Network Timeout Handling**
   - Previous: Script crashed on timeout
   - New: Retry with exponential backoff, then skip and log

2. **Windows Path Restrictions**
   - Previous: Rename failed silently or crashed
   - New: Pre-process filenames, replace illegal characters

3. **Multi-disc Detection False Positives**
   - Previous: "Volume 1", "Volume 2" detected as multi-disc
   - New: Only "Disc 1", "Disc 2" pattern triggers consolidation

---

## Questions Resolved During Planning

### Q1: Why not use a database?
JSON files are simpler, human-readable, and sufficient for this scale. If we hit 100,000+ albums, we'd reconsider.

### Q2: Why keep existing scripts?
They work. The Mutagen and MusicBrainz code is proven. Just needs better orchestration, not rewriting.

### Q3: Why interactive CLI over web UI?
User has been working via command line. Familiar workflow, no additional dependencies (Flask, React, etc.).

### Q4: Why iTunes over Spotify/Amazon?
- Spotify API requires OAuth, rate limits, no album art direct access
- Amazon Music API is closed to public
- iTunes Search API is free, no auth, includes artwork URLs

### Q5: Why process one album at a time?
- Network share can be flaky
- Easier to debug single failures
- Can parallelize later once proven stable

---

## Implementation Strategy

### Phase 1: Foundation First
Build the skeleton:
- Config loading
- State persistence
- CLI framework
- Base agent class

Why: Everything else depends on these. Get them right first.

### Phase 2: Data Sources
- Refactor existing MusicBrainz code into source adapter
- Add iTunes adapter (simple HTTP, no auth)
- Add AcoustID adapter (needs Chromaprint binary)

Why: Agents need data sources to work with. Get sources working before building agents.

### Phase 3: Agents
- Scanner refactors `extract_metadata.py`
- Validator adds confidence scoring to `validate_various_artists.py`
- Fixer combines `fix_metadata.py` + `embed_cover.py`

Why: Build on existing proven code, add new capabilities.

### Phase 4: Orchestration
- Queue management
- Pipeline state machine
- Review interface

Why: Final layer that ties everything together.

---

## Risk Mitigation

### Risk 1: Network Share Unreliable
- Mitigation: Aggressive retry logic, checkpoint frequently
- Fallback: Skip and log, process offline later

### Risk 2: Fingerprinting Slow
- Mitigation: Only use for unknown/disputed tracks
- Fallback: Add to manual review queue

### Risk 3: API Rate Limits
- Mitigation: Configurable delays, respect limits
- Fallback: Spread processing over time

### Risk 4: Data Loss
- Mitigation: Backup before modify, dry-run mode
- Fallback: Restore from backup

---

## Success Metrics

The system will be successful when:
1. Can process entire library (17,274 tracks) unattended
2. 95%+ of matches are auto-approved (formatting only)
3. Failed operations can resume from checkpoint
4. User trusts system to make changes

---

## Next Steps After Implementation

1. Test on Various Artists collection (240 albums, known issues)
2. Fix any edge cases discovered
3. Run on full library
4. Monitor for errors, refine thresholds
5. Document lessons learned

---

**Document Status:** Complete
**Ready for:** Implementation Phase 1
