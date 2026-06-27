#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pluggable AI cover-art validators (optional second-opinion layer).

The deterministic cover checks in ``utilities/core/`` are always-on and do not
depend on anything here. This package adds an OPTIONAL AI "second opinion" on
whether embedded album art visually matches an album. The DEFAULT
(:class:`~validators.null.NullValidator`) abstains and makes zero network
calls, so the public, zero-config experience needs no AI and no internet.

Public API:
    from validators import get_validator, Verdict, BaseAIValidator
    v = get_validator("null", {})            # default, always abstains
    verdict = v.verify_cover_match(b"", {})  # -> Verdict(verdict="abstain", ...)

Bring your own validator via ``validators/contrib/`` or an entry point in the
``music_toolkit.validators`` group - see ``docs/AI_VALIDATORS.md``.
"""

from __future__ import annotations

from .base import VERDICTS, BaseAIValidator, Verdict
from .null import NullValidator
from .registry import available_validators, get_validator

__all__ = [
    "BaseAIValidator",
    "Verdict",
    "VERDICTS",
    "NullValidator",
    "get_validator",
    "available_validators",
]
