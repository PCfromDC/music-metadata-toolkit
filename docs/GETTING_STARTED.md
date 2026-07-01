# Getting Started

This guide gets you from zero to a cleaned-up music library. You do not need to
know anything about the project to follow it. There are two ways to run the
pipeline and they do the same work:

- **Path A - plain Python.** No Claude, no account, no network beyond optional
  metadata lookups. Everything runs locally from your terminal.
- **Path B - Claude Code.** The same pipeline, plus AI judgment for the calls a
  script cannot make (which metadata source to trust, whether a cover art image
  actually matches the album).

The two paths are **equivalent**: same phases, same order, same safety model, same
file output. Path B only adds AI decision-making on top of the identical Python
core. Start with Path A if you just want a deterministic, repeatable clean.

---

## 1. Prerequisites

- **Python 3.9+** on the machine that can reach your music files.
- Your music in per-artist / per-album folders (MP3, M4A/MP4, or FLAC).
- One install line:

```bash
pip install mutagen requests pillow static-ffmpeg pyyaml
```

That is everything required for the full pipeline:

| Package | Used for |
|---------|----------|
| `mutagen` | reading and writing audio tags |
| `requests` | downloading cover art |
| `pillow` | validating images before they are embedded |
| `static-ffmpeg` | bundles `ffprobe`, the same engine your media server uses to read cover art |
| `pyyaml` | reading the optional config files |

**Optional - API credentials.** Audio fingerprinting (track identification) and
extended metadata lookups use free APIs. They are not required; the pipeline runs
fine without them and simply skips those steps. To enable them:

```bash
cp configs/templates/credentials.yaml.example configs/active/credentials.yaml
# then edit configs/active/credentials.yaml and add your free AcoustID key, etc.
```

See `configs/README.md` for what each service does.

---

## 2. Point it at your library

Every command takes a path as its first argument. You can point at:

- a single album folder,
- a single artist folder, or
- your entire library root.

Use the path exactly as your system sees it. Examples:

```bash
# Whole library on a network share (forward slashes work everywhere):
"//192.168.1.252/music"

# A single artist on a local drive:
"D:/Music/U2"
```

Always wrap the path in double quotes so spaces are handled correctly. There is no
separate "set the path" step; you pass it on each run.

---

## 3. The pipeline at a glance

Both paths run the same six phases in this fixed order:

```
scan -> identify -> validate -> dedupe -> covers -> fix
```

| Phase | One-sentence description |
|-------|--------------------------|
| **scan** | Read every album's tags, count tracks, and note missing covers or metadata issues. |
| **identify** | For tracks with weak or unknown tags, fingerprint the actual audio (AcoustID) to find what the song really is; skipped silently if no API key. |
| **validate** | Cross-check each album against MusicBrainz and iTunes, score the match, and route it to auto-apply or human review. |
| **dedupe** | Find duplicate copies of a track within an album, keep the best one, and move the rest to a backup folder (nothing is deleted). |
| **covers** | Verify embedded art with `ffprobe`, repair broken or missing art, and write a `folder.jpg` thumbnail where one is missing. |
| **fix** | Apply the approved metadata and cover corrections to the files. |

---

## 4. Safety model (read this once)

Every phase honors the same three modes, and **the default is a preview**:

| Mode | Flag | What it does |
|------|------|--------------|
| Scan only | `--scan-only` | Reports findings; never modifies anything. |
| Dry run | `--dry-run` *(default)* | Shows the exact plan (what would change) without writing. |
| Execute | `--execute` | The only mode that writes to your music. |

Two guarantees worth stating plainly:

- **Nothing is ever deleted.** Duplicate files are *moved* to an off-library
  backup folder (default `D:/music_backup/_duplicates`), so you can always undo.
- **Covers are validated with the same engine your media server uses.** Art is
  checked with `ffprobe` (the tool Jellyfin and anything built on ffmpeg use to
  read embedded art) both before and after writing, so you never end up with the
  blank `width=0` thumbnails that look fine in a tag editor but break in Jellyfin.

