#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The DEFAULT validator: always abstain, never touch the network.

:class:`NullValidator` is what the toolkit uses when AI validation is disabled
(the default) or when ``provider: null`` is configured. It guarantees:

  * zero network calls,
  * zero imports of ``requests`` or any provider SDK,
  * an ``abstain`` verdict for every input.

Keeping this trivial is the whole point: the public, zero-config experience
must never require an AI key, a local model, or an internet connection.
"""

from __future__ import annotations

from typing import Any, Dict

from .base import BaseAIValidator, Verdict


class NullValidator(BaseAIValidator):
    """No-op validator that always abstains."""

    name = "null"

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {"vision": False}

    def verify_cover_match(
        self, image_bytes: bytes, album_meta: Dict[str, Any]
    ) -> Verdict:
        return self._abstain("AI validation disabled (NullValidator)")
