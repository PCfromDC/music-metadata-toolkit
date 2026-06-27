#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local-vision validator backed by Ollama (e.g. llava, llama3.2-vision).

Talks to a local Ollama server's ``/api/chat`` endpoint. Nothing leaves the
machine, so this is the recommended provider for users who want a private
second opinion. ``requests`` is imported lazily so the package imports cleanly
without it; any error degrades to an ``abstain`` verdict.

Config keys (from the ``ai_validation`` block):
  * ``endpoint``: base URL, default ``http://localhost:11434``
  * ``model``: vision model name, default ``llava``
  * ``timeout``: seconds, default 60
"""

from __future__ import annotations

from typing import Any, Dict

from ._prompt import SYSTEM_PROMPT, build_user_prompt, encode_image_b64, parse_verdict
from .base import BaseAIValidator, Verdict

DEFAULT_ENDPOINT = "http://localhost:11434"
DEFAULT_MODEL = "llava"


class OllamaValidator(BaseAIValidator):
    """Vision validator using a local Ollama server."""

    name = "ollama"

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.endpoint = self.endpoint or DEFAULT_ENDPOINT
        self.model = self.model or DEFAULT_MODEL

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {"vision": True}

    def verify_cover_match(
        self, image_bytes: bytes, album_meta: Dict[str, Any]
    ) -> Verdict:
        if not image_bytes:
            return self._abstain("no image bytes provided")
        try:
            import requests
        except ImportError:
            return self._abstain("requests not installed")

        url = f"{self.endpoint}/api/chat"
        body = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_user_prompt(album_meta),
                    "images": [encode_image_b64(image_bytes)],
                },
            ],
        }
        try:
            resp = requests.post(url, json=body, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # network/JSON/HTTP -> fail soft
            return self._abstain(f"ollama request failed: {exc}")

        content = (data.get("message") or {}).get("content", "")
        return parse_verdict(content, self.name)
