# Lifecycle Command

Run the full music-cleanup pipeline end to end, in the canonical phase order, by
invoking the same tools the Python `cli.py lifecycle` uses, with AI decision
points layered on top of the ambiguous cases the deterministic code defers.

This is the Claude-side orchestrator. It does **not** reimplement any phase
logic; it calls the existing executors and adds judgment where (and only where)
they ask a human to decide.

## Usage

```
/lifecycle <path>
/lifecycle <path> --scan-only
/lifecycle <path> --execute
```

## Examples

```
/lifecycle /path/to/music/Various Artists
/lifecycle //192.168.1.252/music/U2 --scan-only
/lifecycle D:/music/Ben Harper --execute
```

## Canonical Phase Order

The phase order is the single parity anchor shared with the Python CLI
(`LIFECYCLE_PHASES` in `orchestrator/main.py`):

```
scan -> identify -> validate -> dedupe -> covers -> fix
```

Run the phases in this exact order. Do not add, drop, or reorder phases.

## Phase -> Tool Mapping

| # | Phase | Tool invoked (do NOT reimplement) | AI layered on top |
|---|----------|-----------------------------------|-------------------|
| 1 | scan | `python cli.py scan "<path>"` (ScannerAgent) | none |
| 2 | identify | `ValidatorAgent.identify_unknown_tracks(...)` / AcoustID (`sources/acoustid.py`) for weak-metadata albums only | `fingerprint_validator` adjudicates which AcoustID hit to trust |
| 3 | validate | `python cli.py validate "<path>"` (ValidatorAgent vs MusicBrainz/iTunes) | `conflict_resolver` + `fingerprint_validator` on ambiguous matches |
| 4 | dedupe | `python cli.py dedupe "<path>" [--scan-only/--dry-run/--execute]` (`utilities/deduplicate.py`) | `duplicate_detector` adjudicates the `outputs/dedupe_review.json` list |
| 5 | covers | `python cli.py repair-covers "<path>" [...]` then `generate_folder_art(root, execute=...)` (`utilities/generate_folder_art.py`) | `/verify-covers` visual match on embedded/folder art |
| 6 | fix | `python cli.py fix "<path>"` (FixerAgent; applies approved metadata/cover fixes) | applies only the decisions confirmed in phases 3-5 |

The single Python entry point that chains all six is:

```bash
cd "D:\music cleanup" && python cli.py lifecycle "<normalized_path>" [--scan-only|--dry-run|--execute]
```

Running each phase as a separate tool call (as documented below) is the
Claude-side equivalent and lets the AI decision points slot in between phases.
Either path runs the **same** executors in the **same** order.

## Safety Model (read before running)

Every phase honors the shared three-mode safety model:

| Mode | Flag | Writes to music? |
|------|------|------------------|
| Scan-only | `--scan-only` | No. Report only. |
| Dry-run | `--dry-run` (**DEFAULT**) | No. Show the plan / would-do counts. |
| Execute | `--execute` | **Yes.** The only mode that modifies files. |

- **Default is dry-run.** If the user passes neither `--scan-only` nor
  `--execute`, run every phase in dry-run and write nothing.
- **Require explicit user confirmation before any `--execute` run.** Even when
  the user typed `--execute`, present the dry-run plan first and get an explicit
  "yes, execute" before invoking any tool in execute mode. Never escalate from
  dry-run to execute on your own.
- Music is written ONLY under `--execute`. The `fix` phase is skipped entirely
  under `--scan-only` and runs dry (would-fix counts) under the default dry-run.

## Instructions

When this command is invoked with arguments: $ARGUMENTS

