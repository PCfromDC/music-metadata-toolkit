#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validator discovery and construction.

Resolves a provider name (from the ``ai_validation.provider`` config field) to a
constructed :class:`~validators.base.BaseAIValidator`. Resolution order:

  1. Built-in providers shipped in this package (null, ollama, openai_compat,
     anthropic, hermes).
  2. ``validators/contrib/`` modules - drop a file in there exporting a
     ``BaseAIValidator`` subclass and it is discoverable by ``name``.
  3. Installed packages that register an entry point in the
     ``music_toolkit.validators`` group (the "bring your own validator,
     pip-installable" path).

Unknown names fall back to :class:`~validators.null.NullValidator` so the
toolkit never crashes on a typo - it just abstains.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any, Dict, Optional, Type

from .base import BaseAIValidator
from .null import NullValidator

ENTRY_POINT_GROUP = "music_toolkit.validators"

# Built-in providers keyed by their stable name. Imported lazily in
# _load_builtin so importing the package (and registry) never imports requests.
_BUILTIN_MODULES = {
    "null": ("validators.null", "NullValidator"),
    "ollama": ("validators.ollama", "OllamaValidator"),
    "openai_compat": ("validators.openai_compat", "OpenAICompatValidator"),
    "anthropic": ("validators.anthropic", "AnthropicValidator"),
    "hermes": ("validators.hermes", "HermesValidator"),
}


def _load_builtin(name: str) -> Optional[Type[BaseAIValidator]]:
    spec = _BUILTIN_MODULES.get(name)
    if not spec:
        return None
    module_name, class_name = spec
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def _iter_contrib_classes():
    """Yield (name, class) for every BaseAIValidator subclass in contrib/."""
    from . import contrib  # local import keeps package import cheap

    for module_info in pkgutil.iter_modules(contrib.__path__):
        try:
            module = importlib.import_module(f"{contrib.__name__}.{module_info.name}")
        except Exception:
            continue  # a broken contrib module must not break discovery
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseAIValidator)
                and obj is not BaseAIValidator
                and obj.__module__ == module.__name__
            ):
                yield getattr(obj, "name", module_info.name), obj


def _load_contrib(name: str) -> Optional[Type[BaseAIValidator]]:
    for candidate_name, obj in _iter_contrib_classes():
        if candidate_name == name:
            return obj
    return None


def _load_entry_point(name: str) -> Optional[Type[BaseAIValidator]]:
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover - Python < 3.8
        return None

    try:
        eps = entry_points(group=ENTRY_POINT_GROUP)
    except TypeError:  # pragma: no cover - older importlib.metadata API
        eps = entry_points().get(ENTRY_POINT_GROUP, [])

    for ep in eps:
        if ep.name == name:
            try:
                obj = ep.load()
            except Exception:
                continue
            if inspect.isclass(obj) and issubclass(obj, BaseAIValidator):
                return obj
    return None


def get_validator(name: Optional[str], config: Dict[str, Any] | None = None) -> BaseAIValidator:
    """Construct the validator named ``name``, configured with ``config``.

    Falls back to :class:`NullValidator` when ``name`` is missing, empty,
    ``"null"``, or cannot be resolved - so callers always get a usable
    validator and never an exception for a bad provider name.
    """
    config = config or {}
    if not name or name == "null":
        return NullValidator(config)

    cls = _load_builtin(name) or _load_contrib(name) or _load_entry_point(name)
    if cls is None:
        # Unknown provider: degrade to abstain rather than crash.
        return NullValidator(config)
    return cls(config)


def available_validators() -> Dict[str, str]:
    """Return a ``name -> source`` map of every discoverable validator.

    ``source`` is ``"builtin"``, ``"contrib"``, or ``"entry_point"``. Useful for
    CLIs and docs ("which validators can I pick?").
    """
    found: Dict[str, str] = {name: "builtin" for name in _BUILTIN_MODULES}
    for name, _ in _iter_contrib_classes():
        found.setdefault(name, "contrib")
    try:
        from importlib.metadata import entry_points

        try:
            eps = entry_points(group=ENTRY_POINT_GROUP)
        except TypeError:  # pragma: no cover
            eps = entry_points().get(ENTRY_POINT_GROUP, [])
        for ep in eps:
            found.setdefault(ep.name, "entry_point")
    except Exception:
        pass
    return found
