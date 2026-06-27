# Verify Build Command

Run the cover-art test harness to confirm the core pipeline is green before
committing or opening a PR.

## Usage

```
/verify-build
```

## Instructions

When this command is invoked, run the deterministic test harness for the
foundation core. Both steps must pass.

1. **Run the full test suite:**

   ```bash
   python -m pytest tests/ -q
   ```

   Expect every test to pass. The fixtures synthesize real MP3/M4A/FLAC streams
   with the bundled ffmpeg from `static-ffmpeg`; the first run may download the
   ffmpeg/ffprobe binaries.

2. **Run the standalone round-trip smoke check:**

   ```bash
   python tests/cover_roundtrip_check.py
   ```

   This embeds a cover into one file per format and confirms ffprobe (the engine
   Jellyfin uses) reports a cover stream with real, non-zero dimensions. It
   prints a per-format line and a final `PASS`/`FAIL`, exiting `0` on PASS.

## Report

Summarize the outcome:

- Number of tests passed/failed from pytest.
- The final `PASS`/`FAIL` line from the round-trip check.
- If anything fails, surface the first failing assertion and the file it came
  from. Do not "fix" by weakening an assertion; investigate the core change.

## Why This Matters

The toolkit previously embedded invalid cover art (ffprobe reported
`width=0, height=0`) with no validation. This harness is the guardrail that
proves every embed produces art a real consumer can read. Run it whenever the
cover-art core, ffprobe helpers, or audio-file helpers change.