**Always dry-run first, then execute.** The recommended habit is to run the
preview, read the summary, and only then re-run with `--execute`.

---

## 5. Path A - plain Python

The whole pipeline is one command. Preview first:

```bash
python cli.py lifecycle "//192.168.1.252/music" --dry-run
```

Read the summary it prints (scanned / validated / needs review / would-dedupe /
covers to repair / would-fix). When you are happy, apply the changes:

```bash
python cli.py lifecycle "//192.168.1.252/music" --execute
```

Useful variations:

```bash
python cli.py lifecycle "<library>" --scan-only            # report only, touch nothing
python cli.py lifecycle "<library>" --execute --backup-dir "D:/music_backup/_duplicates"
python cli.py lifecycle "<library>" --execute --aggressive # dedupe also groups remaster/version variants
python cli.py lifecycle "<library>" --execute --no-fingerprint  # match dupes on metadata only
```

### Running phases individually

You do not have to run the whole pipeline. Each phase is also its own command if
you want to do one thing at a time:

```bash
python cli.py scan          "<library>"                       # extract metadata + audit
python cli.py validate      "<library>"                       # detect + auto-fix folder-name issues
python cli.py consolidate   "<library>"                       # merge multi-disc album sets
python cli.py dedupe        "<library>" --dry-run             # preview duplicate moves
python cli.py dedupe        "<library>" --execute             # move duplicates to backup
python cli.py repair-covers "<library>"                       # detect + re-embed corrupt/missing art
python cli.py embed-cover   "<library>/Artist/Album" "https://.../cover.jpg"
```

---

## 6. Path B - Claude Code (adds AI judgment)

Open this project in Claude Code and run a slash command. The autonomous,
end-to-end workflow is:

```
/clean-music "//192.168.1.252/music"
```

`/clean-music` runs the same phases without permission prompts and adds AI on top:
it resolves conflicts when MusicBrainz and iTunes disagree, and it can **visually
verify** that a cover image actually matches the album (catching art that is a
technically valid image but the wrong cover).

You can also run the lifecycle pipeline directly inside Claude Code:

```
/lifecycle "//192.168.1.252/music"
```

Targeted Claude commands map to the individual phases:

```
/validate-folders "<library>/Artist"      # fix folder-name mismatches
/consolidate-all  "<library>"             # find + merge every multi-disc set
/repair-covers    "<library>/Artist"      # re-fetch / re-embed bad covers
/verify-covers    "<library>"             # AI vision: does the art match the album?
```

**What AI adds, concretely:** the Python core decides everything it can decide
deterministically; Claude steps in only for the judgment calls a script cannot
make safely (which source to trust, is this the right cover). The files produced
are identical in format either way.

---

## 7. Where state and reports go

- `outputs/` - JSON/CSV audit reports and the dedupe move log (for undo).
- `state/` - session state, plus a `run_history.json` summary appended after each
  lifecycle run, and archived queues under `state/history/`.
- `logs/` - processing logs.

Each lifecycle run starts fresh: the previous work queue is archived to
`state/history/queue-<timestamp>.json` and then cleared, so runs do not contaminate
each other. A dated summary of every run is appended to `state/run_history.json`.

---

## 8. Typical first session

```bash
# 1. install
pip install mutagen requests pillow static-ffmpeg pyyaml

# 2. preview the whole pipeline on your library
python cli.py lifecycle "//192.168.1.252/music" --dry-run

# 3. read the summary, then apply
python cli.py lifecycle "//192.168.1.252/music" --execute
```

Or, inside Claude Code, the one-liner equivalent with AI judgment:

```
/clean-music "//192.168.1.252/music"
```

For the full technical reference see [`../README.md`](../README.md) and
[`../CLAUDE.md`](../CLAUDE.md).
