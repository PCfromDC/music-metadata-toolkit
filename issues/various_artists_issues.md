# Various Artists Collection - Issues Report

**Generated:** 2026-01-07
**Total Albums:** 273 (Various Artists: 239, Holiday: 14, Soundtracks: 20)
**Total Tracks:** 5,393

---

## Executive Summary

**Fixed Issues:**
- ✓ 3 tracks with missing artist metadata fixed

**Remaining Issues:**
- 15 tracks in Club Ibiza album need title/artist research
- 58 albums missing embedded cover art (1,760 tracks affected)

---

## 1. Metadata Issues

### 1.1 FIXED - Missing Artist Metadata ✓

**Tracks Fixed:**
1. **"O Holy Night"** - Now That's What I Call Christmas! 3, Track 22
   - Artist: Al Green (researched and fixed)
   - Source: [Wikipedia - Now That's What I Call Christmas! 3](https://en.wikipedia.org/wiki/Now_That's_What_I_Call_Christmas!_3)

2. **"Santa Baby"** - Now That's What I Call Christmas! 3, Track 32
   - Artist: Pussycat Dolls (researched and fixed)
   - Source: [Wikipedia - Now That's What I Call Christmas! 3](https://en.wikipedia.org/wiki/Now_That's_What_I_Call_Christmas!_3)

3. **"Love Is a Many Splendored Thing"** - Grease Soundtrack, Track 23
   - Artist: Studio Orchestra / James Getzoff (instrumental) (researched and fixed)
   - Source: [Discogs - Grease Soundtrack](https://www.discogs.com/master/97901-Various-Grease-The-Original-Soundtrack-From-The-Motion-Picture)

### 1.2 TODO - Club Ibiza Album Research Needed

**Album:** Club Ibiza (Various Artists folder)
**Tracks:** 15 tracks
**Issue:** All tracks have placeholder titles ("unknown", "Track 2", "Track 3", etc.)

**Path:** `\\openmediavault\music\Various Artists\Club Ibiza\`

**Status:** Needs manual research
**Priority:** Medium
**Recommendation:**
- Access Discogs page directly: https://www.discogs.com/release/725717-Various-Club-Ibiza
- Or verify against physical CD/streaming service
- Once tracklist obtained, use `batch_fix_metadata.py` to update titles and artists

**Related Albums:**
- Club Ibiza 2 (16 tracks) - has proper metadata
- Club Ibiza Disc 3 (4 tracks) - also needs research

---

## 2. Cover Art Issues

**Summary:** 58 albums missing embedded cover art (33% of collection)

### 2.1 Holiday Albums Without Cover Art (6 albums, 169 tracks)

| Album | Tracks | Year | Priority |
|-------|--------|------|----------|
| A Very Special Christmas | 32 | 1987 | High |
| A Very Special Christmas, Vol. 3 | 32 | 1997 | High |
| A Very Special Christmas, Vol. 4: Live | 22 | 1999 | High |
| A Very Special Christmas, Vol. 5 | 30 | 2001 | High |
| Christmas Classics | 30 | N/A | Medium |
| Christmas with the Stars | 1 | 1993 | Low |

**Recommendation:** Use `embed_cover.py` to add artwork
**Sources:** iTunes, Amazon Music, Discogs, Cover Art Archive

**Example:**
```bash
python utilities/embed_cover.py "\\openmediavault\music\Various Artists - Holiday\A Very Special Christmas" "https://url-to-cover-art.jpg"
```

### 2.2 Soundtracks Without Cover Art (7 albums, 104 tracks)

| Album | Tracks | Year | Priority |
|-------|--------|------|----------|
| Grease | 24 | 1978 | High |
| Saturday Night Fever | 17 | 1977 | High |
| Wayne's World | 13 | 1992 | High |
| Down from the Mountain: O Brother, Where Art Thou? | 12 | 2001 | Medium |
| Sesame Street: The Best Of Elmo | 15 | 1992 | Medium |
| The Many Songs Of Winnie The Pooh (English Version) | 12 | 2006 | Medium |
| Shark Tale | 1 | 2004 | Low |

### 2.3 Various Artists Albums Without Cover Art (45 albums, 1,487 tracks)

**Top 20 albums by track count:**
1. Balada 3 masc. (106 tracks)
2. Balada 3 Fem (53 tracks)
3. My First Nursery Rhymes (98 tracks)
4. Caf� Paris (50 tracks)
5. ... (see full list in audit CSV)

**Full List Available:** `outputs/various_artists_audit.csv`

**Recommendation:**
- Prioritize albums with most tracks first
- Use automated cover art lookup tools if available
- MusicBrainz Cover Art Archive API integration recommended

---

## 3. Genre Standardization

**Status:** To be analyzed
**Recommendation:** Extract genre statistics to identify inconsistencies

Potential genres to standardize:
- "Electronica & Dance" vs "Dance" vs "Club"
- "Christmas" (already standardized in Holiday collection)
- "Live" vs "Concert" vs "Live Recording"

---

## 4. Recommended Next Steps

### Immediate (High Priority)
1. ✓ Fix missing artist metadata (3 tracks) - **DONE**
2. Add cover art to popular soundtrack albums (Grease, Saturday Night Fever, Wayne's World)
3. Add cover art to "A Very Special Christmas" series (4 albums, 116 tracks)

### Short-term (Medium Priority)
4. Research Club Ibiza tracklist and fix all 15 tracks
5. Add cover art to remaining Holiday and Soundtracks albums
6. Add cover art to large Various Artists albums (Balada series, Caf� Paris, etc.)

### Long-term (Low Priority)
7. Standardize genres across all collections
8. Add cover art to single-track albums
9. Verify all metadata against authoritative sources

---

## 5. Tools Used

**Extraction:**
```bash
python utilities/extract_metadata.py "\\openmediavault\music\Various Artists" --incremental
```

**Fixing Metadata:**
```bash
python utilities/fix_metadata.py artist "path/to/file.mp3" "Artist Name"
python utilities/fix_missing_artists.py  # Custom script for batch fixes
```

**Adding Cover Art:**
```bash
python utilities/embed_cover.py "album/path" "image_url_or_path"
```

---

## 6. Statistics

**Collection Overview:**
- Total Tracks: 5,393
- Total Albums: 273
- Artists: ~1,500+ individual artists

**Issues Resolved:**
- Missing metadata: 3 tracks fixed ✓

**Issues Remaining:**
- Club Ibiza metadata: 15 tracks
- Missing cover art: 1,760 tracks (58 albums)

**Completion Status:**
- Metadata: 99.7% complete (5,378/5,393 tracks)
- Cover art: 67% complete (3,633/5,393 tracks have embedded art)

---

## 7. Sources Used

Research sources for metadata fixes:
- [Wikipedia - Now That's What I Call Christmas! 3](https://en.wikipedia.org/wiki/Now_That's_What_I_Call_Christmas!_3)
- [Discogs - Various Artists](https://www.discogs.com/)
- [MusicBrainz](https://musicbrainz.org/)

Cover art sources (recommended):
- [iTunes Search API](https://itunes.apple.com/search)
- [Cover Art Archive](https://coverartarchive.org/)
- [Amazon Music](https://music.amazon.com/)
- [Discogs](https://www.discogs.com/)

---

**Last Updated:** 2026-01-07
**Next Review:** After cover art additions complete