**Path Normalization:**
Replace all backslashes (`\`) with forward slashes (`/`).

**Resolve the mode** from the flags: `--scan-only`, `--execute`, or (default)
dry-run. Carry the chosen mode flag into every phase below.

### Phase 1 — scan

```bash
cd "D:\music cleanup" && python cli.py scan "<normalized_path>"
```

Extract metadata, cover presence, and issues for every album. This seeds the
processing queue the later phases consume.

**Excluded directories.** Every phase walks the library through one shared
exclusion rule (`utilities/core/audio_file.is_excluded_dir` /
`is_excluded_path`), so NAS recycle bins and OS/system metadata dirs are never
scanned, validated, de-duped, or cover-checked. Skipped names include
`.recycle`, `#recycle`, `@eaDir`, `#snapshot`, `$RECYCLE.BIN`, `System Volume
Information`, macOS `.Trashes`/`.Spotlight-V100`/`.fseventsd`, Syncthing
`.stfolder`/`.stversions`, and the toolkit's own `backups/`, `.cover_backup/`,
`_duplicates/`. Real music folders that merely start with a dot or symbol
(`.38 Special`, `...And You Will Know Us by the Trail of Dead`) are still
scanned. Do not add ad-hoc skip logic in a phase; extend the shared set instead
so all walkers stay in parity.

### Phase 2 — identify

Best-effort AcoustID song-ID for albums with weak metadata only (no title, or
artist in `{"", "various artists", "unknown"}`) to bound `fpcalc` cost. This is
a graceful no-op when there is no AcoustID API key or no `fpcalc.exe`.

Use `ValidatorAgent.identify_unknown_tracks(album_path)` (returns `[]` and never
raises on missing key / fpcalc / error). Does NOT mutate queue status.

**AI decision point — `fingerprint_validator`:** when an album returns multiple
candidate recordings or a low-confidence hit, consult the
`fingerprint_validator` agent to pick the recording to trust (or to abstain).
Record its choice for the validate phase; do not write tags here.

### Phase 3 — validate

```bash
cd "D:\music cleanup" && python cli.py validate "<normalized_path>" [--dry-run|--scan-only|--execute]
```

ValidatorAgent compares each album against MusicBrainz / iTunes and routes by
confidence (VALIDATED / VERIFIED / NEEDS_REVIEW).

**AI decision point — `conflict_resolver` (+ `fingerprint_validator`):** for
every album that lands in NEEDS_REVIEW or shows a source conflict:

1. Gather the validator output plus the trusted sources.
2. Consult `conflict_resolver`. Auto-accept a resolution ONLY when it returns
   `conflict_resolution_status == "resolved"` and `requires_human_review` is
   empty; otherwise leave the album flagged for a human.
3. If the conflict hinges on identity (wrong recording, conflicting ISRCs),
   bring in the Phase 2 `fingerprint_validator` evidence to break the tie.

Resolved decisions feed the fix phase; unresolved ones stay in `needs_review`.

### Phase 4 — dedupe

```bash
cd "D:\music cleanup" && python cli.py dedupe "<normalized_path>" [--scan-only|--dry-run|--execute] \
  [--backup-dir "D:\music_backup\_duplicates"] [--aggressive] [--no-fingerprint]
```

`utilities/deduplicate.py` finds within-folder duplicates. Strong matches are
auto-routed to backup (move, never delete); probable / cross-album candidates
are written to `outputs/dedupe_review.json` for adjudication.

**AI decision point — `duplicate_detector`:** read `outputs/dedupe_review.json`
and adjudicate each probable / cross-album group: pick the keeper, or mark the
items as legitimately distinct (studio vs live, radio edit vs album, remaster vs
original) and leave them in place. Do not treat distinct versions as duplicates
unless `--aggressive` was requested. Only act on the survivors under `--execute`.

### Phase 5 — covers

First repair corrupted / missing embedded art (ffprobe ground truth via
`utilities/core/ffprobe.attached_pic_dims`):

```bash
cd "D:\music cleanup" && python cli.py repair-covers "<normalized_path>" [--scan-only|--dry-run]
```

Then sync `folder.jpg` for each album:

```bash
# execute mode -> writes folder.<ext>; dry-run/scan-only -> would-write counts only
python -c "from utilities.generate_folder_art import generate_folder_art; print(generate_folder_art('<normalized_path>', execute=<True|False>))"
```

Pass `execute=True` ONLY in confirmed execute mode; otherwise `execute=False`.

**AI decision point — `/verify-covers`:** after art is in place (or planned),
run the visual-match check from `/verify-covers` over the album `folder.jpg`
files. Cover art can be technically valid (good size, full coverage) yet
visually WRONG for the album (Ben Harper, 2026-01-13). Flag mismatches in the
summary; re-embed a correct cover only under confirmed `--execute`.

### Phase 6 — fix

```bash
cd "D:\music cleanup" && python cli.py fix "<normalized_path>" [--dry-run|--execute]
```

FixerAgent applies the approved metadata and cover fixes — the decisions
confirmed in phases 3-5. This phase writes only under `--execute`; it is skipped
entirely under `--scan-only` and reports would-fix counts under dry-run.

### Final — Summary Report

Report per phase (matching the `run_history` record shape):

- scanned, identified, validated, needs_review
- deduped_moved, covers_repaired, folderjpg_added, fixed
- flagged (items needing human attention: dedupe review + cover failures)
- mode used (scan-only / dry-run / execute)

## Queue Strategy

The lifecycle uses a fresh queue per run: at start, a non-empty
`state/queue.json` is archived to `state/history/queue-<timestamp>.json` and
cleared; at end, a dated summary is appended to `state/run_history.json`. The
Python `cli.py lifecycle` handles this automatically — do not manage the queue
by hand.

## AI Decision Points (summary)

| Phase | Agent / command | Decides |
|-------|-----------------|---------|
| identify | `fingerprint_validator` | which AcoustID recording to trust |
| validate | `conflict_resolver` + `fingerprint_validator` | resolve ambiguous source conflicts; auto-apply gate |
| dedupe | `duplicate_detector` | adjudicate probable / cross-album groups in `dedupe_review.json` |
| covers | `/verify-covers` | visual match: catch valid-but-wrong art |

These layers are advisory: they only adjudicate cases the deterministic
executors explicitly defer. They never override a clean deterministic result and
never trigger writes outside confirmed `--execute`.

## Error Handling

If any phase fails: log the error, continue with the remaining phases, include
the failure in the final summary, and do NOT stop the pipeline. A single album
must never crash the run.
