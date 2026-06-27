# AI Cover-Art Validators (optional second opinion)

The deterministic cover checks in `utilities/core/` (Pillow + ffprobe) are
**always-on** and require no AI and no network. They guarantee that embedded art
is a real, decodable image with valid dimensions.

What they cannot tell you is whether the art is the *correct* cover for the
album (the "Ben Harper problem": a technically-valid image that visually belongs
to a different album). That is what this OPTIONAL, pluggable AI layer adds: a
configurable "second opinion" that looks at the art and the album metadata and
returns a verdict.

## Zero-AI by default

Out of the box the toolkit ships with AI validation **off**:

```yaml
# music-config.yaml
ai_validation:
  enabled: false
  provider: null
```

With this default, `python utilities/ai_validate_covers.py <album>` runs the
`NullValidator`, which abstains on every album and makes **zero network calls**.
You never need an AI key or an internet connection to use the toolkit.

## Running a pass

```bash
# Default (NullValidator) - scans, extracts art via core, reports abstain
python utilities/ai_validate_covers.py "/path/to/music/Artist"

# Pick a provider for this run only
python utilities/ai_validate_covers.py "/path/to/album" --provider ollama --endpoint http://localhost:11434 --model llava

# Force-enable whatever provider is configured in music-config.yaml
python utilities/ai_validate_covers.py "/path/to/music/Artist" --enable
```

The CLI is **non-destructive**. On a high-confidence `mismatch` (confidence
>= 0.80) it appends a note to `.claude/knowledge/patterns.json` under
`ai_cover_mismatches` for a human to review. It never deletes or replaces art.

`fail_mode: soft` (the default) logs any validator/network error and continues;
`fail_mode: hard` re-raises.

## The verdict contract

Every validator returns a `Verdict`:

| Field        | Meaning                                                              |
| ------------ | ------------------------------------------------------------------- |
| `verdict`    | `match` / `mismatch` / `uncertain` / `abstain`                      |
| `confidence` | 0.0 - 1.0 (treat `abstain` as 0.0)                                  |
| `notes`      | short human-readable explanation                                    |
| `provider`   | which validator produced it                                         |

`abstain` means "I did not / could not judge" - the default, the null provider,
any non-vision provider, and any soft error all abstain.

## Built-in providers

| `provider`       | Backend                                  | Needs                                  |
| ---------------- | ---------------------------------------- | -------------------------------------- |
| `null`           | none (default)                           | nothing                                |
| `ollama`         | local Ollama vision model (e.g. `llava`) | Ollama running locally                 |
| `openai_compat`  | LM Studio / vLLM / OpenRouter / OpenAI   | endpoint (+ key for cloud)             |
| `anthropic`      | Claude vision (Messages API)             | `ANTHROPIC_API_KEY`                    |
| `hermes`         | a configurable Hermes/Jarvis gateway     | your gateway `endpoint`                |

Example config for a local Ollama vision model (fully local, private):

```yaml
ai_validation:
  enabled: true
  provider: ollama
  endpoint: "http://localhost:11434"
  model: "llava"
```

API keys can come from `configs/active/credentials.yaml` (see
`configs/templates/credentials.yaml.example`) or from environment variables
(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `HERMES_API_KEY`).

## Bring your own validator

There are two ways to add a validator without touching the toolkit's code.

### 1. Drop a file in `validators/contrib/`

Copy `validators/contrib/example_validator.py` and edit it. The registry
auto-discovers any `BaseAIValidator` subclass in that folder and makes it
selectable by its `name`:

```python
# validators/contrib/my_validator.py
from typing import Any, Dict
from validators.base import BaseAIValidator, Verdict

class MyValidator(BaseAIValidator):
    name = "my-validator"  # what you put in ai_validation.provider

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {"vision": True}

    def verify_cover_match(self, image_bytes: bytes, album_meta: Dict[str, Any]) -> Verdict:
        # import any network library lazily, inside the method
        # call your model/service, then translate its answer:
        return Verdict(verdict="match", confidence=0.9, notes="...", provider=self.name)
```

```yaml
ai_validation:
  enabled: true
  provider: my-validator
```

### 2. Register a pip-installable entry point

In your own package's `pyproject.toml`:

```toml
[project.entry-points."music_toolkit.validators"]
my-validator = "my_package.module:MyValidator"
```

After `pip install`, select it the same way (`provider: my-validator`).

### Rules every validator must follow

1. Subclass `BaseAIValidator` and set a unique `name`.
2. Declare `capabilities` - at least `{"vision": bool}`. A non-vision provider
   must `abstain`.
3. Implement `verify_cover_match(image_bytes, album_meta) -> Verdict`.
4. **Never raise for an expected failure** (missing key/endpoint, network down,
   model refusal). Return an `abstain` verdict (use `self._abstain("...")`) so
   the caller can fail soft.
5. Import network libraries lazily inside methods, never at module top level -
   importing the `validators` package must not require `requests` or any SDK.

## Listing what is available

```python
from validators import available_validators
print(available_validators())
# {'null': 'builtin', 'ollama': 'builtin', ..., 'example': 'contrib', ...}
```
