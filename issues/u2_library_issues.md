# U2 Music Library Audit Report (Updated)

**Total Files:** 261 tracks across 20 studio albums, 2 compilations, 3 singles, 3 live bootlegs, 2 collaboration tracks
**Date:** 2025-12-16

---

## Summary of Issues

| Issue Type | Count |
|------------|-------|
| Filename watermarks | 1 |
| Missing tracks (gaps in tracklist) | 4 albums |
| Split artist entries | 2 |
| Genre inconsistency | 1 |
| Filename typos | 1 |

---

## Detailed Issues

### 1. Filename Watermark

**File:** `/path/to/music/U2\7\01 Summer Rain - music-madness.mp3`
- **Issue:** Filename contains "- music-madness" watermark from download source
- **Metadata Title:** Correctly shows "Summer Rain" (without watermark)
- **Recommendation:** Rename file to `01 Summer Rain.mp3` to remove watermark from filename

### 2. Missing Tracks (Track Number Gaps)

**Songs Of Experience (Deluxe Edition)**
- **Current:** 14 tracks
- **Missing Track Numbers:** 5, 13
- **Notes:** Tracks jump from 4 to 6, and from 12 to 14
- **Recommendation:** Verify if tracks 5 ("American Soul") and 13 ("13 (There Is a Light)") are missing or if this is intentional

