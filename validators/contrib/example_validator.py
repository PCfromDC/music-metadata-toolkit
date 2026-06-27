#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Template contrib validator - copy this to build your own.

This is the documented starting point for the "bring your own validator" path.
It is intentionally trivial: it does NOT call any network or model. Instead it
demonstrates the contract every validator must satisfy:

  1. Subclass :class:`~validators.base.BaseAIValidator`.
  2. Set a unique ``name`` - this is what users put in
     ``ai_validation.provider`` to select your validator.
  3. Declare ``capabilities`` (at least ``{"vision": bool}``).
  4. Implement ``verify_cover_match(image_bytes, album_meta) -> Verdict``.
     NEVER raise for an expected failure (no key, no model, network down) -
     return an ``abstain`` verdict so the caller can fail soft.

To make a real validator, replace the body of ``verify_cover_match`` with a
call to your model/service (import any network library lazily, inside the
method) and translate its answer into a :class:`~validators.base.Verdict`.

Selecting this template (for testing the plumbing) - in ``music-config.yaml``::

    ai_validation:
      enabled: true
      provider: example

Or programmatically::

    from validators import get_validator
    v = get_validator("example", {})
    print(v.verify_cover_match(b"...", {"album": "X", "artist": "Y"}))
"""

from __future__ import annotations

from typing import Any, Dict

from validators.base import BaseAIValidator, Verdict


class ExampleValidator(BaseAIValidator):
    """A no-op example. Returns a deterministic ``uncertain`` verdict.

    Real validators would inspect ``image_bytes`` against ``album_meta`` using a
    vision model. This one just proves the registry can find and load a contrib
    module by name and that it returns a well-formed :class:`Verdict`.
    """

    name = "example"

    @property
    def capabilities(self) -> Dict[str, bool]:
        # This template does not actually look at the image.
        return {"vision": False}

    def verify_cover_match(
        self, image_bytes: bytes, album_meta: Dict[str, Any]
    ) -> Verdict:
        if not image_bytes:
            return self._abstain("no image bytes provided")
        album = album_meta.get("album") or album_meta.get("title") or "(unknown album)"
        return Verdict(
            verdict="uncertain",
            confidence=0.5,
            notes=f"example validator received {len(image_bytes)} bytes for {album!r}",
            provider=self.name,
        )
