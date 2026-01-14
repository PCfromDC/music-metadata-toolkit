# Claude Agents for Audio Cleanup - Future Implementation Plan
**Date:** 2026-01-07
**Status:** Planning / Not Implemented
**Decision:** Defer until after processing 100-200 artists

---

## Executive Summary

This document evaluates whether to create custom .claude agents (using Claude Agent SDK) to automate repetitive research and analysis tasks in the music library cleanup project.

**Recommendation:** Don't build agents immediately. Continue with Python utilities and queue system for the next 100-200 artists, then revisit based on actual pain points identified.

**Rationale:**
- Existing Python utilities handle 80% of tasks efficiently
- Unknown what research patterns are repetitive (need more data)
- Queue management system is higher priority (Week 1)
- Can add agents later once needs are validated

---

## Current State Analysis

### Existing Tools
- **Python utilities:** `extract_metadata.py`, `fix_metadata.py`, `batch_fix_metadata.py`, `embed_cover.py`
- **Handles:** Metadata extraction, single-file fixes, bulk operations, cover art embedding
- **Works well for:** Deterministic, scripted operations

### Cleanup Workflow
- **Scale:** 17,274 tracks across 930 artists
- **Tasks:** Extract → identify issues → research → fix → verify
- **Manual work:** Untitled tracks, incomplete albums, cover art sources
- **Planned:** Queue management and progress tracking

### Current Pain Points
1. **Manual research time** - Looking up untitled tracks on Discogs/MusicBrainz/iTunes
2. **Album completeness** - Determining if albums should have more tracks
3. **Decision-making overhead** - 273 Various Artists albums to triage
4. **Issue pattern detection** - Identifying similar problems across albums
5. **Context switching** - Between extraction, research, fixing, verification

---

## Proposed Agents

### Agent 1: Metadata Research Assistant
**Purpose:** Research untitled tracks, incomplete albums, and cover art sources

**Capabilities:**
- Search Discogs, MusicBrainz, iTunes for album information
- Verify album completeness (check official tracklists)
- Find cover art URLs from Cover Art Archive
- Present findings with confidence scores

**Example Usage:**
```
User: Research "Club Ibiza Disc 3" - it has 4 untitled tracks

Agent:
1. Searches Discogs for "Club Ibiza Disc 3"
2. Finds official tracklist
3. Returns:
   - Track 1 = "Some Title"
   - Track 2 = "Another Title"
   - Track 3 = "Third Title"
   - Track 4 = "Fourth Title"
4. Provides Discogs URL for verification
```

**Value:** Saves hours of manual web searches across 4,762 tracks

**Priority:** HIGH (most time-consuming manual task)

---

### Agent 2: Album Completeness Auditor
**Purpose:** Detect incomplete albums and recommend missing tracks

**Capabilities:**
- Compare local track counts vs official releases
- Identify missing tracks by track number gaps
- Flag bootlegs vs official releases
- Suggest acquisition sources

**Example Usage:**
```
User: Analyze "Buddha-Bar, Vol. 1"

Agent:
1. Finds 3 tracks locally (1-02, 1-06, 1-07)
2. Looks up official release: 2 discs, 32 total tracks
3. Reports: Missing 29 tracks (91% incomplete)
4. Lists missing track titles
5. Suggests: Complete album available on streaming services
```

**Value:** Quickly identifies 273 albums needing completeness checks

**Priority:** MEDIUM (useful but not urgent)

---

### Agent 3: Issue Pattern Detector
**Purpose:** Analyze audit reports and identify systematic issues

**Capabilities:**
- Read JSON/CSV audit outputs
- Detect patterns: missing genre, no cover art, truncated titles
- Group similar issues for bulk fixing
- Prioritize by severity and fix complexity

**Example Usage:**
```
User: Analyze various_artists_audit.csv

Agent:
1. Reads CSV with 4,762 tracks
2. Finds patterns:
   - 45 albums missing cover art
   - 12 albums with genre="Other"
   - 8 albums with truncated track titles
3. Groups by fix type:
   - Cover art: bulk download from MusicBrainz
   - Genre: bulk change based on artist lookup
   - Titles: research and manual fix
4. Generates prioritized fix list with commands
```

