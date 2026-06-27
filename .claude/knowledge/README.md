# Knowledge Base

Persistent learning store for the music-metadata toolkit. These JSON files let
the clean/repair flows remember corrections across sessions instead of starting
fresh every time. They are plain JSON (no secrets) and are safe to commit.

## Files and Schemas

### corrections.json (append-only log)
Every applied correction is appended here.

```json
{
  "_description": "...",
  "corrections": [
    {
      "album_path": "Artist/Album or absolute path (forward slashes)",
      "correction_type": "cover_art | metadata | folder_rename | ...",
      "before": { "hash": "...", "size_kb": 0, "description": "..." },
      "after":  { "url": "...", "size_kb": 0, "source": "itunes|musicbrainz|manual" },
      "date": "YYYY-MM-DD",
      "source": "itunes|musicbrainz|manual (optional)"
    }
  ]
}
```

### cover_art_mapping.json (album -> known-correct cover)
Pins a verified correct cover URL per album so future passes skip re-searching.

```json
{
  "_description": "...",
  "albums": {
    "Artist/Album": {
      "correct_url": "https://.../1200x1200bb.jpg",
      "verified_date": "YYYY-MM-DD",
      "source": "itunes|manual",
      "notes": "..."
    }
  }
}
```

The album key is the last two path segments (`Artist/Album`), derived by
`KnowledgeBase.album_key()` and by `utilities/embed_cover.py`.

### patterns.json (human-curated, read-mostly)
Catalogue of issue patterns the clean flow checks against. Each entry has
`id`, `name`, `description`, `detection` (`conditions`, `severity`,
`confidence_threshold`), `discovered`, and `example`. New patterns are added by
humans (or a reviewer) when a recurring issue is identified; the flows read this
file but do not auto-append to it.

## Read/Write Contract

| File | Written by | Read by |
|------|-----------|---------|
| corrections.json | `utilities/embed_cover.py::log_cover_correction` (append) | `/suggest-fixes`, `orchestrator/claude_agents.py::KnowledgeBase.load_corrections` |
| cover_art_mapping.json | `embed_cover.py --force` / `log_cover_correction` (upsert by album key) | `/clean-music`, `/verify-covers`, `cover_art_verifier`, `KnowledgeBase.known_cover_url` |
| patterns.json | humans / reviewer (manual) | `/suggest-fixes`, `KnowledgeBase.load_patterns` |

Rules:
- **Reads fail soft.** Missing or malformed files yield empty structures
  (`KnowledgeBase._load`), so the toolkit runs without a knowledge base.
- **Writes are additive.** corrections.json only appends; cover_art_mapping.json
  upserts a single album key; patterns.json is not written automatically.
- **Encoding** is UTF-8, pretty-printed (`indent=2`) to stay diff-friendly.
- **Keys** in cover_art_mapping.json use forward slashes and the `Artist/Album`
  form regardless of OS path separators.
- **No secrets.** API tokens live in `configs/active/` (gitignored), never here.

## Programmatic Access

```python
from orchestrator.claude_agents import KnowledgeBase

kb = KnowledgeBase()                       # defaults to .claude/knowledge
url = kb.known_cover_url(album_path)       # verified cover URL, or None
prior = kb.past_corrections(album_path)    # list of logged corrections
patterns = kb.load_patterns()              # learned issue patterns
```

`AgentWorkflow.decide_auto_apply()` folds `known_cover_url` and the prior
corrections count into its pre-apply decision so the agents benefit from past
fixes automatically.
