#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared prompt + response parsing for vision validators.

Kept separate so every provider asks the model the same question and parses the
answer the same way. No network or SDK imports here.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict

from .base import VERDICTS, Verdict

SYSTEM_PROMPT = (
    "You are a meticulous music-library assistant. You are shown an album "
    "cover image and the album's metadata. Decide whether the image is "
    "plausibly the correct front cover for that album. Be conservative: only "
    "say 'mismatch' when the artwork clearly belongs to a different album or "
    "is obviously not album art."
)


def build_user_prompt(album_meta: Dict[str, Any]) -> str:
    """Build the text portion of the prompt from album metadata."""
    album = album_meta.get("album") or album_meta.get("title") or "(unknown)"
    artist = album_meta.get("artist") or album_meta.get("albumartist") or "(unknown)"
    year = album_meta.get("year") or album_meta.get("date") or ""
    extra = f" (released {year})" if year else ""
    return (
        f"Album: {album}\n"
        f"Artist: {artist}{extra}\n\n"
        "Does the attached image look like the correct front cover for this "
        "album? Respond ONLY with a compact JSON object of the form:\n"
        '{"verdict": "match|mismatch|uncertain", "confidence": 0.0-1.0, '
        '"notes": "<short reason>"}'
    )


def encode_image_data_url(image_bytes: bytes) -> str:
    """Return a base64 ``data:`` URL for OpenAI-style image parts."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    mime = "image/png" if image_bytes[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return f"data:{mime};base64,{b64}"


def encode_image_b64(image_bytes: bytes) -> str:
    """Return bare base64 (Ollama / Anthropic style)."""
    return base64.b64encode(image_bytes).decode("ascii")


def _first_json_object(text: str) -> Dict[str, Any]:
    """Return the first valid JSON object embedded in ``text``, or ``{}``.

    Scans each ``{`` and uses a raw decoder so trailing prose after a complete
    object (e.g. ``{...}. Note: see below``) does not defeat parsing - unlike a
    greedy ``{.*}`` regex, which spans to the last ``}`` and fails on the inner
    brace.
    """
    decoder = json.JSONDecoder()
    index = text.find("{")
    while index != -1:
        try:
            obj, _ = decoder.raw_decode(text, index)
        except ValueError:
            index = text.find("{", index + 1)
            continue
        if isinstance(obj, dict):
            return obj
        index = text.find("{", index + 1)
    return {}


def parse_verdict(text: Any, provider: str) -> Verdict:
    """Parse a model's free-text answer into a :class:`Verdict`.

    Prefers a JSON object embedded in the response (the format we ask for). If
    no usable verdict can be parsed, returns ``uncertain`` rather than guessing
    from naive substrings - a prose answer like "there is no mismatch" must not
    be misread as a mismatch (which would get logged as a false positive). Never
    raises: a non-string ``text`` is coerced safely.
    """
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    if not text.strip():
        return Verdict("abstain", 0.0, "empty model response", provider)

    payload = _first_json_object(text)
    verdict = str(payload.get("verdict", "")).strip().lower()
    if verdict not in VERDICTS or verdict == "abstain":
        # Could not extract a clear verdict; do NOT guess from substrings
        # (negations like "no mismatch" would invert). Stay conservative.
        verdict = "uncertain"

    try:
        confidence = float(payload.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5

    notes = str(payload.get("notes") or text.strip())[:300]
    return Verdict(verdict=verdict, confidence=confidence, notes=notes, provider=provider)