**Value:** Reduces analysis time for large collections

**Priority:** MEDIUM (nice to have for bulk operations)

---

### Agent 4: Queue Strategy Advisor
**Purpose:** Help prioritize which artists/albums to process next

**Capabilities:**
- Analyze artist library sizes, issue counts, complexity
- Suggest processing order (smallest first, most issues first, alphabetical)
- Estimate time per artist
- Recommend batch sizes

**Example Usage:**
```
User: Help me prioritize the next 10 artists to process

Agent:
1. Analyzes 929 pending artists
2. Suggests priority order:
   - 5 small artists (50-100 tracks) - quick wins
   - 3 medium artists (100-300 tracks) - moderate effort
   - 2 problem artists (high issues) - learning opportunities
3. Provides estimated 10-15 hours total
```

**Value:** Reduces decision fatigue

**Priority:** LOW (manual prioritization works fine)

---

### Agent 5: Metadata Validation Expert
**Purpose:** Review proposed metadata changes before applying

**Capabilities:**
- Verify genre standardization is correct
- Check artist name consistency
- Validate album artist vs track artist logic
- Flag suspicious changes

**Example Usage:**
```
User: Review these 50 proposed genre changes

Agent:
1. Analyzes each change:
   - 45 changes "Other" → "Rock" - APPROVED
   - 3 changes "Pop" → "Rock" - QUESTIONABLE (reviews artist)
   - 2 changes "Live" → "Rock" - REJECTED (keep Live)
2. Provides reasoning for each decision
```

**Value:** Prevents metadata corruption

**Priority:** LOW (Python utilities have built-in verification)

---

## Integration Architecture

### Hybrid Approach: Agents + Python Utilities

**Python utilities handle:**
- Fast, deterministic operations (extract, apply fixes, verify)
- File I/O and metadata manipulation
- Batch processing and checkpointing

**Claude agents handle:**
- Research and web lookups (Discogs, MusicBrainz, iTunes)
- Decision-making and prioritization
- Pattern detection and analysis
- Complex reasoning tasks

### Integration Points

1. **Metadata Research Agent** → generates CSV of fixes → `batch_fix_metadata.py` applies them
2. **Album Completeness Auditor** → outputs missing track reports → user decides
3. **Issue Pattern Detector** → analyzes `extract_metadata.py` outputs → suggests scripts
4. **Queue Strategy Advisor** → recommends artist order → `music_queue_manager.py` uses it
5. **Metadata Validation Expert** → reviews changes → approves before `fix_metadata.py` runs

### Example Workflow

```bash
# Step 1: Extract metadata (Python utility)
python utilities/extract_metadata.py "Various Artists"

# Step 2: Agent analyzes audit
[Metadata Research Agent] reads: outputs/various_artists_audit.csv
[Agent] identifies: 15 albums with untitled tracks
[Agent] researches: Discogs, MusicBrainz for each
[Agent] generates: outputs/research_findings.json

# Step 3: User reviews
cat outputs/research_findings.json
# Review agent's findings, verify sources

# Step 4: Apply fixes (Python utility)
python utilities/batch_fix_from_json.py research_findings.json

# Step 5: Verify (Python utility)
python utilities/extract_metadata.py "Various Artists" --verify
```

**Benefits:**
- Semi-automated (agent researches, user approves, utilities apply)
- Maintains safety (manual review before changes)
- Leverages both agent intelligence and utility speed

---

## Pros and Cons Analysis

### Pros of Creating .claude Agents

**Time Savings:**
- Automate hours of manual research (Discogs lookups, tracklist verification)
- Reduce decision-making overhead (which albums to prioritize)
- Pattern detection across thousands of tracks

**Quality Improvements:**
- Consistent research methodology (same sources, same criteria)
- Validation before applying changes (catch errors)
- Better completeness checking

