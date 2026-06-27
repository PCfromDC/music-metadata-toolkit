# AI Validate Covers Command

Run the OPTIONAL AI "second opinion" pass over embedded album cover art to flag
art that is technically valid but visually WRONG for the album.

## Usage

```
/ai-validate-covers <path>
```

## Examples

```
/ai-validate-covers /path/to/music/Various Artists
/ai-validate-covers D:/music/Ben Harper
```

## Instructions

When this command is invoked with a path argument: $ARGUMENTS

**Path Normalization:**
Replace all backslashes (`\`) with forward slashes (`/`).

**Execute the validation pass (NON-DESTRUCTIVE - never deletes or replaces art):**

1. **Run the validator** over the path:
   ```bash
   cd "D:\music cleanup" && python utilities/ai_validate_covers.py "<normalized_path>"
   ```

2. **Behavior depends on `ai_validation` in `music-config.yaml`:**
   - Default (`enabled: false` / `provider: null`): the `NullValidator` runs,
     every album abstains, and NO network calls are made. This is the safe,
     zero-AI default.
   - If a provider is configured (ollama, openai_compat, anthropic, hermes, or a
     contrib validator), that validator judges each album's art.

3. **High-confidence mismatches** (confidence >= 0.80) are logged to
   `.claude/knowledge/patterns.json` under `ai_cover_mismatches` for review.
   The command does NOT auto-fix; review and fix manually with `embed_cover.py`.

4. **Report summary** from the command output:
   - albums, checked, mismatches, abstained, errors

## Provider selection (optional)

To use a specific provider for one run without editing the config:

```bash
cd "D:\music cleanup" && python utilities/ai_validate_covers.py "<path>" --provider ollama --endpoint http://localhost:11434 --model llava
```

## Notes

- This layer is OPTIONAL and sits on top of the always-on deterministic cover
  checks in `utilities/core/`. It adds a visual-match opinion only.
- `fail_mode: soft` (default) means any AI error is logged and the scan
  continues. Set `fail_mode: hard` in config to re-raise.
- See `docs/AI_VALIDATORS.md` to bring your own validator.
