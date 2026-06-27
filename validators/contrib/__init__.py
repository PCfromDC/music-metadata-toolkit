#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Drop-in validators.

Any module placed in this package that exports a
:class:`~validators.base.BaseAIValidator` subclass is auto-discovered by the
registry and selectable by its ``name`` attribute via
``ai_validation.provider`` in ``music-config.yaml``.

See ``example_validator.py`` for a documented template, and
``docs/AI_VALIDATORS.md`` for the full guide.
"""