**Scalability:**
- 930 artists benefit from automated research
- Research agent works async (while you sleep)
- Reusable for future artists added to library

**Learning:**
- Agents document reasoning (why this track title, why this genre)
- Build knowledge base of common issues
- Improve over time with feedback

### Cons of Creating .claude Agents

**Development Overhead:**
- Time to build, test, refine agents (1-2 weeks)
- Learning curve for Claude Agent SDK
- Maintenance as APIs change

**API Costs:**
- Claude API calls for each agent invocation
- Rate limits on external APIs (Discogs, MusicBrainz)
- May need paid tiers for high-volume usage

**Complexity:**
- Additional layer of abstraction
- Debugging agent behavior harder than Python code
- Integration challenges

**Overkill for Simple Tasks:**
- Many operations don't need reasoning
- Python utilities already fast and reliable
- Agents best for complex, judgment-heavy tasks

---

## Implementation Plan (When Ready)

### Phase 1: Single Agent Prototype (Week 1)

**Build:** Metadata Research Assistant (simplest, highest value)

**Features:**
- Input: Album name, artist name
- Output: Track titles, cover art URL, album info
- APIs: Discogs, MusicBrainz, Cover Art Archive

**Test on:**
- Club Ibiza Disc 3 (4 untitled tracks)
- Buddha-Bar Vol. 1 (completeness check)
- 5-10 other albums with known issues

**Success Criteria:**
- Finds correct track titles with >90% accuracy
- Saves >50% time vs manual research
- Provides verifiable sources (URLs)

**Files to Create:**
```
.claude/
├── agents/
│   ├── metadata-research/
│   │   ├── agent.json
│   │   ├── system-prompt.md
│   │   └── tools/
│   │       ├── discogs-search.js
│   │       ├── musicbrainz-lookup.js
│   │       └── coverart-find.js
│   └── README.md
└── config.json
```

### Phase 2: Integration with Workflow (Week 2)

**Integrate agent with utilities:**

1. Create wrapper script: `utilities/research_with_agent.py`
   - Reads audit CSV
   - Invokes Metadata Research Agent
   - Writes findings JSON

2. Create new utility: `utilities/batch_fix_from_json.py`
   - Reads agent findings JSON
   - Applies fixes to audio files
   - Logs changes for verification

3. Update workflow documentation in CLAUDE.md

**Benefits:**
- Semi-automated workflow
- Maintains safety (manual review)
- Leverages both agent and utility strengths

### Phase 3: Expand Agent Library (Week 3+)

**Add agents as needed:**
- Issue Pattern Detector (if pattern analysis becomes tedious)
- Album Completeness Auditor (if incomplete albums are common)
- Custom agents for specific problems

**Prioritize based on actual pain points discovered during cleanup.**

---

## Decision Framework

### When to Build Agents

Build agents if **ANY** of these conditions are met:

1. **Time Threshold:** Research takes >2 hours per album on average
2. **Volume Threshold:** >100 albums need similar research tasks
3. **Repetition Threshold:** Same research task repeated >50 times
4. **Burnout Threshold:** Manual lookups causing fatigue/errors

### When to Skip Agents

Skip agents if **ALL** of these are true:

1. **Low volume:** <20 problematic albums total
2. **Fast research:** <20% of time spent on manual lookups
3. **One-time cleanup:** Not maintaining library long-term
4. **Utilities sufficient:** Python scripts handle everything efficiently

---

## Recommendation: Phased Approach

### Phase 0: Current (Week 0)
**Decision:** Don't build agents yet

**Actions:**
1. Continue Various Artists reorganization (in progress)
2. Build queue management system (Week 1 plan)
3. Process 50-100 more artists with current tools
4. Document pain points and repetitive tasks

**Why:**
- Already 14 albums into Various Artists (folder reorganization done)
- Queue system is more urgent
- Don't know repetitive patterns yet
- Can add agents anytime

### Phase 1: Evaluate (After 100 artists)
**Decision:** Re-evaluate whether agents are needed