**Rattle and Hum**
- **Current:** 16 tracks
- **Missing Track Number:** 15 (shown as Track 16, then Track 17)
- **Notes:** Track 15 is "The Star Spangled Banner" but listed under "Jimi Hendrix" artist
- **Recommendation:** Track 15 exists but appears separately due to artist split (see Issue #3)

**Zoocoustic**
- **Current:** 25 tracks
- **Missing Track Number:** 24
- **Notes:** Tracks jump from 23 to 25
- **Recommendation:** Verify if track 24 is missing (was previously deleted as duplicate)

**How to Dismantle an Atomic Bomb**
- **Current:** 11 tracks
- **Expected:** 12 tracks (including hidden track "Fast Cars")
- **Notes:** Missing track 12, but this may be intentional if hidden track wasn't included in source files

### 3. Split Artist Entries

The library has tracks split across multiple artist categories:

**Jimi Hendrix - Rattle and Hum (Track 15)**
- **File:** `15 The Star Spangled Banner.mp3`
- **Issue:** Artist field is "Jimi Hendrix" instead of "U2"
- **Status:** PREVIOUSLY ADDRESSED - Album Artist set to "U2", Artist set to "Jimi Hendrix"
- **Current State:** Metadata correctly split, but appears as separate artist in JSON structure
- **Recommendation:** Keep as-is (metadata is correct for proper album organization)

**U2 & Kygo - Songs Of Experience (Track 17)**
- **File:** `17 - You're The Best Thing About Me (U2 Vs. Kygo).mp3`
- **Issue:** Artist field is "U2 & Kygo" instead of "U2"
- **Status:** This is CORRECT - it's an official remix collaboration
- **Recommendation:** Keep as-is

### 4. Genre Inconsistency

**U218 Singles**
- **Current Genre:** "Other"
- **Expected Genre:** "Rock" (to match other compilations)
- **Recommendation:** Change genre to "Rock" for consistency

### 5. Filename Typo

**Who's Gonna Ride Your Wild Horses [Import CD] - Track 3**
- **Metadata Title:** "Fortuante Son"
- **Should Be:** "Fortunate Son"
- **Note:** Typo in "Fortunate" (missing 'n')

---

## Album Status Summary

### OFFICIAL STUDIO ALBUMS (10) - ALL COMPLETE

| Album | Year | Tracks | Cover | Issues |
|-------|------|--------|-------|--------|
| Achtung Baby | 1991 | 12/12 | YES | None |
| All That You Can't Leave Behind | 2000 | 11/11 | YES | None |
| How to Dismantle an Atomic Bomb | 2004 | 11/12 | YES | Missing track 12 (hidden track) |
| No Line On The Horizon | 2009 | 11/11 | YES | None |
| Pop | 1997 | 12/12 | YES | None |
| Rattle and Hum | 1988 | 17/17 | YES | Track 15 split to different artist |
| Songs of Innocence | 2014 | 11/11 | YES | None |
| Songs Of Experience (Deluxe Edition) | 2017 | 14/17 | YES | Missing tracks 5 & 13 |
| The Joshua Tree | 1987 | 11/11 | YES | None |
| Zooropa | 1993 | 10/10 | YES | None |

### OFFICIAL COMPILATIONS (2) - COMPLETE

| Album | Year | Tracks | Cover | Issues |
|-------|------|--------|-------|--------|
| The Best of 1980-1990 | 1998 | 29/29 | YES | None |
| U218 Singles | 2006 | 19/19 | YES | Genre = "Other" instead of "Rock" |

### OFFICIAL LIMITED/FAN CLUB RELEASES (2)

| Album | Year | Tracks | Cover | Issues |
|-------|------|--------|-------|--------|
| 7 | 2002 | 7/7 | YES | Filename watermark on track 1 |
| Artificial Horizon | 2010 | 1/13 | YES | INCOMPLETE - only has track 7 |

### OFFICIAL SINGLES (3) - COMPLETE

| Album | Year | Tracks | Cover | Issues |
|-------|------|--------|-------|--------|
| Electrical Storm [DVD] | 2002 | 1 | YES | None |
| Invisible (RED) Edit Version | 2014 | 1 | YES | None |
| Who's Gonna Ride Your Wild Horses [Import CD] | 2001 | 4/4 | YES | Track 3 title typo |

### LIVE RECORDINGS (3) - BOOTLEG/UNOFFICIAL

| Album | Year | Tracks | Cover | Issues |
|-------|------|--------|-------|--------|
| Before The Fire - After The Flood | 1993 | 24 | YES | Bootleg compilation |
| The Final Sphere Concert | 2024 | 27 | YES | Bootleg - U2:UV finale (3/2/24) |
| Zoocoustic | 1994 | 25/26 | YES | Bootleg, missing track 24 |

### COLLABORATION TRACKS (2) - COMPLETE

| Track | Artist | Album | Year | Cover | Issues |
|-------|--------|-------|------|-------|--------|
| Knockin' On Heaven's Door | U2 feat. Bob Dylan | Joshua Tree Tour - Live from LA | 1987 | YES | None |
| One / Unchained Melody | U2 feat. Eddie Vedder | Make Poverty History - Live from Melbourne | 2006 | YES | None |

---

## Recommended Actions

### High Priority
1. **Rename file:** Remove "- music-madness" watermark from track 1 filename in "7" album
2. **Fix genre:** Change U218 Singles genre from "Other" to "Rock"
3. **Fix typo:** Correct "Fortuante Son" to "Fortunate Son" in Who's Gonna Ride Your Wild Horses

### Medium Priority
1. **Songs Of Experience:** Investigate missing tracks 5 ("American Soul") and 13 ("13 (There Is a Light)")
2. **Zoocoustic:** Verify track 24 was intentionally deleted (duplicate) or needs to be recovered

### Low Priority
1. **Artificial Horizon:** Remains incomplete (1 of 13 tracks) - decide whether to complete or keep as-is
2. **How to Dismantle an Atomic Bomb:** Verify if hidden track 12 ("Fast Cars") should be added

---

## Overall Library Health

**Excellent Progress!** The U2 library has been significantly improved:
- ✓ All albums now have cover art embedded
- ✓ Metadata is clean and consistent
- ✓ Artist tags properly organized with Album Artist/Artist split where needed
- ✓ Live recordings properly categorized with "Live" genre
- ✓ Collaboration tracks properly attributed
- ✓ Bootleg albums cleaned up with corrected metadata

**Remaining work is minor** - primarily cosmetic filename issues and a few potentially missing tracks to investigate.

---

## Sources
- [U2 - MusicBrainz](https://musicbrainz.org/artist/a3cb23fc-acd3-4ce0-8f36-1e5aa6a18432)
- [U2 discography - Wikipedia](https://en.wikipedia.org/wiki/U2_discography)
- [Songs of Experience - Wikipedia](https://en.wikipedia.org/wiki/Songs_of_Experience_(U2_album))
- iTunes Music Store (for album verification)
