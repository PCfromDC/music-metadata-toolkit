#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validator for any OpenAI-compatible chat-completions endpoint.

Works with LM Studio, vLLM, OpenRouter, llama.cpp server, and the OpenAI API
itself - anything that speaks ``POST /v1/chat/completions`` with vision message
parts (``image_url`` content blocks). ``requests`` is imported lazily; any
failure degrades to ``abstain``.

Config keys (from the ``ai_validation`` block):
  * ``endpoint``: base URL incl. ``/v1`` if required, e.g.
    ``http://localhost:1234/v1`` (LM Studio) or ``https://api.openai.com/v1``
  * ``model``: vision-capable model name, e.g. ``gpt-4o-mini``
  * ``api_key``: bearer token (optional for local servers). Falls back to the
    ``OPENAI_API_KEY`` environment variable.
  * ``timeout``: seconds, default 60
"""

from __future__ import annotations

import os
from typing import Any, Dict

from ._prompt import (
    SYSTEM_PROMPT,
    build_user_prompt,
    encode_image_data_url,
    parse_verdict,
)
from .base import BaseAIValidator, Verdict

DEFAULT_ENDPOINT = "http://localhost:1234/v1"
DEFAULT_MODEL = "gpt-4o-mini"


class OpenAICompatValidator(BaseAIValidator):
    """Vision validator for OpenAI-compatible servers."""

    name = "openai_compat"

    def __init__(self, config: Dict[str, Any] | None = None):
        super().__init__(config)
        self.endpoint = self.endpoint or DEFAULT_ENDPOINT
        self.model = self.model or DEFAULT_MODEL
        self.api_key = str(
            self.config.get("api_key") or os.environ.get("OPENAI_API_KEY") or ""
        )

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

        url = f"{self.endpoint}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": build_user_prompt(album_meta)},
                        {
                            "type": "image_url",
                            "image_url": {"url": encode_image_data_url(image_bytes)},
                        },
                    ],
                },
            ],
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # network/JSON/HTTP -> fail soft
            return self._abstain(f"openai-compatible request failed: {exc}")

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return self._abstain("unexpected response shape")
        return parse_verdict(_content_to_text(content), self.name)


def _content_to_text(content: Any) -> str:
    """Normalize a chat message ``content`` to text.

    Some OpenAI-compatible servers return ``content`` as a list of parts
    (``[{"type": "text", "text": "..."}, ...]``) rather than a plain string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""