**Metrics to track:**
- Average research time per album
- Number of untitled tracks encountered
- Number of incomplete albums found
- Repetitive research patterns identified
- Manual lookup burnout level

**Questions to answer:**
1. What percentage of time is manual research? (>50% → build agents)
2. How many problematic albums found? (>100 → agents valuable)
3. Are patterns repetitive? (Yes → agents save time)

### Phase 2: Build (If needed)
**Decision:** Build Metadata Research Assistant first

**Approach:**
1. Start with single agent (Metadata Research)
2. Test on 20 albums with known issues
3. Measure time savings vs development cost
4. Expand to other agents if ROI is positive

### Phase 3: Expand (If successful)
**Decision:** Add more agents based on needs

**Priority order:**
1. Metadata Research Assistant (highest value)
2. Issue Pattern Detector (if bulk analysis needed)
3. Album Completeness Auditor (if many incomplete albums)

---

## Questions for Future Evaluation

Before building agents, answer these:

1. **What percentage of time is spent on manual research** vs running Python scripts?
   - If >50% → agents worth it
   - If <20% → stick with utilities

2. **How many untitled/problematic albums** across 930 artists?
   - If >100 → Metadata Research Agent very valuable
   - If <20 → manual research is fine

3. **Comfort level with Claude Agent SDK?**
   - Familiar → faster to build
   - New → learning curve adds overhead

4. **Willing to wait 1-2 weeks** before continuing cleanup?
   - Yes → build agent prototype first
   - No → proceed with utilities, add agents later

5. **Long-term use** (years, adding new music)?
   - Yes → agents are good investment
   - No (one-time) → utilities sufficient

---

## Cost-Benefit Analysis

### If Building Agents

**Costs:**
- Development time: 1-2 weeks (20-40 hours)
- Learning curve: Claude Agent SDK
- API costs: Claude API calls + Discogs/MusicBrainz rate limits
- Maintenance: Updates as APIs change

**Benefits:**
- Time savings: 50-80% reduction in manual research
- Consistency: Same methodology for all lookups
- Scalability: Works for all 930 artists
- Quality: Validation before changes
- Reusability: Future music library additions

**Break-even point:**
- If agents save 2 hours per album
- And 200 albums need research
- Total savings: 400 hours
- Development cost: 40 hours
- ROI: 10x

### If Skipping Agents

**Costs:**
- Manual research time: 1-2 hours per problematic album
- Decision fatigue: Choosing what to fix next
- Errors: Manual lookups more error-prone

**Benefits:**
- No development overhead
- Simpler workflow (Python utilities only)
- Full control over each decision
- No API dependencies

**Break-even point:**
- If only 10-20 albums need research
- Manual research: 20 hours total
- Agent development: 40 hours
- ROI: Negative (don't build)

---

## Next Steps (When Ready to Implement)

1. **Finalize decision** based on actual data from 100+ artists
2. **Choose agent type** (start with Metadata Research Assistant)
3. **Set up Claude Agent SDK** development environment
4. **Build prototype** with Discogs/MusicBrainz integration
5. **Test on 20 albums** with known issues
6. **Measure time savings** vs manual research
7. **Decide whether to expand** agent library or stick with single agent
8. **Document agent usage** in CLAUDE.md and README.md

---

## Conclusion

**Current Recommendation:** Wait and see.

**Why:**
- Too early to know if agents are needed
- Python utilities handle most tasks well
- Queue system is higher priority
- Can build agents later if patterns emerge

**When to Reconsider:**
- After processing 100-200 artists
- If research takes >2 hours per album
- If similar issues repeat across 50+ albums
- If manual lookups cause burnout

**Best Path Forward:**
1. Continue with current Python utilities
2. Build queue management system (Week 1)
3. Process Various Artists and 100 more artists
4. Document pain points and repetitive tasks
5. Revisit this plan with actual data
6. Build agents only if ROI is clear

---

**Document Version:** 1.0
**Last Updated:** 2026-01-07
**Status:** Planning / Deferred
**Next Review:** After processing 100-200 artists
